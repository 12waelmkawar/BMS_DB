import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import type {
  ReleaseInfo,
  TCResult,
  JiraTicket,
  DomainStats,
  DiffEntry,
  TraceabilityEntry,
} from '@/types'
import * as api from '@/api'

export const useBmsStore = defineStore('bms', () => {
  // ── State ──────────────────────────────────────────────────────────────
  const releases      = ref<ReleaseInfo[]>([])
  const selectedSop   = ref<string>('SOP2606')
  const selectedRelease = ref<string>('i450-ATS')
  const results       = ref<TCResult[]>([])
  const tickets       = ref<JiraTicket[]>([])
  const fixAlerts     = ref<JiraTicket[]>([])
  const domainStats   = ref<DomainStats[]>([])
  const traceability  = ref<TraceabilityEntry[]>([])
  const diffEntries   = ref<DiffEntry[]>([])
  const loading       = ref(false)
  const activeModal   = ref<JiraTicket | null>(null)

  // ── Computed ───────────────────────────────────────────────────────────
  const sops = computed(() => [...new Set(releases.value.map(r => r.sop))])

  const releasesForSop = computed(() =>
    releases.value.filter(r => r.sop === selectedSop.value).map(r => r.release)
  )

  const totalTCs   = computed(() => results.value.length)
  const totalPass  = computed(() => results.value.filter(r => r.result === 'PASS').length)
  const totalFail  = computed(() => results.value.filter(r => r.result === 'FAIL').length)
  const openTickets = computed(() =>
    tickets.value.filter(t => t.status === 'OPEN' || t.status === 'IN_PROGRESS').length
  )
  const fixClaims  = computed(() =>
    tickets.value.filter(t => t.fix_release != null).length
  )
  const hasFixFailed = computed(() => fixAlerts.value.length > 0)

  // ── Actions ────────────────────────────────────────────────────────────
  async function loadReleases() {
    releases.value = await api.getReleases()
    if (releases.value.length) {
      selectedSop.value = releases.value[0].sop
      selectedRelease.value = releases.value[0].release
    }
  }

  async function loadDashboard() {
    loading.value = true
    try {
      const [res, t, fa, stats] = await Promise.all([
        api.getResults(selectedSop.value, selectedRelease.value),
        api.getTickets(),
        api.getFixAlerts(),
        api.getStats(selectedSop.value, selectedRelease.value),
      ])
      results.value     = res
      tickets.value     = t
      fixAlerts.value   = fa
      domainStats.value = stats
    } finally {
      loading.value = false
    }
  }

  async function loadTraceability() {
    traceability.value = await api.getTraceability()
  }

  async function loadDiff(relA: string, relB: string) {
    diffEntries.value = await api.getDiff(selectedSop.value, relA, relB)
  }

  function selectRelease(sop: string, release: string) {
    selectedSop.value     = sop
    selectedRelease.value = release
    loadDashboard()
  }

  function openModal(ticket: JiraTicket) {
    activeModal.value = ticket
  }

  function closeModal() {
    activeModal.value = null
  }

  function ticketForTc(tcId: string): JiraTicket | undefined {
    return tickets.value.find(t => t.tc_id === tcId)
  }

  async function seedDemo() {
    await api.seedDemo()
    await loadReleases()
    await loadDashboard()
  }

  return {
    releases, selectedSop, selectedRelease, results, tickets,
    fixAlerts, domainStats, traceability, diffEntries,
    loading, activeModal,
    sops, releasesForSop, totalTCs, totalPass, totalFail,
    openTickets, fixClaims, hasFixFailed,
    loadReleases, loadDashboard, loadTraceability, loadDiff,
    selectRelease, openModal, closeModal, ticketForTc, seedDemo,
  }
})
