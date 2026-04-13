"""
main.py — FastAPI application entry point.

Endpoints
---------
GET  /api/releases
GET  /api/results/{sop}/{release}
GET  /api/tickets
GET  /api/tickets/{tc_id}
GET  /api/fix-alerts
GET  /api/stats/{sop}/{release}
GET  /api/traceability
GET  /api/diff/{sop}/{rel_a}/{rel_b}
POST /api/seed-demo          (loads mock data for development/demo)
"""

import os
from contextlib import asynccontextmanager
from typing import Any

import psycopg2.extras
import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

from database import get_conn, init_db, upsert_result, upsert_ticket
from models import TCResult, JiraTicket, ReleaseInfo, DomainStats, DiffEntry, TraceabilityEntry
import watcher

load_dotenv()

# ---------------------------------------------------------------------------
# Lifespan: init DB + start background watcher
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    watcher.start_background()
    yield


app = FastAPI(title="BMS Test Intelligence", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _rows(conn, sql: str, params=()) -> list[dict]:
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(sql, params)
        return [dict(r) for r in cur.fetchall()]


def _row(conn, sql: str, params=()) -> dict | None:
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(sql, params)
        r = cur.fetchone()
        return dict(r) if r else None


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.get("/api/releases", response_model=list[ReleaseInfo])
def get_releases():
    with get_conn() as conn:
        return _rows(conn, "SELECT DISTINCT sop, release FROM tc_results ORDER BY sop, release")


@app.get("/api/results/{sop}/{release}", response_model=list[TCResult])
def get_results(sop: str, release: str):
    with get_conn() as conn:
        return _rows(
            conn,
            "SELECT * FROM tc_results WHERE sop=%s AND release=%s ORDER BY domain, tc_id",
            (sop, release),
        )


@app.get("/api/tickets", response_model=list[JiraTicket])
def get_tickets():
    with get_conn() as conn:
        rows = _rows(
            conn,
            """SELECT * FROM jira_tickets
               ORDER BY
                 CASE fix_status
                   WHEN 'FIX_FAILED'    THEN 1
                   WHEN 'OPEN'          THEN 2
                   WHEN 'IN_PROGRESS'   THEN 3
                   WHEN 'FIX_PENDING'   THEN 4
                   WHEN 'FIX_CONFIRMED' THEN 5
                   ELSE 6
                 END,
                 CASE priority
                   WHEN 'Critical' THEN 1
                   WHEN 'High'     THEN 2
                   WHEN 'Medium'   THEN 3
                   WHEN 'Low'      THEN 4
                   ELSE 5
                 END""",
        )
        return [_coerce_ticket_dates(r) for r in rows]


@app.get("/api/tickets/{tc_id}", response_model=JiraTicket)
def get_ticket(tc_id: str):
    with get_conn() as conn:
        row = _row(conn, "SELECT * FROM jira_tickets WHERE tc_id=%s", (tc_id,))
    if not row:
        raise HTTPException(status_code=404, detail="Ticket not found")
    return _coerce_ticket_dates(row)


@app.get("/api/fix-alerts", response_model=list[JiraTicket])
def get_fix_alerts():
    with get_conn() as conn:
        rows = _rows(conn, "SELECT * FROM jira_tickets WHERE fix_status='FIX_FAILED'")
        return [_coerce_ticket_dates(r) for r in rows]


@app.get("/api/stats/{sop}/{release}", response_model=list[DomainStats])
def get_stats(sop: str, release: str):
    with get_conn() as conn:
        tc_rows = _rows(
            conn,
            "SELECT tc_id, domain, result FROM tc_results WHERE sop=%s AND release=%s",
            (sop, release),
        )
        ticket_rows = _rows(conn, "SELECT tc_id, status, fix_status FROM jira_tickets")

    ticket_map: dict[str, dict] = {t["tc_id"]: t for t in ticket_rows}
    domains: dict[str, dict] = {}
    for r in tc_rows:
        d = r["domain"]
        if d not in domains:
            domains[d] = {
                "domain": d, "total": 0, "passed": 0, "failed": 0, "inconclusive": 0,
                "open_tickets": 0, "in_progress": 0, "fixed": 0, "fix_failed": 0,
            }
        s = domains[d]
        s["total"] += 1
        if r["result"] == "PASS":
            s["passed"] += 1
        elif r["result"] == "FAIL":
            s["failed"] += 1
            t = ticket_map.get(r["tc_id"])
            if t:
                if t["fix_status"] == "FIX_CONFIRMED":
                    s["fixed"] += 1
                elif t["fix_status"] == "FIX_FAILED":
                    s["fix_failed"] += 1
                elif t["status"] == "IN_PROGRESS":
                    s["in_progress"] += 1
                else:
                    s["open_tickets"] += 1
        else:
            s["inconclusive"] += 1

    result = []
    for s in domains.values():
        s["pass_rate"] = round(s["passed"] / s["total"] * 100, 1) if s["total"] else 0.0
        result.append(DomainStats(**s))
    return sorted(result, key=lambda x: x.domain)


@app.get("/api/traceability", response_model=list[TraceabilityEntry])
def get_traceability():
    with get_conn() as conn:
        tc_rows = _rows(conn, """
            SELECT tc_id, tc_name, domain, sop, release, result
            FROM tc_results
            ORDER BY sop, domain, tc_id, release
        """)
        ticket_rows = _rows(conn, "SELECT * FROM jira_tickets")

    ticket_map: dict[str, dict] = {t["tc_id"]: t for t in ticket_rows}

    # Group by (sop, tc_id, domain) and collect results per release
    groups: dict[tuple, dict] = {}
    for r in tc_rows:
        key = (r["sop"], r["tc_id"], r["domain"])
        if key not in groups:
            groups[key] = {
                "tc_id": r["tc_id"],
                "tc_name": r["tc_name"],
                "domain": r["domain"],
                "sop": r["sop"],
                "result_per_release": {},
            }
        groups[key]["result_per_release"][r["release"]] = r["result"]

    entries: list[TraceabilityEntry] = []
    for (sop, tc_id, domain), g in groups.items():
        # Only include TCs with at least one FAIL
        if "FAIL" not in g["result_per_release"].values():
            continue
        # Find the first release where it failed
        fail_release = next(
            (rel for rel, res in g["result_per_release"].items() if res == "FAIL"), ""
        )
        t = ticket_map.get(tc_id)
        entries.append(TraceabilityEntry(
            tc_id=tc_id,
            tc_name=g["tc_name"],
            domain=domain,
            sop=sop,
            fail_release=fail_release,
            result_per_release=g["result_per_release"],
            jira_id=t["jira_id"] if t else None,
            jira_url=t["jira_url"] if t else None,
            status=t["status"] if t else None,
            fix_release=t["fix_release"] if t else None,
            fix_status=t["fix_status"] if t else None,
            priority=t["priority"] if t else None,
            assignee=t["assignee"] if t else None,
        ))
    return sorted(entries, key=lambda e: (e.domain, e.tc_id))


@app.get("/api/diff/{sop}/{rel_a}/{rel_b}", response_model=list[DiffEntry])
def get_diff(sop: str, rel_a: str, rel_b: str):
    with get_conn() as conn:
        rows_a = {r["tc_id"]: r for r in _rows(
            conn,
            "SELECT tc_id, tc_name, domain, result FROM tc_results WHERE sop=%s AND release=%s",
            (sop, rel_a),
        )}
        rows_b = {r["tc_id"]: r for r in _rows(
            conn,
            "SELECT tc_id, tc_name, domain, result FROM tc_results WHERE sop=%s AND release=%s",
            (sop, rel_b),
        )}
        ticket_rows = _rows(conn, "SELECT tc_id, jira_id, jira_url, fix_status FROM jira_tickets")
    ticket_map = {t["tc_id"]: t for t in ticket_rows}

    all_ids = set(rows_a) | set(rows_b)
    entries: list[DiffEntry] = []
    for tc_id in sorted(all_ids):
        ra = rows_a.get(tc_id)
        rb = rows_b.get(tc_id)
        res_a = ra["result"] if ra else None
        res_b = rb["result"] if rb else None
        domain = (rb or ra)["domain"]
        tc_name = (rb or ra).get("tc_name")

        if res_a == res_b:
            change_type = "UNCHANGED"
        elif res_b is None:
            change_type = "UNCHANGED"
        elif res_a is None:
            change_type = "NEW"
        elif res_a != "FAIL" and res_b == "FAIL":
            change_type = "REGRESSION"
        elif res_a == "FAIL" and res_b != "FAIL":
            change_type = "FIXED"
        else:
            change_type = "UNCHANGED"

        t = ticket_map.get(tc_id)
        entries.append(DiffEntry(
            tc_id=tc_id,
            tc_name=tc_name,
            domain=domain,
            result_a=res_a,
            result_b=res_b,
            change_type=change_type,
            jira_id=t["jira_id"] if t else None,
            jira_url=t["jira_url"] if t else None,
            fix_status=t["fix_status"] if t else None,
        ))
    return [e for e in entries if e.change_type != "UNCHANGED"]


# ---------------------------------------------------------------------------
# Demo seed endpoint (POST /api/seed-demo)
# ---------------------------------------------------------------------------

DEMO_RELEASES = [
    ("SOP2606", "i450-ATS"),
    ("SOP2606", "i450-ATS+2"),
    ("SOP2606", "i460-ATS"),
    ("SOP2606", "i520-ATS"),
    ("SOP2611", "i450-ATS"),
    ("SOP2611", "i460-ATS"),
]

DEMO_TCS: list[dict[str, Any]] = [
    {"tc_id":"TC_HSI_012","tc_name":"HVIL_StatusCheck_IgnCycle","domain":"HSI",
     "results":{"i450-ATS":"FAIL","i450-ATS+2":"FAIL","i460-ATS":"FAIL","i520-ATS":"PASS"}},
    {"tc_id":"TC_HSI_031","tc_name":"Interlock_Verify_ChargeSeq","domain":"HSI",
     "results":{"i450-ATS":"FAIL","i450-ATS+2":"PASS","i460-ATS":"PASS","i520-ATS":"PASS"}},
    {"tc_id":"TC_HSI_044","tc_name":"PreCharge_RelayClose_200ms","domain":"HSI",
     "results":{"i450-ATS":"PASS","i450-ATS+2":"FAIL","i460-ATS":"FAIL","i520-ATS":"PASS"}},
    {"tc_id":"TC_HSI_005","tc_name":"HVIL_Open_Detection","domain":"HSI",
     "results":{"i450-ATS":"PASS","i450-ATS+2":"FAIL","i460-ATS":"PASS","i520-ATS":"PASS"}},
    {"tc_id":"TC_HSI_002","tc_name":"HVIL_Close_Detection","domain":"HSI",
     "results":{"i450-ATS":"PASS","i450-ATS+2":"PASS","i460-ATS":"PASS","i520-ATS":"PASS"}},
    {"tc_id":"TC_HSI_017","tc_name":"Contactor_Weld_Detection","domain":"HSI",
     "results":{"i450-ATS":"PASS","i450-ATS+2":"PASS","i460-ATS":"PASS","i520-ATS":"PASS"}},
    {"tc_id":"TC_HSI_023","tc_name":"PreCharge_Timeout_1000ms","domain":"HSI",
     "results":{"i450-ATS":"PASS","i450-ATS+2":"PASS","i460-ATS":"PASS","i520-ATS":"PASS"}},
    {"tc_id":"TC_HSI_038","tc_name":"Interlock_Open_DriveCycle","domain":"HSI",
     "results":{"i450-ATS":"PASS","i450-ATS+2":"PASS","i460-ATS":"PASS","i520-ATS":"PASS"}},
    {"tc_id":"TC_DIAG_041","tc_name":"DTC_ReadActive","domain":"Diagnostics",
     "results":{"i450-ATS":"FAIL","i450-ATS+2":"FAIL","i460-ATS":"PASS","i520-ATS":"PASS"}},
    {"tc_id":"TC_DIAG_087","tc_name":"NRC_Handling_0x22","domain":"Diagnostics",
     "results":{"i450-ATS":"FAIL","i450-ATS+2":"FAIL","i460-ATS":"PASS","i520-ATS":"PASS"}},
    {"tc_id":"TC_DIAG_056","tc_name":"DTC_Clear_All","domain":"Diagnostics",
     "results":{"i450-ATS":"FAIL","i450-ATS+2":"PASS","i460-ATS":"PASS","i520-ATS":"PASS"}},
    {"tc_id":"TC_DIAG_072","tc_name":"ECUReset_Hard","domain":"Diagnostics",
     "results":{"i450-ATS":"PASS","i450-ATS+2":"PASS","i460-ATS":"PASS","i520-ATS":"FAIL"}},
    {"tc_id":"TC_DIAG_011","tc_name":"DTC_Session_Extended","domain":"Diagnostics",
     "results":{"i450-ATS":"PASS","i450-ATS+2":"PASS","i460-ATS":"PASS","i520-ATS":"PASS"}},
    {"tc_id":"TC_DIAG_030","tc_name":"UDS_WriteDataByID","domain":"Diagnostics",
     "results":{"i450-ATS":"PASS","i450-ATS+2":"PASS","i460-ATS":"PASS","i520-ATS":"PASS"}},
    {"tc_id":"TC_DIAG_060","tc_name":"NRC_Handling_0x31","domain":"Diagnostics",
     "results":{"i450-ATS":"PASS","i450-ATS+2":"PASS","i460-ATS":"PASS","i520-ATS":"PASS"}},
    {"tc_id":"TC_DIAG_075","tc_name":"SecuredAccess_Level2","domain":"Diagnostics",
     "results":{"i450-ATS":"PASS","i450-ATS+2":"PASS","i460-ATS":"PASS","i520-ATS":"PASS"}},
    {"tc_id":"TC_DCDC_019","tc_name":"VoltageRamp_12V_StepLoad","domain":"DCDC",
     "results":{"i450-ATS":"FAIL","i450-ATS+2":"FAIL","i460-ATS":"PASS","i520-ATS":"PASS"}},
    {"tc_id":"TC_DCDC_031","tc_name":"OverVoltage_Protection","domain":"DCDC",
     "results":{"i450-ATS":"PASS","i450-ATS+2":"PASS","i460-ATS":"FAIL","i520-ATS":"PASS"}},
    {"tc_id":"TC_DCDC_007","tc_name":"Efficiency_FullLoad","domain":"DCDC",
     "results":{"i450-ATS":"PASS","i450-ATS+2":"PASS","i460-ATS":"PASS","i520-ATS":"PASS"}},
    {"tc_id":"TC_DCDC_014","tc_name":"UnderVoltage_Protection","domain":"DCDC",
     "results":{"i450-ATS":"PASS","i450-ATS+2":"PASS","i460-ATS":"PASS","i520-ATS":"PASS"}},
    {"tc_id":"TC_DCDC_025","tc_name":"Thermal_Shutdown","domain":"DCDC",
     "results":{"i450-ATS":"PASS","i450-ATS+2":"PASS","i460-ATS":"PASS","i520-ATS":"PASS"}},
    {"tc_id":"TC_MEAS_007","tc_name":"CellTemp_Sensor_Ch3","domain":"Measurement",
     "results":{"i450-ATS":"FAIL","i450-ATS+2":"PASS","i460-ATS":"PASS","i520-ATS":"FAIL"}},
    {"tc_id":"TC_MEAS_025","tc_name":"HV_Isolation_Monitor","domain":"Measurement",
     "results":{"i450-ATS":"PASS","i450-ATS+2":"FAIL","i460-ATS":"PASS","i520-ATS":"PASS"}},
    {"tc_id":"TC_MEAS_003","tc_name":"CellVoltage_AllCh","domain":"Measurement",
     "results":{"i450-ATS":"PASS","i450-ATS+2":"PASS","i460-ATS":"PASS","i520-ATS":"PASS"}},
    {"tc_id":"TC_MEAS_011","tc_name":"SoC_Accuracy_C20","domain":"Measurement",
     "results":{"i450-ATS":"PASS","i450-ATS+2":"PASS","i460-ATS":"PASS","i520-ATS":"PASS"}},
    {"tc_id":"TC_MEAS_018","tc_name":"CurrentSensor_Calibration","domain":"Measurement",
     "results":{"i450-ATS":"PASS","i450-ATS+2":"PASS","i460-ATS":"PASS","i520-ATS":"PASS"}},
    {"tc_id":"TC_FLASH_001","tc_name":"ECU_Identification_PreFlash","domain":"Flashing",
     "results":{"i450-ATS":"PASS","i450-ATS+2":"PASS","i460-ATS":"PASS","i520-ATS":"PASS"}},
    {"tc_id":"TC_FLASH_002","tc_name":"Flash_Full_ECU","domain":"Flashing",
     "results":{"i450-ATS":"PASS","i450-ATS+2":"PASS","i460-ATS":"PASS","i520-ATS":"PASS"}},
    {"tc_id":"TC_FLASH_003","tc_name":"Flash_Verify_Checksum","domain":"Flashing",
     "results":{"i450-ATS":"PASS","i450-ATS+2":"PASS","i460-ATS":"PASS","i520-ATS":"PASS"}},
    {"tc_id":"TC_FLASH_004","tc_name":"Flash_Rollback","domain":"Flashing",
     "results":{"i450-ATS":"PASS","i450-ATS+2":"PASS","i460-ATS":"PASS","i520-ATS":"PASS"}},
    {"tc_id":"TC_FLASH_005","tc_name":"Flash_SBL_Download","domain":"Flashing",
     "results":{"i450-ATS":"PASS","i450-ATS+2":"PASS","i460-ATS":"PASS","i520-ATS":"PASS"}},
]

DEMO_TICKETS = [
    {"tc_id":"TC_HSI_012","jira_id":"BMS-1041","status":"IN_PROGRESS","priority":"Critical","assignee":"K. Mueller","fail_release":"i450-ATS","fix_release":None,"fix_status":None,"jira_url":"https://jira.bmw.com/browse/BMS-1041","created_at":"2026-01-10"},
    {"tc_id":"TC_HSI_031","jira_id":"BMS-1038","status":"FIX_CONFIRMED","priority":"High","assignee":"K. Mueller","fail_release":"i450-ATS","fix_release":"i460-ATS","fix_status":"FIX_CONFIRMED","jira_url":"https://jira.bmw.com/browse/BMS-1038","created_at":"2026-01-08"},
    {"tc_id":"TC_HSI_044","jira_id":"BMS-1052","status":"FIX_FAILED","priority":"High","assignee":"M. Schmidt","fail_release":"i450-ATS+2","fix_release":"i460-ATS","fix_status":"FIX_FAILED","jira_url":"https://jira.bmw.com/browse/BMS-1052","created_at":"2026-01-20"},
    {"tc_id":"TC_HSI_005","jira_id":"BMS-1055","status":"FIX_PENDING","priority":"Medium","assignee":"M. Schmidt","fail_release":"i450-ATS+2","fix_release":"i520-ATS","fix_status":"FIX_PENDING","jira_url":"https://jira.bmw.com/browse/BMS-1055","created_at":"2026-01-22"},
    {"tc_id":"TC_DIAG_041","jira_id":"BMS-1029","status":"FIX_CONFIRMED","priority":"Medium","assignee":"A. Fischer","fail_release":"i450-ATS","fix_release":"i460-ATS","fix_status":"FIX_CONFIRMED","jira_url":"https://jira.bmw.com/browse/BMS-1029","created_at":"2026-01-05"},
    {"tc_id":"TC_DIAG_087","jira_id":"BMS-1031","status":"FIX_CONFIRMED","priority":"Medium","assignee":"A. Fischer","fail_release":"i450-ATS","fix_release":"i460-ATS","fix_status":"FIX_CONFIRMED","jira_url":"https://jira.bmw.com/browse/BMS-1031","created_at":"2026-01-06"},
    {"tc_id":"TC_DIAG_056","jira_id":"BMS-1033","status":"OPEN","priority":"Low","assignee":"Unassigned","fail_release":"i450-ATS","fix_release":None,"fix_status":None,"jira_url":"https://jira.bmw.com/browse/BMS-1033","created_at":"2026-01-07"},
    {"tc_id":"TC_DIAG_072","jira_id":"BMS-1061","status":"IN_PROGRESS","priority":"High","assignee":"A. Fischer","fail_release":"i520-ATS","fix_release":None,"fix_status":None,"jira_url":"https://jira.bmw.com/browse/BMS-1061","created_at":"2026-02-01"},
    {"tc_id":"TC_DCDC_019","jira_id":"BMS-1044","status":"FIX_CONFIRMED","priority":"High","assignee":"L. Bauer","fail_release":"i450-ATS","fix_release":"i460-ATS","fix_status":"FIX_CONFIRMED","jira_url":"https://jira.bmw.com/browse/BMS-1044","created_at":"2026-01-14"},
    {"tc_id":"TC_DCDC_031","jira_id":"BMS-1049","status":"FIX_PENDING","priority":"Medium","assignee":"L. Bauer","fail_release":"i460-ATS","fix_release":"i520-ATS","fix_status":"FIX_PENDING","jira_url":"https://jira.bmw.com/browse/BMS-1049","created_at":"2026-01-18"},
    {"tc_id":"TC_MEAS_007","jira_id":"BMS-1047","status":"OPEN","priority":"Medium","assignee":"Unassigned","fail_release":"i450-ATS","fix_release":None,"fix_status":None,"jira_url":"https://jira.bmw.com/browse/BMS-1047","created_at":"2026-01-16"},
    {"tc_id":"TC_MEAS_025","jira_id":"BMS-1058","status":"FIX_FAILED","priority":"High","assignee":"M. Schmidt","fail_release":"i450-ATS+2","fix_release":"i460-ATS","fix_status":"FIX_FAILED","jira_url":"https://jira.bmw.com/browse/BMS-1058","created_at":"2026-01-28"},
]


@app.post("/api/seed-demo", summary="Load mock data for development / demo")
def seed_demo():
    with get_conn() as conn:
        for sop, release in DEMO_RELEASES:
            for tc in DEMO_TCS:
                if release in tc["results"]:
                    upsert_result(conn, {
                        "tc_id":       tc["tc_id"],
                        "tc_name":     tc["tc_name"],
                        "release":     release,
                        "sop":         sop,
                        "domain":      tc["domain"],
                        "result":      tc["results"].get(release, "INCONCLUSIVE"),
                        "report_file": None,
                    })
        for t in DEMO_TICKETS:
            upsert_ticket(conn, t)
    return {"status": "ok", "message": "Demo data loaded successfully"}


# ---------------------------------------------------------------------------
# Date coercion helper (convert date objects to strings for Pydantic)
# ---------------------------------------------------------------------------

def _coerce_ticket_dates(row: dict) -> dict:
    for k in ("created_at", "updated_at"):
        if row.get(k) is not None:
            row[k] = str(row[k])[:19]
    return row


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    port = int(os.getenv("PORT", "8000"))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=True)
