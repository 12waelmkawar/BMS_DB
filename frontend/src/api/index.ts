import axios from 'axios'
import type {
  ReleaseInfo,
  TCResult,
  JiraTicket,
  DomainStats,
  DiffEntry,
  TraceabilityEntry,
} from '@/types'

const api = axios.create({ baseURL: '/api' })

export const getReleases = (): Promise<ReleaseInfo[]> =>
  api.get<ReleaseInfo[]>('/releases').then(r => r.data)

export const getResults = (sop: string, release: string): Promise<TCResult[]> =>
  api.get<TCResult[]>(`/results/${sop}/${release}`).then(r => r.data)

export const getTickets = (): Promise<JiraTicket[]> =>
  api.get<JiraTicket[]>('/tickets').then(r => r.data)

export const getTicket = (tcId: string): Promise<JiraTicket> =>
  api.get<JiraTicket>(`/tickets/${tcId}`).then(r => r.data)

export const getFixAlerts = (): Promise<JiraTicket[]> =>
  api.get<JiraTicket[]>('/fix-alerts').then(r => r.data)

export const getStats = (sop: string, release: string): Promise<DomainStats[]> =>
  api.get<DomainStats[]>(`/stats/${sop}/${release}`).then(r => r.data)

export const getTraceability = (): Promise<TraceabilityEntry[]> =>
  api.get<TraceabilityEntry[]>('/traceability').then(r => r.data)

export const getDiff = (sop: string, relA: string, relB: string): Promise<DiffEntry[]> =>
  api.get<DiffEntry[]>(`/diff/${sop}/${relA}/${relB}`).then(r => r.data)

export const seedDemo = (): Promise<void> =>
  api.post('/seed-demo').then(r => r.data)
