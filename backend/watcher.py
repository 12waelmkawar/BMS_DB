"""
watcher.py — Background service that:
  1. Watches the network drive for new/modified report files.
  2. Polls Jira for tickets and writes them to the DB.
  3. Validates fix claims every time new results land.

Run standalone:  python watcher.py
Or imported by main.py and started in a background thread.
"""

import os
import re
import logging
import threading
import time
from pathlib import Path

import schedule
from dotenv import load_dotenv
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler, FileCreatedEvent, FileModifiedEvent

from database import get_conn, upsert_result, upsert_ticket, validate_fix, revalidate_fix_claims
from parsers import parse_report

load_dotenv()

JIRA_URL     = os.getenv("JIRA_URL", "")
JIRA_USER    = os.getenv("JIRA_USER", "")
JIRA_TOKEN   = os.getenv("JIRA_TOKEN", "")
JIRA_PROJECT = os.getenv("JIRA_PROJECT", "BMS")
DRIVE_PATH   = Path(os.getenv("NETWORK_DRIVE_PATH", r"\\NETWORK\xchange"))

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("watcher")

# ---------------------------------------------------------------------------
# Label parsing helpers
# ---------------------------------------------------------------------------

_LABEL_PATTERNS = {
    "sop":         re.compile(r"BMS-(SOP\d+)", re.I),
    "fail_release": re.compile(r"REL-([^\s,]+)", re.I),
    "domain":      re.compile(r"DOM-([^\s,]+)", re.I),
    "tc_id":       re.compile(r"TC-([^\s,]+)", re.I),
    "fix_release": re.compile(r"FIXREL-([^\s,]+)", re.I),
}


def _parse_labels(labels: list[str]) -> dict:
    label_str = " ".join(labels)
    return {k: (m.group(1) if (m := p.search(label_str)) else None)
            for k, p in _LABEL_PATTERNS.items()}


# ---------------------------------------------------------------------------
# Jira polling
# ---------------------------------------------------------------------------

def poll_jira() -> None:
    if not JIRA_URL or not JIRA_TOKEN:
        log.warning("Jira credentials not configured — skipping poll.")
        return
    try:
        from jira import JIRA
        jira = JIRA(server=JIRA_URL, basic_auth=(JIRA_USER, JIRA_TOKEN))
        issues = jira.search_issues(
            f'project={JIRA_PROJECT} AND labels in ("BMS-SOP2606","BMS-SOP2611")',
            maxResults=500,
            fields="summary,status,priority,assignee,labels,created,resolutiondate",
        )
        with get_conn() as conn:
            for issue in issues:
                f      = issue.fields
                labels = [str(lbl) for lbl in (f.labels or [])]
                parsed = _parse_labels(labels)
                if not parsed.get("tc_id"):
                    continue  # skip tickets not linked to a TC

                # Map Jira status to our internal status
                jira_status = f.status.name.lower()
                if "done" in jira_status or "closed" in jira_status or "resolved" in jira_status:
                    internal_status = "FIX_PENDING"
                elif "progress" in jira_status:
                    internal_status = "IN_PROGRESS"
                else:
                    internal_status = "OPEN"

                fix_release = parsed.get("fix_release")
                fix_status  = None
                if fix_release and parsed.get("tc_id") and parsed.get("sop"):
                    fix_status = validate_fix(conn, parsed["tc_id"], fix_release, parsed["sop"])
                    internal_status = fix_status  # overrides status once fix claimed

                row = {
                    "tc_id":        parsed["tc_id"],
                    "jira_id":      issue.key,
                    "status":       internal_status,
                    "priority":     f.priority.name if f.priority else None,
                    "assignee":     f.assignee.displayName if f.assignee else "Unassigned",
                    "fail_release": parsed.get("fail_release"),
                    "fix_release":  fix_release,
                    "fix_status":   fix_status,
                    "jira_url":     f"{JIRA_URL}/browse/{issue.key}",
                    "created_at":   str(f.created)[:19] if f.created else None,
                }
                upsert_ticket(conn, row)
        log.info("Jira poll complete.")
    except Exception as exc:
        log.error("Jira poll failed: %s", exc)


# ---------------------------------------------------------------------------
# Network-drive scanner
# ---------------------------------------------------------------------------

REPORT_EXTENSIONS = {".trf", ".html", ".htm", ".xlsx", ".xls"}


def _store_report(path: Path) -> None:
    if path.suffix.lower() not in REPORT_EXTENSIONS:
        return
    records = list(parse_report(path))
    if not records:
        return
    with get_conn() as conn:
        for rec in records:
            if not rec.get("sop") or not rec.get("release"):
                continue
            upsert_result(conn, {
                "tc_id":       rec["tc_id"],
                "tc_name":     rec.get("tc_name"),
                "release":     rec["release"],
                "sop":         rec["sop"],
                "domain":      rec["domain"],
                "result":      rec["result"],
                "report_file": rec.get("report_file"),
            })
        # Re-validate fix claims for this release
        sop     = records[0].get("sop", "")
        release = records[0].get("release", "")
        if sop and release:
            revalidate_fix_claims(conn, release, sop)
    log.info("Stored %d records from %s", len(records), path.name)


def scan_xchange() -> None:
    """Walk the network drive and (re-)parse all report files."""
    if not DRIVE_PATH.exists():
        log.warning("Network drive not accessible: %s", DRIVE_PATH)
        return
    log.info("Scanning %s …", DRIVE_PATH)
    for p in DRIVE_PATH.rglob("*"):
        if p.is_file() and p.suffix.lower() in REPORT_EXTENSIONS:
            _store_report(p)
    log.info("Scan complete.")


# ---------------------------------------------------------------------------
# Watchdog file-system observer
# ---------------------------------------------------------------------------

class _ReportHandler(FileSystemEventHandler):
    def on_created(self, event):
        if not event.is_directory:
            _store_report(Path(event.src_path))

    def on_modified(self, event):
        if not event.is_directory:
            _store_report(Path(event.src_path))


def setup_file_watcher() -> Observer | None:
    if not DRIVE_PATH.exists():
        log.warning("Watchdog not started — drive path inaccessible: %s", DRIVE_PATH)
        return None
    observer = Observer()
    observer.schedule(_ReportHandler(), str(DRIVE_PATH), recursive=True)
    observer.start()
    log.info("Watchdog observing %s", DRIVE_PATH)
    return observer


# ---------------------------------------------------------------------------
# Scheduler + main loop
# ---------------------------------------------------------------------------

def run_scheduler() -> None:
    schedule.every(5).minutes.do(poll_jira)
    schedule.every(30).minutes.do(scan_xchange)

    # Initial run
    scan_xchange()
    poll_jira()

    observer = setup_file_watcher()
    try:
        while True:
            schedule.run_pending()
            time.sleep(10)
    finally:
        if observer:
            observer.stop()
            observer.join()


def start_background() -> threading.Thread:
    """Start the watcher in a daemon thread (called from main.py)."""
    t = threading.Thread(target=run_scheduler, daemon=True, name="bms-watcher")
    t.start()
    return t


if __name__ == "__main__":
    run_scheduler()
