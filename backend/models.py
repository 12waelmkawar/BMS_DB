"""
models.py — Pydantic v2 request / response models for FastAPI.
"""

from typing import Optional
from pydantic import BaseModel


class TCResult(BaseModel):
    id: Optional[int] = None
    tc_id: str
    tc_name: Optional[str] = None
    release: str
    sop: str
    domain: str
    result: str  # PASS | FAIL | INCONCLUSIVE
    report_file: Optional[str] = None
    parsed_at: Optional[str] = None


class JiraTicket(BaseModel):
    tc_id: str
    jira_id: str
    status: str  # OPEN | IN_PROGRESS | FIX_PENDING | FIX_CONFIRMED | FIX_FAILED
    priority: Optional[str] = None
    assignee: Optional[str] = None
    fail_release: Optional[str] = None
    fix_release: Optional[str] = None
    fix_status: Optional[str] = None
    jira_url: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class ReleaseInfo(BaseModel):
    sop: str
    release: str


class DomainStats(BaseModel):
    domain: str
    total: int
    passed: int
    failed: int
    inconclusive: int
    pass_rate: float
    open_tickets: int
    in_progress: int
    fixed: int
    fix_failed: int


class DiffEntry(BaseModel):
    tc_id: str
    tc_name: Optional[str] = None
    domain: str
    result_a: Optional[str] = None
    result_b: Optional[str] = None
    change_type: str  # REGRESSION | FIXED | UNCHANGED | NEW
    jira_id: Optional[str] = None
    jira_url: Optional[str] = None
    fix_status: Optional[str] = None


class TraceabilityEntry(BaseModel):
    tc_id: str
    tc_name: Optional[str] = None
    domain: str
    sop: str
    fail_release: str
    result_per_release: dict
    jira_id: Optional[str] = None
    jira_url: Optional[str] = None
    status: Optional[str] = None
    fix_release: Optional[str] = None
    fix_status: Optional[str] = None
    priority: Optional[str] = None
    assignee: Optional[str] = None
