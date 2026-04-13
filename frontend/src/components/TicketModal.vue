<script setup lang="ts">
import { useBmsStore } from '@/stores/bms'
import StatusBadge from './StatusBadge.vue'

const store = useBmsStore()

const STATUS_MSG: Record<string, string> = {
  FIX_FAILED:    '🚨 Claimed fixed — TC still FAILING in fix release',
  FIX_CONFIRMED: '✅ TC passing in fix release — verified by watcher',
  FIX_PENDING:   '🔵 Awaiting test run in fix release',
  IN_PROGRESS:   '🔍 Under investigation — no fix version set yet',
  OPEN:          '🔴 Failure detected — ticket open',
}
</script>

<template>
  <Teleport to="body">
    <div v-if="store.activeModal" class="modal-backdrop" @click.self="store.closeModal()">
      <div class="modal fade-in">
        <!-- Header -->
        <div class="modal-header">
          <div>
            <span class="modal-jira-id">{{ store.activeModal.jira_id }}</span>
            <span class="modal-tc-id">{{ store.activeModal.tc_id }}</span>
          </div>
          <button class="modal-close" @click="store.closeModal()">✕</button>
        </div>

        <!-- Status banner -->
        <div :class="['status-banner', `status-banner--${(store.activeModal.fix_status ?? store.activeModal.status).toLowerCase().replace('_','-')}`]">
          {{ STATUS_MSG[store.activeModal.fix_status ?? store.activeModal.status] ?? store.activeModal.status }}
        </div>

        <!-- Field grid -->
        <div class="field-grid">
          <div class="field"><span class="field-label">Priority</span><span>{{ store.activeModal.priority ?? '—' }}</span></div>
          <div class="field"><span class="field-label">Assignee</span><span>{{ store.activeModal.assignee ?? '—' }}</span></div>
          <div class="field"><span class="field-label">Created</span><span>{{ store.activeModal.created_at?.slice(0,10) ?? '—' }}</span></div>
          <div class="field"><span class="field-label">Fail Release</span><span>{{ store.activeModal.fail_release ?? '—' }}</span></div>
          <div class="field"><span class="field-label">Fix Release</span><span>{{ store.activeModal.fix_release ?? '—' }}</span></div>
          <div class="field"><span class="field-label">Fix Status</span>
            <StatusBadge v-if="store.activeModal.fix_status" :status="store.activeModal.fix_status" />
            <span v-else>—</span>
          </div>
        </div>

        <!-- Watcher validation -->
        <div class="section-title">Watcher Validation</div>
        <div class="watcher-info">
          <template v-if="store.activeModal.fix_release">
            TC <strong>{{ store.activeModal.tc_id }}</strong> in
            <strong>{{ store.activeModal.fix_release }}</strong>:
            <StatusBadge :status="store.activeModal.fix_status ?? 'FIX_PENDING'" />
          </template>
          <template v-else>No fix release specified yet.</template>
        </div>

        <!-- Open in Jira -->
        <div class="modal-footer">
          <a v-if="store.activeModal.jira_url" :href="store.activeModal.jira_url" target="_blank" class="btn-jira">
            Open in Jira ↗
          </a>
        </div>
      </div>
    </div>
  </Teleport>
</template>

<style scoped>
.modal-backdrop {
  position: fixed; inset: 0;
  background: rgba(0,0,0,0.7);
  display: flex; align-items: center; justify-content: center;
  z-index: 9999;
}
.modal {
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: 10px;
  width: 540px;
  max-width: 95vw;
  padding: 24px;
  display: flex;
  flex-direction: column;
  gap: 16px;
}
.modal-header {
  display: flex; align-items: flex-start; justify-content: space-between;
}
.modal-jira-id {
  font-family: 'Syne', sans-serif;
  font-size: 18px;
  color: var(--pending);
  margin-right: 10px;
}
.modal-tc-id { color: var(--text-muted); font-size: 13px; }
.modal-close { background: none; border: none; color: var(--text-muted); font-size: 16px; cursor: pointer; }
.modal-close:hover { color: var(--text-primary); }

.status-banner {
  padding: 10px 14px;
  border-radius: 6px;
  font-size: 12px;
}
.status-banner--fix-failed    { background: rgba(255,32,32,0.15); border-left: 3px solid var(--fix-failed); }
.status-banner--fix-confirmed { background: rgba(0,255,148,0.1);  border-left: 3px solid var(--pass); }
.status-banner--fix-pending   { background: rgba(0,212,255,0.1);  border-left: 3px solid var(--pending); }
.status-banner--in-progress   { background: rgba(255,215,0,0.1);  border-left: 3px solid var(--in-progress); }
.status-banner--open          { background: rgba(255,68,68,0.1);   border-left: 3px solid var(--fail); }

.field-grid {
  display: grid; grid-template-columns: 1fr 1fr;
  gap: 10px;
}
.field { display: flex; flex-direction: column; gap: 3px; }
.field-label { font-size: 10px; color: var(--text-muted); text-transform: uppercase; letter-spacing: 0.08em; }

.section-title {
  font-size: 11px;
  color: var(--text-muted);
  text-transform: uppercase;
  letter-spacing: 0.1em;
  border-top: 1px solid var(--border);
  padding-top: 12px;
}
.watcher-info { font-size: 13px; display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.modal-footer { display: flex; justify-content: flex-end; }
.btn-jira {
  display: inline-block;
  padding: 8px 18px;
  background: rgba(0,212,255,0.1);
  color: var(--pending);
  border: 1px solid var(--pending);
  border-radius: 6px;
  text-decoration: none;
  font-size: 12px;
  transition: background 0.15s;
}
.btn-jira:hover { background: rgba(0,212,255,0.25); }
</style>
