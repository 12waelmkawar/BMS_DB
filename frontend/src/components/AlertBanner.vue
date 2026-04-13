<script setup lang="ts">
import { useBmsStore } from '@/stores/bms'
const store = useBmsStore()
</script>

<template>
  <div v-if="store.hasFixFailed" class="alert-banner fade-in">
    <span class="pulse-dot"></span>
    <strong>🚨 FIX_FAILED ALERT</strong>
    <span v-for="t in store.fixAlerts" :key="t.tc_id" class="alert-item" @click="store.openModal(t)">
      {{ t.tc_id }} ({{ t.jira_id }})
    </span>
  </div>
</template>

<style scoped>
.alert-banner {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
  background: rgba(255, 32, 32, 0.12);
  border: 1px solid var(--fix-failed);
  border-radius: 8px;
  padding: 10px 16px;
  font-size: 12px;
  color: var(--fix-failed);
  margin-bottom: 16px;
}
.pulse-dot {
  width: 8px; height: 8px;
  border-radius: 50%;
  background: var(--fix-failed);
  animation: pulse 1.2s ease-in-out infinite;
  flex-shrink: 0;
}
.alert-item {
  background: rgba(255,32,32,0.15);
  padding: 2px 8px;
  border-radius: 4px;
  cursor: pointer;
}
.alert-item:hover { background: rgba(255,32,32,0.3); }
</style>
