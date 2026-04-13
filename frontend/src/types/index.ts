// TypeScript interfaces for BMS Test Intelligence

export interface ReleaseInfo {
  sop: string
  release: string
}

export interface TCResult {
  id?: number
  tc_id: string
  tc_name?: string
  release: string
  sop: string
  domain: string
  result: 'PASS' | 'FAIL' | 'INCONCLUSIVE'
  report_file?: string
  parsed_at?: string
}

export interface JiraTicket {
  tc_id: string
  jira_id: string
  status: 'OPEN' | 'IN_PROGRESS' | 'FIX_PENDING' | 'FIX_CONFIRMED' | 'FIX_FAILED'
  priority?: string
  assignee?: string
  fail_release?: string
  fix_release?: string
  fix_status?: 'FIX_PENDING' | 'FIX_CONFIRMED' | 'FIX_FAILED' | null
  jira_url?: string
  created_at?: string
  updated_at?: string
}

export interface DomainStats {
  domain: string
  total: number
  passed: number
  failed: number
  inconclusive: number
  pass_rate: number
  open_tickets: number
  in_progress: number
  fixed: number
  fix_failed: number
}

export interface DiffEntry {
  tc_id: string
  tc_name?: string
  domain: string
  result_a?: string
  result_b?: string
  change_type: 'REGRESSION' | 'FIXED' | 'UNCHANGED' | 'NEW'
  jira_id?: string
  jira_url?: string
  fix_status?: string
}

export interface TraceabilityEntry {
  tc_id: string
  tc_name?: string
  domain: string
  sop: string
  fail_release: string
  result_per_release: Record<string, string>
  jira_id?: string
  jira_url?: string
  status?: string
  fix_release?: string
  fix_status?: string
  priority?: string
  assignee?: string
}
