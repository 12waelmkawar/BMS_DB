<script setup lang="ts">
defineProps<{
  label: string
  value: number | string
  accent?: string
  subtitle?: string
}>()
</script>

<template>
  <div class="kpi-card" :style="{ '--accent': accent ?? 'var(--pending)' }">
    <div class="kpi-label">{{ label }}</div>
    <div class="kpi-value">{{ value }}</div>
    <div v-if="subtitle" class="kpi-subtitle">{{ subtitle }}</div>
  </div>
</template>

<style scoped>
.kpi-card {
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-top: 2px solid var(--accent);
  border-radius: 8px;
  padding: 16px 20px;
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.kpi-label {
  font-size: 10px;
  color: var(--text-muted);
  text-transform: uppercase;
  letter-spacing: 0.1em;
}
.kpi-value {
  font-family: 'Syne', sans-serif;
  font-size: 32px;
  font-weight: 700;
  color: var(--text-primary);
  line-height: 1;
}
.kpi-subtitle {
  font-size: 11px;
  color: var(--text-muted);
}
</style>
