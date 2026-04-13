<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { use } from 'echarts/core'
import { BarChart, PieChart } from 'echarts/charts'
import { GridComponent, TooltipComponent, LegendComponent } from 'echarts/components'
import { useBmsStore } from '@/stores/bms'
import KpiCard from '@/components/KpiCard.vue'
import DomainTable from '@/components/DomainTable.vue'
import StatusBadge from '@/components/StatusBadge.vue'
import JiraBadge from '@/components/JiraBadge.vue'
import AlertBanner from '@/components/AlertBanner.vue'
import TicketModal from '@/components/TicketModal.vue'

use([BarChart, PieChart, GridComponent, TooltipComponent, LegendComponent])

const store = useBmsStore()
const activeTab = ref<'overview' | 'traceability' | 'drilldown' | 'diff' | 'tickets'>('overview')
const drillDomain = ref<string>('HSI')
const diffRelA = ref<string>('')
const diffRelB = ref<string>('')

const DOMAINS = ['Diagnostics', 'HSI', 'Flashing', 'DCDC', 'Measurement']
const DOMAIN_COLORS: Record<string, string> = {
  Diagnostics: '#00d4ff',
  HSI:         '#ff6b35',
  Flashing:    '#00ff94',
  DCDC:        '#ffd700',
  Measurement: '#c084fc',
}

// ── Lifecycle ─────────────────────────────────────────────────────────────
onMounted(async () => {
  await store.loadReleases()
  await store.loadDashboard()
  if (store.releasesForSop.length >= 2) {
    diffRelA.value = store.releasesForSop[0]
    diffRelB.value = store.releasesForSop[1]
  }
})

watch(activeTab, async (tab) => {
  if (tab === 'traceability') await store.loadTraceability()
  if (tab === 'diff' && diffRelA.value && diffRelB.value) {
    await store.loadDiff(diffRelA.value, diffRelB.value)
  }
})

// ── Bar chart: pass/fail per domain ──────────────────────────────────────
const barOption = computed(() => ({
  backgroundColor: 'transparent',
  tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
  legend: { data: ['Pass', 'Fail'], textStyle: { color: '#e0e8f0', fontFamily: 'DM Mono' } },
  grid: { left: 16, right: 16, bottom: 8, top: 36, containLabel: true },
  xAxis: {
    type: 'category',
    data: store.domainStats.map(d => d.domain),
    axisLabel: { color: '#445566', fontFamily: 'DM Mono', fontSize: 11 },
    axisLine: { lineStyle: { color: '#1a2d45' } },
  },
  yAxis: {
    type: 'value',
    axisLabel: { color: '#445566', fontFamily: 'DM Mono', fontSize: 11 },
    splitLine: { lineStyle: { color: '#1a2d45' } },
  },
  series: [
    { name: 'Pass', type: 'bar', stack: 'total', data: store.domainStats.map(d => d.passed),      itemStyle: { color: '#00ff94' } },
    { name: 'Fail', type: 'bar', stack: 'total', data: store.domainStats.map(d => d.failed),       itemStyle: { color: '#ff4444' } },
  ],
}))

// ── Donut chart: overall pass rate ───────────────────────────────────────
const donutOption = computed(() => ({
  backgroundColor: 'transparent',
  tooltip: { trigger: 'item' },
  series: [{
    type: 'pie', radius: ['55%', '80%'],
    label: {
      show: true, position: 'center',
      formatter: () => `${store.totalTCs ? Math.round(store.totalPass / store.totalTCs * 100) : 0}%`,
      fontSize: 28, fontFamily: 'Syne', fontWeight: '700', color: '#e0e8f0',
    },
    data: [
      { value: store.totalPass, name: 'Pass', itemStyle: { color: '#00ff94' } },
      { value: store.totalFail, name: 'Fail', itemStyle: { color: '#ff4444' } },
    ],
  }],
}))

// ── Cross-release bar chart ───────────────────────────────────────────────
const releaseBarOption = computed(() => {
  const rels = store.releasesForSop
  return {
    backgroundColor: 'transparent',
    tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
    grid: { left: 16, right: 16, bottom: 8, top: 12, containLabel: true },
    xAxis: {
      type: 'category', data: rels,
      axisLabel: { color: '#445566', fontFamily: 'DM Mono', fontSize: 11, rotate: 15 },
      axisLine: { lineStyle: { color: '#1a2d45' } },
    },
    yAxis: {
      type: 'value', max: 100,
      axisLabel: { color: '#445566', fontFamily: 'DM Mono', fontSize: 11, formatter: '{value}%' },
      splitLine: { lineStyle: { color: '#1a2d45' } },
    },
    series: [{
      type: 'bar',
      data: rels.map(() => 0), // placeholder — computed per release via store
      itemStyle: { color: '#00d4ff' },
    }],
  }
})

// ── Drilldown filtered TCs ────────────────────────────────────────────────
const drilledTCs = computed(() =>
  store.results.filter(r => r.domain === drillDomain.value)
)

// ── Traceability grouped by domain ───────────────────────────────────────
const traceByDomain = computed(() => {
  const map: Record<string, typeof store.traceability> = {}
  for (const e of store.traceability) {
    if (!map[e.domain]) map[e.domain] = []
    map[e.domain].push(e)
  }
  return map
})

// ── Diff ──────────────────────────────────────────────────────────────────
async function runDiff() {
  if (diffRelA.value && diffRelB.value) await store.loadDiff(diffRelA.value, diffRelB.value)
}

const regressions = computed(() => store.diffEntries.filter(d => d.change_type === 'REGRESSION').length)
const fixes       = computed(() => store.diffEntries.filter(d => d.change_type === 'FIXED').length)

// ── Helpers ───────────────────────────────────────────────────────────────
function allReleases(): string[] {
  return store.releases.filter(r => r.sop === store.selectedSop).map(r => r.release)
}

function resultClass(result?: string): string {
  if (result === 'PASS')  return 'res-pass'
  if (result === 'FAIL')  return 'res-fail'
  return 'res-inc'
}
</script>

<template>
  <div class="dashboard">
    <!-- Ticket modal (global) -->
    <TicketModal />

    <!-- ── Header ─────────────────────────────────────────────────────── -->
    <header class="header">
      <div class="header-left">
        <span class="logo">BMS<span class="logo-accent"> TEST INTELLIGENCE</span></span>
        <span class="live-dot"></span><span class="live-label">LIVE</span>
      </div>
      <div class="header-right">
        <!-- Release pills -->
        <span
          v-for="rel in store.releasesForSop"
          :key="rel"
          :class="['release-pill', rel === store.selectedRelease ? 'release-pill--active' : '',
                   store.fixAlerts.some(a => a.fix_release === rel) ? 'release-pill--alert' : '']"
          @click="store.selectRelease(store.selectedSop, rel)"
        >
          <span v-if="store.fixAlerts.some(a => a.fix_release === rel)" class="pill-dot"></span>
          {{ rel }}
        </span>
      </div>
    </header>

    <!-- ── SOP selector ───────────────────────────────────────────────── -->
    <div class="sop-bar">
      <span
        v-for="sop in store.sops"
        :key="sop"
        :class="['sop-btn', sop === store.selectedSop ? 'sop-btn--active' : '']"
        @click="store.selectRelease(sop, store.releases.find(r => r.sop === sop)?.release ?? '')"
      >{{ sop }}</span>
      <span class="spacer" />
      <button class="seed-btn" @click="store.seedDemo()">⚡ Load Demo Data</button>
    </div>

    <!-- ── Tab bar ────────────────────────────────────────────────────── -->
    <nav class="tabs">
      <button v-for="t in (['overview','traceability','drilldown','diff','tickets'] as const)"
        :key="t"
        :class="['tab', activeTab === t ? 'tab--active' : '']"
        @click="activeTab = t"
      >
        {{ { overview:'Overview', traceability:'Traceability', drilldown:'TC Drill-Down', diff:'Release Diff', tickets:'All Tickets' }[t] }}
      </button>
    </nav>

    <!-- ── Main content ───────────────────────────────────────────────── -->
    <main class="content fade-in" :key="activeTab">

      <!-- ═══ OVERVIEW ══════════════════════════════════════════════════ -->
      <template v-if="activeTab === 'overview'">
        <AlertBanner />

        <!-- KPI cards -->
        <div class="kpi-row">
          <KpiCard label="Total TCs"    :value="store.totalTCs"    accent="var(--pending)"  />
          <KpiCard label="Passed"        :value="store.totalPass"   accent="var(--pass)"     />
          <KpiCard label="Failed"        :value="store.totalFail"   accent="var(--fail)"     />
          <KpiCard label="Open Tickets"  :value="store.openTickets" accent="var(--in-progress)" />
          <KpiCard label="Fix Claims"    :value="store.fixClaims"   accent="var(--domain-meas)" />
        </div>

        <!-- Charts row -->
        <div class="chart-row">
          <div class="card chart-card">
            <div class="card-title">Pass / Fail by Domain</div>
            <v-chart :option="barOption" autoresize style="height:220px;" />
          </div>
          <div class="card chart-card chart-card--small">
            <div class="card-title">Overall Pass Rate</div>
            <v-chart :option="donutOption" autoresize style="height:220px;" />
          </div>
        </div>

        <!-- Domain table -->
        <div class="card">
          <div class="card-title">Domain Summary</div>
          <DomainTable @domain-click="(d) => { drillDomain = d; activeTab = 'drilldown' }" />
        </div>

        <!-- Cross-release bar chart -->
        <div class="card chart-card">
          <div class="card-title">Pass Rate by Release</div>
          <v-chart :option="releaseBarOption" autoresize style="height:180px;" />
        </div>

        <!-- Fix claims panel -->
        <div class="card" v-if="store.tickets.some(t => t.fix_release)">
          <div class="card-title">Fix Claims for {{ store.selectedRelease }}</div>
          <table>
            <thead><tr><th>TC</th><th>Jira</th><th>Claimed Fix</th><th>Fix Status</th></tr></thead>
            <tbody>
              <tr v-for="t in store.tickets.filter(t => t.fix_release)" :key="t.tc_id" @click="store.openModal(t)">
                <td class="mono">{{ t.tc_id }}</td>
                <td><JiraBadge :tc-id="t.tc_id" :ticket="t" /></td>
                <td>{{ t.fix_release }}</td>
                <td><StatusBadge :status="t.fix_status ?? 'FIX_PENDING'" /></td>
              </tr>
            </tbody>
          </table>
        </div>
      </template>

      <!-- ═══ TRACEABILITY ══════════════════════════════════════════════ -->
      <template v-else-if="activeTab === 'traceability'">
        <AlertBanner />
        <div v-for="(entries, domain) in traceByDomain" :key="domain" class="card">
          <div class="card-title" :style="{ color: DOMAIN_COLORS[domain] ?? 'inherit' }">{{ domain }}</div>
          <table>
            <thead>
              <tr>
                <th>TC ID</th>
                <th v-for="rel in allReleases()" :key="rel">{{ rel }}</th>
                <th>Jira</th>
                <th>Fix Status</th>
                <th>Fix Release</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="e in entries" :key="e.tc_id" @click="e.jira_id ? store.openModal(store.ticketForTc(e.tc_id)!) : null">
                <td class="mono">{{ e.tc_id }}<br><span style="color:var(--text-muted);font-size:10px">{{ e.tc_name }}</span></td>
                <td v-for="rel in allReleases()" :key="rel">
                  <span :class="['res-cell', resultClass(e.result_per_release[rel])]">
                    {{ e.result_per_release[rel] ?? '—' }}
                  </span>
                  <div v-if="e.fix_release === rel" style="font-size:9px;margin-top:2px;">
                    <span v-if="e.fix_status === 'FIX_CONFIRMED'" style="color:var(--pass)">fix ✓</span>
                    <span v-else-if="e.fix_status === 'FIX_FAILED'" style="color:var(--fix-failed)">fix ✗</span>
                  </div>
                </td>
                <td><JiraBadge :tc-id="e.tc_id" /></td>
                <td><StatusBadge v-if="e.fix_status" :status="e.fix_status" /></td>
                <td>{{ e.fix_release ?? '—' }}</td>
              </tr>
            </tbody>
          </table>
        </div>
        <div v-if="!store.traceability.length" class="empty">No failing TCs found.</div>
      </template>

      <!-- ═══ TC DRILL-DOWN ════════════════════════════════════════════ -->
      <template v-else-if="activeTab === 'drilldown'">
        <div class="domain-pills">
          <span
            v-for="d in DOMAINS" :key="d"
            :class="['domain-pill', drillDomain === d ? 'domain-pill--active' : '']"
            :style="drillDomain === d ? { borderColor: DOMAIN_COLORS[d], color: DOMAIN_COLORS[d] } : {}"
            @click="drillDomain = d"
          >{{ d }}</span>
        </div>

        <div class="card">
          <div class="card-title">{{ drillDomain }} — {{ store.selectedRelease }}</div>
          <table>
            <thead><tr><th>TC ID / Name</th><th>Result</th><th>Jira</th></tr></thead>
            <tbody>
              <tr v-for="tc in drilledTCs" :key="tc.tc_id" @click="store.ticketForTc(tc.tc_id) ? store.openModal(store.ticketForTc(tc.tc_id)!) : null">
                <td class="mono">
                  {{ tc.tc_id }}<br>
                  <span style="color:var(--text-muted);font-size:10px">{{ tc.tc_name }}</span>
                </td>
                <td><StatusBadge :status="tc.result" /></td>
                <td>
                  <JiraBadge v-if="tc.result === 'FAIL'" :tc-id="tc.tc_id" />
                </td>
              </tr>
            </tbody>
          </table>
          <div v-if="!drilledTCs.length" class="empty">No TCs for this domain in selected release.</div>
        </div>
      </template>

      <!-- ═══ RELEASE DIFF ════════════════════════════════════════════ -->
      <template v-else-if="activeTab === 'diff'">
        <div class="card diff-controls">
          <div class="diff-select-row">
            <div class="field-group">
              <label>Base Release</label>
              <select v-model="diffRelA" @change="runDiff">
                <option v-for="r in allReleases()" :key="r" :value="r">{{ r }}</option>
              </select>
            </div>
            <span class="diff-arrow">→</span>
            <div class="field-group">
              <label>Target Release</label>
              <select v-model="diffRelB" @change="runDiff">
                <option v-for="r in allReleases()" :key="r" :value="r">{{ r }}</option>
              </select>
            </div>
          </div>
        </div>

        <!-- Summary -->
        <div class="kpi-row">
          <KpiCard label="Total Changes" :value="store.diffEntries.length" accent="var(--pending)" />
          <KpiCard label="Regressions"   :value="regressions" accent="var(--fail)" />
          <KpiCard label="Fixes"         :value="fixes"        accent="var(--pass)" />
        </div>

        <div class="card">
          <table>
            <thead><tr><th>TC ID</th><th>Domain</th><th>Base</th><th>Target</th><th>Change</th><th>Jira</th></tr></thead>
            <tbody>
              <tr
                v-for="d in store.diffEntries" :key="d.tc_id"
                :class="['diff-row', d.change_type === 'REGRESSION' ? 'diff-row--reg' : d.change_type === 'FIXED' ? 'diff-row--fix' : '']"
                @click="store.ticketForTc(d.tc_id) ? store.openModal(store.ticketForTc(d.tc_id)!) : null"
              >
                <td class="mono">{{ d.tc_id }}</td>
                <td>{{ d.domain }}</td>
                <td><StatusBadge :status="d.result_a ?? 'INCONCLUSIVE'" /></td>
                <td><StatusBadge :status="d.result_b ?? 'INCONCLUSIVE'" /></td>
                <td>
                  <span :class="['change-label', d.change_type === 'REGRESSION' ? 'change-label--reg' : 'change-label--fix']">
                    {{ d.change_type }}
                  </span>
                </td>
                <td><JiraBadge :tc-id="d.tc_id" /></td>
              </tr>
            </tbody>
          </table>
          <div v-if="!store.diffEntries.length" class="empty">No differences found between selected releases.</div>
        </div>
      </template>

      <!-- ═══ ALL TICKETS ═════════════════════════════════════════════ -->
      <template v-else-if="activeTab === 'tickets'">
        <!-- Summary cards -->
        <div class="kpi-row">
          <KpiCard label="Fix Failed"    :value="store.tickets.filter(t => t.fix_status === 'FIX_FAILED').length"    accent="var(--fix-failed)" />
          <KpiCard label="Open"          :value="store.tickets.filter(t => t.status === 'OPEN').length"               accent="var(--fail)" />
          <KpiCard label="In Progress"   :value="store.tickets.filter(t => t.status === 'IN_PROGRESS').length"        accent="var(--in-progress)" />
          <KpiCard label="Fix Pending"   :value="store.tickets.filter(t => t.fix_status === 'FIX_PENDING').length"    accent="var(--pending)" />
          <KpiCard label="Fix Confirmed" :value="store.tickets.filter(t => t.fix_status === 'FIX_CONFIRMED').length"  accent="var(--pass)" />
        </div>

        <div class="card">
          <table>
            <thead>
              <tr>
                <th>Ticket</th><th>TC ID</th><th>Priority</th><th>Assignee</th>
                <th>Failed In</th><th>Fix Release</th><th>Status</th><th></th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="t in store.tickets" :key="t.tc_id"
                :class="['ticket-row', t.fix_status === 'FIX_FAILED' ? 'ticket-row--alert' : '']"
                @click="store.openModal(t)"
              >
                <td style="color: var(--pending);">{{ t.jira_id }}</td>
                <td class="mono">{{ t.tc_id }}</td>
                <td>{{ t.priority ?? '—' }}</td>
                <td>{{ t.assignee ?? '—' }}</td>
                <td>{{ t.fail_release ?? '—' }}</td>
                <td>{{ t.fix_release ?? '—' }}</td>
                <td><StatusBadge :status="t.fix_status ?? t.status" /></td>
                <td style="color:var(--text-muted)">›</td>
              </tr>
            </tbody>
          </table>
          <div v-if="!store.tickets.length" class="empty">No tickets found.</div>
        </div>
      </template>

    </main>
  </div>
</template>

<style scoped>
/* ── Layout ────────────────────────────────────────────────────────────── */
.dashboard {
  min-height: 100vh;
  display: flex;
  flex-direction: column;
  background: var(--bg-primary);
}

/* ── Header ────────────────────────────────────────────────────────────── */
.header {
  display: flex; align-items: center; justify-content: space-between;
  padding: 14px 24px;
  border-bottom: 1px solid var(--border);
  gap: 16px;
  flex-wrap: wrap;
}
.header-left { display: flex; align-items: center; gap: 12px; }
.logo {
  font-family: 'Syne', sans-serif;
  font-size: 18px;
  font-weight: 800;
  letter-spacing: 0.04em;
}
.logo-accent { color: var(--pending); }
.live-dot {
  width: 7px; height: 7px; border-radius: 50%;
  background: var(--pass);
  animation: pulse 1.4s ease-in-out infinite;
}
.live-label { font-size: 10px; color: var(--text-muted); letter-spacing: 0.1em; }

.header-right { display: flex; gap: 8px; flex-wrap: wrap; }
.release-pill {
  padding: 4px 12px;
  border: 1px solid var(--border);
  border-radius: 20px;
  font-size: 12px;
  cursor: pointer;
  transition: all 0.15s;
  display: flex; align-items: center; gap: 6px;
}
.release-pill:hover { border-color: var(--pending); color: var(--pending); }
.release-pill--active { border-color: var(--pending); color: var(--pending); background: rgba(0,212,255,0.08); }
.release-pill--alert { border-color: var(--fix-failed) !important; animation: pulse 1.2s ease-in-out infinite; }
.pill-dot { width: 6px; height: 6px; border-radius: 50%; background: var(--fix-failed); }

/* ── SOP bar ───────────────────────────────────────────────────────────── */
.sop-bar {
  display: flex; align-items: center; gap: 8px;
  padding: 8px 24px;
  border-bottom: 1px solid var(--border);
}
.sop-btn {
  padding: 3px 12px; border-radius: 4px;
  font-size: 11px; cursor: pointer;
  border: 1px solid var(--border);
  color: var(--text-muted);
  transition: all 0.15s;
}
.sop-btn:hover { color: var(--text-primary); border-color: var(--text-muted); }
.sop-btn--active { border-color: var(--domain-dcdc); color: var(--domain-dcdc); }
.spacer { flex: 1; }
.seed-btn {
  padding: 4px 14px; font-size: 11px; font-family: 'DM Mono', monospace;
  border: 1px solid var(--border); border-radius: 4px;
  background: transparent; color: var(--text-muted); cursor: pointer;
  transition: all 0.15s;
}
.seed-btn:hover { border-color: var(--pass); color: var(--pass); }

/* ── Tabs ──────────────────────────────────────────────────────────────── */
.tabs {
  display: flex; gap: 0;
  border-bottom: 1px solid var(--border);
  padding: 0 24px;
}
.tab {
  padding: 10px 18px; font-size: 12px; font-family: 'DM Mono', monospace;
  background: none; border: none; color: var(--text-muted);
  cursor: pointer; border-bottom: 2px solid transparent;
  transition: all 0.15s; margin-bottom: -1px;
}
.tab:hover { color: var(--text-primary); }
.tab--active { color: var(--pending); border-bottom-color: var(--pending); }

/* ── Content ───────────────────────────────────────────────────────────── */
.content {
  flex: 1;
  padding: 20px 24px;
  display: flex; flex-direction: column; gap: 16px;
  overflow-y: auto;
}

/* ── Cards ─────────────────────────────────────────────────────────────── */
.card {
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 16px;
}
.card-title {
  font-family: 'Syne', sans-serif;
  font-size: 13px; font-weight: 700;
  margin-bottom: 14px;
  color: var(--text-primary);
}

/* ── KPI row ───────────────────────────────────────────────────────────── */
.kpi-row {
  display: grid;
  grid-template-columns: repeat(5, 1fr);
  gap: 12px;
}
@media (max-width: 900px) {
  .kpi-row { grid-template-columns: repeat(3, 1fr); }
}

/* ── Charts ────────────────────────────────────────────────────────────── */
.chart-row {
  display: grid;
  grid-template-columns: 1fr 280px;
  gap: 12px;
}
.chart-card { display: flex; flex-direction: column; }
.chart-card--small { }

/* ── Result cell ───────────────────────────────────────────────────────── */
.res-cell {
  display: inline-block; padding: 1px 6px;
  border-radius: 3px; font-size: 10px;
}
.res-pass { background: rgba(0,255,148,0.12); color: var(--pass); }
.res-fail { background: rgba(255,68,68,0.12);  color: var(--fail); }
.res-inc  { background: rgba(255,215,0,0.12);  color: var(--inconclusive); }

/* ── Diff rows ─────────────────────────────────────────────────────────── */
.diff-row--reg { border-left: 3px solid var(--fail); }
.diff-row--fix { border-left: 3px solid var(--pass); }
.change-label { font-size: 10px; font-weight: 500; padding: 2px 6px; border-radius: 3px; }
.change-label--reg { background: rgba(255,68,68,0.15); color: var(--fail); }
.change-label--fix { background: rgba(0,255,148,0.12); color: var(--pass); }

/* ── Diff controls ─────────────────────────────────────────────────────── */
.diff-controls { padding: 14px 16px; }
.diff-select-row { display: flex; align-items: center; gap: 16px; }
.field-group { display: flex; flex-direction: column; gap: 4px; }
.field-group label { font-size: 10px; color: var(--text-muted); text-transform: uppercase; letter-spacing: 0.08em; }
.field-group select {
  background: var(--bg-primary); color: var(--text-primary);
  border: 1px solid var(--border); border-radius: 4px;
  padding: 6px 10px; font-family: 'DM Mono', monospace; font-size: 12px;
}
.diff-arrow { font-size: 20px; color: var(--text-muted); }

/* ── Domain pills ──────────────────────────────────────────────────────── */
.domain-pills { display: flex; gap: 8px; flex-wrap: wrap; }
.domain-pill {
  padding: 5px 14px; border-radius: 20px;
  font-size: 12px; cursor: pointer;
  border: 1px solid var(--border); color: var(--text-muted);
  transition: all 0.15s;
}
.domain-pill:hover { color: var(--text-primary); border-color: var(--text-muted); }
.domain-pill--active { border-width: 1.5px; font-weight: 500; }

/* ── Ticket rows ───────────────────────────────────────────────────────── */
.ticket-row--alert { background: rgba(255,32,32,0.05); }

/* ── Misc ──────────────────────────────────────────────────────────────── */
.mono { font-family: 'DM Mono', monospace; }
.empty { color: var(--text-muted); font-size: 12px; padding: 16px 0; text-align: center; }
</style>
