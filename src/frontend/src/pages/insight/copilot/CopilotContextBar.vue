<script setup lang="ts">
import { computed, ref } from 'vue'
import { MessageSquare } from 'lucide-vue-next'
import { formatBytes } from '../../../lib/kopiaProgress'
import { formatLocalDateTime } from '../../../lib/dateTime'
import type { LensSessionLink } from '../../../lib/lensApi'

const props = defineProps<{
  session: LensSessionLink
}>()

const detailsOpen = ref(false)
const activeRunStatuses = new Set(['queued', 'running', 'streaming'])

const statusLabel = computed(() => {
  if (props.session.lifecycle_status === 'failed') return 'Failed'
  if (props.session.lifecycle_status === 'provisioning') return 'Preparing…'
  if (props.session.lifecycle_status === 'deleting') return 'Deleting…'
  if (activeRunStatuses.has(props.session.active_run_status || '')) return 'Answering…'
  return 'Ready'
})

const statusClass = computed(() => ({
  'is-failed': props.session.lifecycle_status === 'failed',
  'is-preparing': props.session.lifecycle_status === 'provisioning',
  'is-deleting': props.session.lifecycle_status === 'deleting',
  'is-answering': activeRunStatuses.has(props.session.active_run_status || ''),
}))

const sourceName = computed(() => props.session.backup_source_name?.trim() || 'Backup Source')
const scopes = computed(() => props.session.source_scopes_json || [])
const firstPath = computed(() => scopes.value[0]?.source_path?.trim() || 'No files selected')
const additionalPathCount = computed(() => Math.max(0, scopes.value.length - 1))
const createdShort = computed(() => {
  if (!props.session.created_at) return 'Unavailable'
  const value = new Date(props.session.created_at)
  if (Number.isNaN(value.getTime())) return 'Unavailable'
  return new Intl.DateTimeFormat('en-US', {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  }).format(value)
})
const gatewaySummary = computed(() => props.session.gateway_selection_mode === 'manual'
  ? `Private Gateway${props.session.gateway_name ? `: ${props.session.gateway_name}` : ''}`
  : 'Platform Gateway')

</script>

<template>
  <header class="copilot-context-bar">
    <div class="copilot-context-bar__top">
      <div class="copilot-context-bar__identity">
        <MessageSquare :size="16" class="copilot-context-bar__icon" aria-hidden="true" />
        <h1 :title="session.title">{{ session.title }}</h1>
        <span class="copilot-context-bar__status" :class="statusClass"><i />{{ statusLabel }}</span>
      </div>
    </div>

    <div class="copilot-context-bar__summary" :title="`${sourceName} · ${firstPath} · ${gatewaySummary} · Created ${createdShort}`">
      <span class="copilot-context-bar__source">{{ sourceName }}</span><em>·</em>
      <button type="button" class="copilot-context-bar__path" @click="detailsOpen = true">{{ firstPath }}<b v-if="additionalPathCount"> +{{ additionalPathCount }}</b></button><em>·</em>
      <span class="copilot-context-bar__gateway">{{ gatewaySummary }}</span><em>·</em>
      <span class="copilot-context-bar__created">Created {{ createdShort }}</span>
    </div>
  </header>

  <ElDialog v-model="detailsOpen" title="Chat Details" width="560px" append-to-body>
    <div class="copilot-details">
      <section>
        <h3>Data Source</h3>
        <dl><dt>Backup Source</dt><dd>{{ sourceName }}</dd></dl>
        <dl><dt>Snapshot</dt><dd>{{ session.snapshot_created_at ? formatLocalDateTime(session.snapshot_created_at) : '—' }}</dd></dl>
        <dl><dt>Snapshot Size</dt><dd>{{ session.snapshot_size_bytes != null ? formatBytes(session.snapshot_size_bytes) : '—' }}</dd></dl>
      </section>
      <section>
        <h3>Files and Folders</h3>
        <ol><li v-for="(scope, index) in scopes" :key="`${scope.backup_snapshot_directory_id}-${index}`">{{ scope.source_path }}</li></ol>
      </section>
      <section>
        <h3>Data Privacy</h3>
        <dl><dt>Gateway Type</dt><dd>{{ session.gateway_selection_mode === 'manual' ? 'Private Gateway' : 'Platform Gateway' }}</dd></dl>
        <dl v-if="session.gateway_selection_mode === 'manual'"><dt>Gateway</dt><dd>{{ session.gateway_name || '—' }}</dd></dl>
      </section>
    </div>
  </ElDialog>
</template>

<style scoped>
.copilot-context-bar { display: flex; min-width: 0; flex-direction: column; gap: 5px; padding: 9px 18px 10px; border-bottom: 1px solid var(--color-border-light); background: var(--color-card-bg); }
.copilot-context-bar__top { display: flex; min-width: 0; align-items: center; justify-content: space-between; gap: 12px; }
.copilot-context-bar__identity { display: flex; min-width: 0; align-items: center; gap: 8px; }
.copilot-context-bar__icon { flex-shrink: 0; color: var(--color-primary); }
.copilot-context-bar__identity h1 { min-width: 0; overflow: hidden; margin: 0; color: var(--color-text-title); font-size: 14px; font-weight: 650; line-height: 20px; text-overflow: ellipsis; white-space: nowrap; }
.copilot-context-bar__status { display: inline-flex; min-height: 20px; flex-shrink: 0; align-items: center; gap: 5px; padding: 1px 7px; border: 1px solid #abefc6; border-radius: 999px; background: #ecfdf3; color: #027a48; font-size: 11px; font-weight: 600; line-height: 16px; }
.copilot-context-bar__status i { width: 6px; height: 6px; flex: 0 0 6px; border-radius: 999px; background: currentColor; }
.copilot-context-bar__status.is-preparing { border-color: #d9d2ff; background: #f2f0ff; color: #654cf0; }
.copilot-context-bar__status.is-deleting { border-color: var(--color-border-light); background: var(--color-grey-3); color: var(--color-text-tertiary); }
.copilot-context-bar__status.is-answering { border-color: #b2ccff; background: #eef4ff; color: #165dff; }
.copilot-context-bar__status.is-answering i,.copilot-context-bar__status.is-preparing i { animation: copilot-status-pulse 1.4s ease-in-out infinite; }
.copilot-context-bar__status.is-failed { border-color: #fecdca; background: #fef3f2; color: #d92d20; }
.copilot-context-bar__summary { display: flex; min-width: 0; align-items: center; gap: 6px; overflow: hidden; color: var(--color-text-tertiary); font-size: 12px; line-height: 18px; white-space: nowrap; }
.copilot-context-bar__summary > span { overflow: hidden; text-overflow: ellipsis; }
.copilot-context-bar__summary em { flex-shrink: 0; color: var(--color-text-disabled); font-style: normal; }
.copilot-context-bar__source { max-width: 18%; flex: 0 1 auto; color: var(--color-text-secondary); }
.copilot-context-bar__path { min-width: 60px; max-width: 42%; flex: 0 1 auto; overflow: hidden; padding: 0; border: 0; background: transparent; color: var(--color-text-secondary); font: inherit; text-align: left; text-overflow: ellipsis; white-space: nowrap; cursor: pointer; }
.copilot-context-bar__path:hover { color: var(--color-primary); }
.copilot-context-bar__path b { font-weight: 600; }
.copilot-context-bar__gateway,.copilot-context-bar__created { flex: 0 0 auto; }
.copilot-details { display: grid; gap: 20px; }
.copilot-details section + section { padding-top: 18px; border-top: 1px solid var(--color-border-light); }
.copilot-details h3 { margin: 0 0 12px; color: var(--color-text-tertiary); font-size: 11px; font-weight: 600; }
.copilot-details dl { display: grid; grid-template-columns: 130px minmax(0, 1fr); gap: 14px; margin: 0 0 10px; }
.copilot-details dt { color: var(--color-text-tertiary); font-size: 12px; }
.copilot-details dd { overflow-wrap: anywhere; margin: 0; color: var(--color-text-title); font-size: 13px; font-weight: 500; }
.copilot-details ol { display: grid; gap: 8px; margin: 0; padding-left: 30px; }
.copilot-details li { padding-left: 4px; overflow-wrap: anywhere; color: var(--color-text-secondary); font-family: var(--font-mono); font-size: 12px; }
@keyframes copilot-status-pulse { 50% { opacity: .58; } }
@media (max-width: 760px) { .copilot-context-bar__source { max-width: 24%; }.copilot-context-bar__gateway { max-width: 24%; }.copilot-context-bar__created { display: none; } }
</style>
