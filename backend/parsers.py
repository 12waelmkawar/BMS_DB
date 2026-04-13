"""
parsers.py — Parse ECU-Test report files (.trf XML, .html, .xls/.xlsx)
and extract metadata from network-drive folder paths.
"""

import re
from pathlib import Path
from typing import Generator

from lxml import etree
from bs4 import BeautifulSoup
import openpyxl

# ---------------------------------------------------------------------------
# Domain normalisation
# ---------------------------------------------------------------------------

DOMAIN_MAP: dict[str, str] = {
    "diagnostics": "Diagnostics",
    "diagnostic":  "Diagnostics",
    "hsi":         "HSI",
    "flash":       "Flashing",
    "flashing":    "Flashing",
    "dcdc":        "DCDC",
    "dc_dc":       "DCDC",
    "measurement": "Measurement",
    "measure":     "Measurement",
}


def _normalise_domain(raw: str) -> str:
    key = raw.lower().replace("_results", "").replace("-", "_").strip("_")
    for k, v in DOMAIN_MAP.items():
        if k in key:
            return v
    return raw.title()


def _normalise_result(raw: str) -> str:
    raw = raw.strip().upper()
    if raw in ("PASSED", "PASS"):
        return "PASS"
    if raw in ("FAILED", "FAIL", "ERROR"):
        return "FAIL"
    return "INCONCLUSIVE"


# ---------------------------------------------------------------------------
# Path metadata extraction
# ---------------------------------------------------------------------------

def extract_path_metadata(path: Path) -> dict | None:
    """
    Extract sop, release, and domain from a network-drive path.

    Expected structure (relative to the xchange root):
        <SOP>/<release>/<domain_folder>/report.trf

    Example:
        \\NETWORK\\xchange\\SOP2606\\i450-ATS\\HSI_Results\\report.trf
        → sop="SOP2606", release="i450-ATS", domain="HSI"
    """
    parts = path.parts
    # Find the SOP folder (starts with "SOP")
    sop_idx = next(
        (i for i, p in enumerate(parts) if re.match(r"SOP\d+", p, re.I)), None
    )
    if sop_idx is None:
        return None
    try:
        sop     = parts[sop_idx]
        release = parts[sop_idx + 1]
        domain  = _normalise_domain(parts[sop_idx + 2])
    except IndexError:
        return None
    return {"sop": sop, "release": release, "domain": domain}


# ---------------------------------------------------------------------------
# TRF parser (.trf — ECU-Test XML)
# ---------------------------------------------------------------------------

def parse_trf(path: Path) -> Generator[dict, None, None]:
    """
    Parse an ECU-Test .trf XML file and yield one dict per test case:
    {tc_id, tc_name, result, report_file}
    """
    meta = extract_path_metadata(path) or {}
    try:
        tree = etree.parse(str(path))
    except etree.XMLSyntaxError:
        return

    # ECU-Test TRF: <TestCase name="TC_HSI_012" id="TC_HSI_012" result="PASSED">
    for tc_elem in tree.iter("TestCase"):
        tc_id   = tc_elem.get("id") or tc_elem.get("name", "UNKNOWN")
        tc_name = tc_elem.get("name", tc_id)
        result  = _normalise_result(tc_elem.get("result", "INCONCLUSIVE"))
        yield {
            "tc_id":       tc_id,
            "tc_name":     tc_name,
            "result":      result,
            "report_file": str(path),
            **meta,
        }


# ---------------------------------------------------------------------------
# HTML parser (.html — ECU-Test HTML report)
# ---------------------------------------------------------------------------

def parse_html(path: Path) -> Generator[dict, None, None]:
    """
    Parse an ECU-Test HTML report.  Rows have class "passed"/"failed"/"inconclusive".
    First cell = TC name / ID.
    """
    meta = extract_path_metadata(path) or {}
    try:
        soup = BeautifulSoup(path.read_text(encoding="utf-8", errors="replace"), "lxml")
    except Exception:
        return

    for row in soup.find_all("tr", class_=re.compile(r"passed|failed|inconclusive", re.I)):
        cells = row.find_all("td")
        if not cells:
            continue
        tc_name = cells[0].get_text(strip=True)
        tc_id   = tc_name  # ECU-Test HTML uses name as ID
        # Derive result from row class
        cls = " ".join(row.get("class", []))
        if "passed" in cls.lower():
            result = "PASS"
        elif "failed" in cls.lower():
            result = "FAIL"
        else:
            result = "INCONCLUSIVE"
        yield {
            "tc_id":       tc_id,
            "tc_name":     tc_name,
            "result":      result,
            "report_file": str(path),
            **meta,
        }


# ---------------------------------------------------------------------------
# XLS/XLSX parser (.xls / .xlsx — ECU-Test spreadsheet export)
# ---------------------------------------------------------------------------

_NAME_COLS  = {"name", "testcase", "test case", "tc"}
_RESULT_COLS = {"result", "verdict", "status"}


def parse_xlsx(path: Path) -> Generator[dict, None, None]:
    """
    Parse an ECU-Test .xlsx report.
    First row = headers; look for name/testcase and result/verdict columns.
    """
    meta = extract_path_metadata(path) or {}
    try:
        wb = openpyxl.load_workbook(str(path), read_only=True, data_only=True)
    except Exception:
        return

    ws = wb.active
    rows = list(ws.iter_rows(values_only=True))
    if not rows:
        return

    # Find header row (first row containing recognised column names)
    header_idx = None
    name_col = result_col = None
    for idx, row in enumerate(rows):
        lower_row = [str(c).lower().strip() if c else "" for c in row]
        for col_i, cell_val in enumerate(lower_row):
            if cell_val in _NAME_COLS and name_col is None:
                name_col = col_i
            if cell_val in _RESULT_COLS and result_col is None:
                result_col = col_i
        if name_col is not None and result_col is not None:
            header_idx = idx
            break

    if header_idx is None:
        wb.close()
        return

    for row in rows[header_idx + 1:]:
        if row[name_col] is None:
            continue
        tc_name = str(row[name_col]).strip()
        raw_res = str(row[result_col]).strip() if row[result_col] else "INCONCLUSIVE"
        yield {
            "tc_id":       tc_name,
            "tc_name":     tc_name,
            "result":      _normalise_result(raw_res),
            "report_file": str(path),
            **meta,
        }
    wb.close()


# ---------------------------------------------------------------------------
# Dispatcher
# ---------------------------------------------------------------------------

def parse_report(path: Path) -> Generator[dict, None, None]:
    """Dispatch to the correct parser based on file extension."""
    ext = path.suffix.lower()
    if ext == ".trf":
        yield from parse_trf(path)
    elif ext in (".html", ".htm"):
        yield from parse_html(path)
    elif ext in (".xlsx", ".xls"):
        yield from parse_xlsx(path)
