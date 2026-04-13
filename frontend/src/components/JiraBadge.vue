<script setup lang="ts">
import { useBmsStore } from '@/stores/bms'
import type { JiraTicket } from '@/types'

const props = defineProps<{
  tcId: string
  ticket?: JiraTicket
}>()

const store = useBmsStore()

function open() {
  const t = props.ticket ?? store.ticketForTc(props.tcId)
  if (t) store.openModal(t)
}
</script>

<template>
  <span v-if="ticket || store.ticketForTc(tcId)" class="jira-badge" @click.stop="open">
    {{ (ticket ?? store.ticketForTc(tcId))?.jira_id }}
  </span>
  <span v-else class="no-ticket">⚠ No ticket</span>
</template>

<style scoped>
.jira-badge {
  display: inline-block;
  padding: 2px 8px;
  border-radius: 4px;
  background: rgba(0,212,255,0.1);
  color: var(--pending);
  font-size: 11px;
  cursor: pointer;
  transition: background 0.15s;
  white-space: nowrap;
}
.jira-badge:hover { background: rgba(0,212,255,0.25); }
.no-ticket {
  color: #ff9800;
  font-size: 11px;
  opacity: 0.85;
}
</style>
