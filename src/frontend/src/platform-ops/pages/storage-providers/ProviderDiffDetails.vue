<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import type { ProviderDiff } from '../../../lib/storageProviderCatalogApi'

defineProps<{ diffs: ProviderDiff[] }>()

const { t } = useI18n()

function displayValue(value: unknown) {
  if (value === null || value === undefined || value === '') return '—'
  return typeof value === 'object' ? JSON.stringify(value) : String(value)
}
</script>

<template>
  <section class="provider-diff" aria-live="polite">
    <article v-for="diff in diffs" :key="diff.provider_id" class="provider-diff__provider">
      <header>
        <div>
          <strong>{{ diff.provider_id }}</strong>
          <span>{{ t(`platformOps.storageProviders.changeType.${diff.change_type}`) }}</span>
        </div>
        <el-tag v-if="diff.persistence_action" effect="plain">
          {{ t(`platformOps.storageProviders.persistenceAction.${diff.persistence_action}`) }}
        </el-tag>
      </header>

      <div v-if="diff.provider_changes.length" class="provider-diff__group">
        <h4>{{ t('platformOps.storageProviders.providerFieldChanges') }}</h4>
        <div class="provider-diff__changes">
          <div v-for="change in diff.provider_changes" :key="change.path" class="provider-diff__change">
            <code>{{ change.path }}</code>
            <span class="provider-diff__before">{{ displayValue(change.before) }}</span>
            <span aria-hidden="true">→</span>
            <span class="provider-diff__after">{{ displayValue(change.after) }}</span>
          </div>
        </div>
      </div>

      <div v-if="diff.added_regions.length" class="provider-diff__group">
        <h4>{{ t('platformOps.storageProviders.addedRegions') }}</h4>
        <div v-for="region in diff.added_regions" :key="region.id" class="provider-diff__region">
          <strong>{{ region.display_name }}</strong>
          <code>{{ region.id }} · {{ region.region_group_en }}</code>
          <span>{{ region.external_endpoint }}</span>
          <span>{{ region.internal_endpoint }}</span>
        </div>
      </div>

      <div v-if="diff.removed_regions.length" class="provider-diff__group provider-diff__group--risk">
        <h4>{{ t('platformOps.storageProviders.removedRegions') }}</h4>
        <div v-for="region in diff.removed_regions" :key="region.id" class="provider-diff__region">
          <strong>{{ region.display_name }}</strong>
          <code>{{ region.id }} · {{ region.region_group_en }}</code>
          <span>{{ region.external_endpoint }}</span>
          <span>{{ region.internal_endpoint }}</span>
        </div>
      </div>

      <div v-if="diff.modified_regions.length" class="provider-diff__group">
        <h4>{{ t('platformOps.storageProviders.modifiedRegions') }}</h4>
        <div v-for="region in diff.modified_regions" :key="region.region_id" class="provider-diff__modified">
          <strong>{{ region.region_id }}</strong>
          <div v-for="change in region.changes" :key="change.path" class="provider-diff__change">
            <code>{{ change.path }}</code>
            <span class="provider-diff__before">{{ displayValue(change.before) }}</span>
            <span aria-hidden="true">→</span>
            <span class="provider-diff__after">{{ displayValue(change.after) }}</span>
          </div>
        </div>
      </div>

      <div v-if="diff.high_risk_changes.length" class="provider-diff__risks">
        <strong>{{ t('platformOps.storageProviders.highRiskChanges') }}</strong>
        <el-tag v-for="risk in diff.high_risk_changes" :key="risk.id" type="danger" effect="plain">
          {{ risk.type }} · {{ risk.path }}
        </el-tag>
      </div>

      <el-empty
        v-if="!diff.provider_changes.length && !diff.added_regions.length && !diff.removed_regions.length && !diff.modified_regions.length"
        :description="t('platformOps.storageProviders.noChanges')"
        :image-size="44"
      />
    </article>
  </section>
</template>

<style scoped>
.provider-diff { display: grid; gap: 12px; margin-top: 14px; }
.provider-diff__provider { overflow: hidden; border: 1px solid var(--color-border-light, #e7e7ef); border-radius: 10px; background: var(--color-bg, #fff); }
.provider-diff__provider > header { display: flex; align-items: center; justify-content: space-between; gap: 12px; padding: 12px 14px; background: var(--color-fill-light, #f7f7fa); }
.provider-diff__provider > header div { display: flex; align-items: baseline; gap: 8px; }
.provider-diff__provider > header span { color: var(--color-text-secondary, #70707e); font-size: 12px; }
.provider-diff__group { padding: 12px 14px; border-top: 1px solid var(--color-border-light, #ededf3); }
.provider-diff__group--risk { background: color-mix(in srgb, var(--el-color-danger) 5%, transparent); }
.provider-diff__group h4 { margin: 0 0 8px; font-size: 12px; }
.provider-diff__changes, .provider-diff__modified { display: grid; gap: 6px; }
.provider-diff__change { display: grid; grid-template-columns: minmax(130px, .7fr) minmax(0, 1fr) auto minmax(0, 1fr); align-items: start; gap: 8px; font-size: 12px; }
.provider-diff__change code, .provider-diff__region code { color: var(--color-text-secondary, #70707e); font-size: 11px; }
.provider-diff__before { color: var(--el-color-danger); overflow-wrap: anywhere; }
.provider-diff__after { color: var(--el-color-success); overflow-wrap: anywhere; }
.provider-diff__region { display: grid; grid-template-columns: minmax(160px, .8fr) minmax(160px, .8fr) minmax(240px, 1.4fr); gap: 8px; padding: 5px 0; font-size: 12px; }
.provider-diff__region span { overflow-wrap: anywhere; }
.provider-diff__modified > strong { margin: 4px 0; font-size: 12px; }
.provider-diff__risks { display: flex; flex-wrap: wrap; align-items: center; gap: 7px; padding: 12px 14px; border-top: 1px solid var(--color-border-light, #ededf3); }
.provider-diff__risks > strong { margin-right: 4px; font-size: 12px; }
@media (max-width: 720px) { .provider-diff__change, .provider-diff__region { grid-template-columns: 1fr; } .provider-diff__change > span[aria-hidden] { display: none; } }
</style>
