<script setup lang="ts">
import { useBmsStore } from '@/stores/bms'
import StatusBadge from './StatusBadge.vue'

const emit = defineEmits<{ (e: 'domain-click', domain: string): void }>()
const store = useBmsStore()

const DOMAIN_COLORS: Record<string, string> = {
  Diagnostics: 'var(--domain-diag)',
  HSI:         'var(--domain-hsi)',
  Flashing:    'var(--domain-flash)',
  DCDC:        'var(--domain-dcdc)',
  Measurement: 'var(--domain-meas)',
}
</script>

<template>
  <table class="domain-table">
    <thead>
      <tr>
        <th>Domain</th>
        <th>Pass</th>
        <th>Fail</th>
        <th>Pass Rate</th>
        <th>Open</th>
        <th>In Progress</th>
        <th>Fixed</th>
        <th>Fix Failed</th>
      </tr>
    </thead>
    <tbody>
      <tr
        v-for="s in store.domainStats"
        :key="s.domain"
        @click="emit('domain-click', s.domain)"
      >
        <td>
          <span class="domain-dot" :style="{ background: DOMAIN_COLORS[s.domain] ?? '#888' }"></span>
          {{ s.domain }}
        </td>
        <td style="color: var(--pass);">{{ s.passed }}</td>
        <td style="color: var(--fail);">{{ s.failed }}</td>
        <td>
          <span :class="['rate', s.pass_rate >= 80 ? 'rate--good' : s.pass_rate >= 50 ? 'rate--mid' : 'rate--bad']">
            {{ s.pass_rate }}%
          </span>
        </td>
        <td>
          <StatusBadge v-if="s.open_tickets" status="OPEN" />
          <span v-else style="color: var(--text-muted)">0</span>
        </td>
        <td>
          <StatusBadge v-if="s.in_progress" status="IN_PROGRESS" />
          <span v-else style="color: var(--text-muted)">0</span>
        </td>
        <td style="color: var(--pass);">{{ s.fixed }}</td>
        <td>
          <span v-if="s.fix_failed" style="color: var(--fix-failed); font-weight: 500;">{{ s.fix_failed }}</span>
          <span v-else style="color: var(--text-muted)">0</span>
        </td>
      </tr>
    </tbody>
  </table>
</template>

<style scoped>
.domain-table { width: 100%; }
.domain-dot {
  display: inline-block;
  width: 8px; height: 8px;
  border-radius: 50%;
  margin-right: 8px;
  vertical-align: middle;
}
.rate { font-weight: 500; }
.rate--good { color: var(--pass); }
.rate--mid  { color: var(--in-progress); }
.rate--bad  { color: var(--fail); }
</style>
