<script setup lang="ts">
defineProps<{ status: string }>()

const LABELS: Record<string, string> = {
  PASS:          'PASS',
  FAIL:          'FAIL',
  INCONCLUSIVE:  'INC',
  OPEN:          'OPEN',
  IN_PROGRESS:   'IN PROGRESS',
  FIX_PENDING:   'FIX PENDING',
  FIX_CONFIRMED: 'FIX CONFIRMED',
  FIX_FAILED:    'FIX FAILED',
}
</script>

<template>
  <span :class="['badge', `badge--${status.toLowerCase().replace('_', '-')}`]">
    {{ LABELS[status] ?? status }}
  </span>
</template>

<style scoped>
.badge {
  display: inline-block;
  padding: 2px 8px;
  border-radius: 4px;
  font-size: 10px;
  font-weight: 500;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  white-space: nowrap;
}
.badge--pass          { background: rgba(0,255,148,0.15); color: var(--pass); }
.badge--fail          { background: rgba(255,68,68,0.15);  color: var(--fail); }
.badge--inconclusive,
.badge--inc           { background: rgba(255,215,0,0.15);  color: var(--inconclusive); }
.badge--open          { background: rgba(255,68,68,0.12);  color: #ff6060; }
.badge--in-progress   { background: rgba(255,215,0,0.12);  color: var(--in-progress); }
.badge--fix-pending   { background: rgba(0,212,255,0.12);  color: var(--pending); }
.badge--fix-confirmed { background: rgba(0,255,148,0.12);  color: var(--pass); }
.badge--fix-failed    { background: rgba(255,32,32,0.2);   color: var(--fix-failed); border: 1px solid var(--fix-failed); }
</style>
