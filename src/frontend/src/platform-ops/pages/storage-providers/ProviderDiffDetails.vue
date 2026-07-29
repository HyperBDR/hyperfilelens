<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import type { ProviderDiff } from '../../../lib/storageProviderCatalogApi'

withDefaults(defineProps<{
  diffs: ProviderDiff[]
  showProviderHeader?: boolean
}>(), {
  showProviderHeader: true,
})

const { t } = useI18n()

function displayValue(value: unknown) {
  if (value === null || value === undefined || value === '') return '—'
  return typeof value === 'object' ? JSON.stringify(value) : String(value)
}
</script>

<template>
  <section class="provider-diff" aria-live="polite">
    <article
      v-for="diff in diffs"
      :key="diff.provider_id"
      class="provider-diff__provider"
      :class="{ 'provider-diff__provider--without-header': !showProviderHeader }"
    >
      <header v-if="showProviderHeader">
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
          <div class="provider-diff__change provider-diff__change--heading" aria-hidden="true">
            <span>{{ t('platformOps.storageProviders.field') }}</span>
            <span>{{ t('platformOps.storageProviders.currentValue') }}</span>
            <span></span>
            <span>{{ t('platformOps.storageProviders.importedValue') }}</span>
          </div>
          <div v-for="change in diff.provider_changes" :key="change.path" class="provider-diff__change">
            <code>{{ change.path }}</code>
            <span class="provider-diff__before">{{ displayValue(change.before) }}</span>
            <span aria-hidden="true">→</span>
            <span class="provider-diff__after">{{ displayValue(change.after) }}</span>
          </div>
        </div>
      </div>

      <div v-if="diff.added_regions.length" class="provider-diff__group provider-diff__group--added">
        <h4>{{ t('platformOps.storageProviders.addedRegions') }}</h4>
        <div v-for="region in diff.added_regions" :key="region.id" class="provider-diff__region">
          <el-tag size="small" type="success" effect="plain">+ {{ t('platformOps.storageProviders.added') }}</el-tag>
          <div><strong>{{ region.display_name }}</strong><code>{{ region.id }} · {{ region.region_group_en }}</code></div>
          <div><small>{{ t('platformOps.storageProviders.externalEndpoint') }}</small><span>{{ region.external_endpoint }}</span></div>
          <div><small>{{ t('platformOps.storageProviders.internalEndpoint') }}</small><span>{{ region.internal_endpoint }}</span></div>
        </div>
      </div>

      <div v-if="diff.removed_regions.length" class="provider-diff__group provider-diff__group--removed">
        <h4>{{ t('platformOps.storageProviders.removedRegions') }}</h4>
        <div v-for="region in diff.removed_regions" :key="region.id" class="provider-diff__region">
          <el-tag size="small" type="danger" effect="plain">− {{ t('platformOps.storageProviders.removed') }}</el-tag>
          <div><strong>{{ region.display_name }}</strong><code>{{ region.id }} · {{ region.region_group_en }}</code></div>
          <div><small>{{ t('platformOps.storageProviders.externalEndpoint') }}</small><span>{{ region.external_endpoint }}</span></div>
          <div><small>{{ t('platformOps.storageProviders.internalEndpoint') }}</small><span>{{ region.internal_endpoint }}</span></div>
        </div>
      </div>

      <div v-if="diff.modified_regions.length" class="provider-diff__group provider-diff__group--modified">
        <h4>{{ t('platformOps.storageProviders.modifiedRegions') }}</h4>
        <div v-for="region in diff.modified_regions" :key="region.region_id" class="provider-diff__modified">
          <strong>{{ region.region_id }}</strong>
          <div class="provider-diff__change provider-diff__change--heading" aria-hidden="true">
            <span>{{ t('platformOps.storageProviders.field') }}</span>
            <span>{{ t('platformOps.storageProviders.currentValue') }}</span>
            <span></span>
            <span>{{ t('platformOps.storageProviders.importedValue') }}</span>
          </div>
          <div v-for="change in region.changes" :key="change.path" class="provider-diff__change">
            <code>{{ change.path }}</code>
            <span class="provider-diff__before">{{ displayValue(change.before) }}</span>
            <span aria-hidden="true">→</span>
            <span class="provider-diff__after">{{ displayValue(change.after) }}</span>
          </div>
        </div>
      </div>

      <el-empty
        v-if="!diff.provider_changes.length && !diff.added_regions.length && !diff.removed_regions.length && !diff.modified_regions.length"
        class="provider-diff__empty"
        :description="t('platformOps.storageProviders.noChanges')"
        :image-size="32"
      />
    </article>
  </section>
</template>

<style scoped>
.provider-diff { display: grid; gap: 12px; margin-top: 14px; }
.provider-diff__provider { overflow: hidden; border: 1px solid var(--color-border-light, #e7e7ef); border-radius: 10px; background: var(--color-bg, #fff); }
.provider-diff__provider--without-header { border: 0; border-radius: 0; }
.provider-diff__provider > header { display: flex; align-items: center; justify-content: space-between; gap: 12px; padding: 12px 14px; background: var(--color-fill-light, #f7f7fa); }
.provider-diff__provider > header div { display: flex; align-items: baseline; gap: 8px; }
.provider-diff__provider > header span { color: var(--color-text-secondary, #70707e); font-size: 12px; }
.provider-diff__group { padding: 12px 14px; border-top: 1px solid var(--color-border-light, #ededf3); }
.provider-diff__provider--without-header > .provider-diff__group:first-child { border-top: 0; }
.provider-diff__group h4 { margin: 0 0 8px; font-size: 12px; }
.provider-diff__group--added, .provider-diff__group--removed, .provider-diff__group--modified { margin: 10px 12px; border: 1px solid; border-radius: 8px; }
.provider-diff__provider--without-header > .provider-diff__group--added:first-child,
.provider-diff__provider--without-header > .provider-diff__group--removed:first-child,
.provider-diff__provider--without-header > .provider-diff__group--modified:first-child { border-top: 1px solid; }
.provider-diff__group--added { border-color: color-mix(in srgb, var(--el-color-success) 28%, transparent); background: color-mix(in srgb, var(--el-color-success) 5%, #fff); }
.provider-diff__group--removed { border-color: color-mix(in srgb, var(--el-color-danger) 28%, transparent); background: color-mix(in srgb, var(--el-color-danger) 5%, #fff); }
.provider-diff__group--modified { border-color: color-mix(in srgb, var(--el-color-warning) 32%, transparent); background: color-mix(in srgb, var(--el-color-warning) 7%, #fff); }
.provider-diff__group--added h4, .provider-diff__group--removed h4, .provider-diff__group--modified h4 { display: flex; align-items: center; gap: 7px; }
.provider-diff__group--added h4::before, .provider-diff__group--removed h4::before, .provider-diff__group--modified h4::before { width: 3px; height: 14px; border-radius: 999px; content: ''; }
.provider-diff__group--added h4::before { background: var(--el-color-success); }
.provider-diff__group--removed h4::before { background: var(--el-color-danger); }
.provider-diff__group--modified h4::before { background: var(--el-color-warning); }
.provider-diff__changes, .provider-diff__modified { display: grid; gap: 6px; }
.provider-diff__change { display: grid; grid-template-columns: minmax(130px, .7fr) minmax(0, 1fr) auto minmax(0, 1fr); align-items: start; gap: 8px; font-size: 12px; }
.provider-diff__change--heading { padding-bottom: 4px; border-bottom: 1px solid var(--color-border-light, #ededf3); color: var(--color-text-secondary, #70707e); font-size: 10px; font-weight: 600; }
.provider-diff__change code, .provider-diff__region code { color: var(--color-text-secondary, #70707e); font-size: 11px; }
.provider-diff__before { color: var(--el-color-danger); overflow-wrap: anywhere; }
.provider-diff__after { color: var(--el-color-success); overflow-wrap: anywhere; }
.provider-diff__region { display: grid; grid-template-columns: auto minmax(140px, .8fr) minmax(180px, 1fr) minmax(180px, 1fr); align-items: start; gap: 10px; padding: 8px 0; font-size: 12px; }
.provider-diff__region > div { display: grid; min-width: 0; gap: 2px; }
.provider-diff__region small { color: var(--color-text-secondary, #70707e); font-size: 10px; }
.provider-diff__region span { overflow-wrap: anywhere; }
.provider-diff__modified { padding: 4px 0; }
.provider-diff__modified > strong { margin: 4px 0; font-size: 12px; }
.provider-diff__region + .provider-diff__region, .provider-diff__modified + .provider-diff__modified { border-top: 1px solid color-mix(in srgb, var(--color-border-light, #ededf3) 80%, transparent); }
.provider-diff__empty { padding: 14px; }
.provider-diff__empty :deep(.el-empty__description) { margin-top: 6px; }
.provider-diff__empty :deep(.el-empty__description p) { font-size: 12px; line-height: 18px; }
@media (max-width: 720px) { .provider-diff__change, .provider-diff__region { grid-template-columns: 1fr; } .provider-diff__change > span[aria-hidden], .provider-diff__change--heading { display: none; } }
</style>
