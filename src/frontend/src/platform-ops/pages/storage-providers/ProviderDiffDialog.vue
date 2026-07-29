<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import type { ProviderDiff, ProviderImportPreview } from '../../../lib/storageProviderCatalogApi'
import ProviderDiffDetails from './ProviderDiffDetails.vue'

const props = defineProps<{
  modelValue: boolean
  preview: ProviderImportPreview | null
}>()

const emit = defineEmits<{
  'update:modelValue': [value: boolean]
}>()

const { t } = useI18n()
const selectedProviderId = ref('')

const providers = computed(() => props.preview?.providers || [])
const selectedDiff = computed(() => (
  providers.value.find((provider) => provider.provider_id === selectedProviderId.value)
  || providers.value[0]
  || null
))

const summary = computed(() => providers.value.reduce((result, provider) => {
  result.addedRegions += provider.added_regions.length
  result.removedRegions += provider.removed_regions.length
  result.modifiedRegions += provider.modified_regions.length
  return result
}, {
  addedRegions: 0,
  removedRegions: 0,
  modifiedRegions: 0,
}))

watch(
  () => [props.modelValue, providers.value] as const,
  ([open, items]) => {
    if (!open || !items.length) return
    if (items.some((provider) => provider.provider_id === selectedProviderId.value)) return
    selectedProviderId.value = (
      items.find((provider) => provider.change_type !== 'unchanged') || items[0]
    ).provider_id
  },
  { immediate: true },
)

function changeTagType(changeType: ProviderDiff['change_type']) {
  if (changeType === 'added') return 'success'
  if (changeType === 'modified') return 'warning'
  return 'info'
}
</script>

<template>
  <el-dialog
    class="provider-diff-dialog"
    :model-value="modelValue"
    width="min(1120px, 92vw)"
    top="5vh"
    :z-index="4100"
    append-to-body
    destroy-on-close
    @update:model-value="emit('update:modelValue', $event)"
  >
    <template #header>
      <div class="provider-diff-dialog__heading">
        <h2>{{ t('platformOps.storageProviders.diffDialogTitle') }}</h2>
        <p>{{ t('platformOps.storageProviders.diffDialogDescription') }}</p>
      </div>
    </template>

    <div v-if="preview" class="provider-diff-dialog__content">
      <section class="provider-diff-dialog__summary" :aria-label="t('platformOps.storageProviders.diffSummaryLabel')">
        <div class="provider-diff-dialog__summary-card provider-diff-dialog__summary-card--added">
          <span>{{ t('platformOps.storageProviders.added') }}</span>
          <strong>{{ summary.addedRegions }}</strong>
          <small>{{ t('platformOps.storageProviders.addedRegions') }}</small>
        </div>
        <div class="provider-diff-dialog__summary-card provider-diff-dialog__summary-card--removed">
          <span>{{ t('platformOps.storageProviders.removed') }}</span>
          <strong>{{ summary.removedRegions }}</strong>
          <small>{{ t('platformOps.storageProviders.removedRegions') }}</small>
        </div>
        <div class="provider-diff-dialog__summary-card provider-diff-dialog__summary-card--modified">
          <span>{{ t('platformOps.storageProviders.modified') }}</span>
          <strong>{{ summary.modifiedRegions }}</strong>
          <small>{{ t('platformOps.storageProviders.modifiedRegions') }}</small>
        </div>
      </section>

      <el-empty
        v-if="!providers.length"
        :description="t('platformOps.storageProviders.noProvidersInDiff')"
        :image-size="64"
      />

      <div v-else class="provider-diff-dialog__workspace">
        <el-select
          v-model="selectedProviderId"
          class="provider-diff-dialog__mobile-select"
          :aria-label="t('platformOps.storageProviders.selectDiffProvider')"
        >
          <el-option
            v-for="provider in providers"
            :key="provider.provider_id"
            :label="provider.provider_id"
            :value="provider.provider_id"
          />
        </el-select>

        <nav class="provider-diff-dialog__providers" :aria-label="t('platformOps.storageProviders.selectDiffProvider')">
          <button
            v-for="provider in providers"
            :key="provider.provider_id"
            type="button"
            :class="{ 'is-active': provider.provider_id === selectedDiff?.provider_id }"
            @click="selectedProviderId = provider.provider_id"
          >
            <span>
              <strong>{{ provider.provider_id }}</strong>
              <small>{{ t(`platformOps.storageProviders.changeType.${provider.change_type}`) }}</small>
            </span>
            <el-tag size="small" :type="changeTagType(provider.change_type)" effect="plain">
              {{ provider.change_type === 'added' ? '+' : provider.change_type === 'modified' ? '~' : '=' }}
            </el-tag>
          </button>
        </nav>

        <main v-if="selectedDiff" class="provider-diff-dialog__details">
          <header class="provider-diff-dialog__details-header">
            <div>
              <h3>{{ selectedDiff.provider_id }}</h3>
              <el-tag :type="changeTagType(selectedDiff.change_type)" effect="plain">
                {{ t(`platformOps.storageProviders.changeType.${selectedDiff.change_type}`) }}
              </el-tag>
            </div>
            <el-tag v-if="selectedDiff.persistence_action" effect="plain">
              {{ t(`platformOps.storageProviders.persistenceAction.${selectedDiff.persistence_action}`) }}
            </el-tag>
          </header>

          <ProviderDiffDetails :diffs="[selectedDiff]" :show-provider-header="false" />
        </main>
      </div>
    </div>

    <template #footer>
      <el-button type="primary" @click="emit('update:modelValue', false)">
        {{ t('common.close') }}
      </el-button>
    </template>
  </el-dialog>
</template>

<style scoped>
.provider-diff-dialog__heading h2 { margin: 0; color: var(--color-text-title, #1c1c26); font-size: 18px; font-weight: 650; }
.provider-diff-dialog__heading p { margin: 5px 0 0; color: var(--color-text-secondary, #70707e); font-size: 12px; }
.provider-diff-dialog__content { display: grid; gap: 14px; }
.provider-diff-dialog__summary { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 10px; }
.provider-diff-dialog__summary-card { display: grid; gap: 3px; padding: 12px 14px; border: 1px solid var(--color-border-light, #e6e7ee); border-radius: 9px; background: var(--color-fill-light, #fafafe); }
.provider-diff-dialog__summary span { color: var(--color-text-secondary, #70707e); font-size: 11px; font-weight: 600; }
.provider-diff-dialog__summary strong { color: var(--color-text-title, #1c1c26); font-size: 22px; line-height: 1.1; }
.provider-diff-dialog__summary small { color: var(--color-text-secondary, #70707e); font-size: 11px; }
.provider-diff-dialog__summary-card--added { border-color: color-mix(in srgb, var(--el-color-success) 28%, transparent); background: color-mix(in srgb, var(--el-color-success) 5%, #fff); }
.provider-diff-dialog__summary-card--added strong { color: var(--el-color-success); }
.provider-diff-dialog__summary-card--removed { border-color: color-mix(in srgb, var(--el-color-danger) 28%, transparent); background: color-mix(in srgb, var(--el-color-danger) 5%, #fff); }
.provider-diff-dialog__summary-card--removed strong { color: var(--el-color-danger); }
.provider-diff-dialog__summary-card--modified { border-color: color-mix(in srgb, var(--el-color-warning) 32%, transparent); background: color-mix(in srgb, var(--el-color-warning) 7%, #fff); }
.provider-diff-dialog__summary-card--modified strong { color: var(--el-color-warning); }
.provider-diff-dialog__workspace { display: grid; grid-template-columns: 238px minmax(0, 1fr); min-height: 390px; max-height: calc(90vh - 310px); overflow: hidden; border: 1px solid var(--color-border-light, #e6e7ee); border-radius: 10px; }
.provider-diff-dialog__providers { overflow-y: auto; border-right: 1px solid var(--color-border-light, #e6e7ee); background: var(--color-fill-light, #fafafe); }
.provider-diff-dialog__providers button { display: grid; width: 100%; grid-template-columns: minmax(0, 1fr) auto; align-items: center; gap: 7px; padding: 12px; border: 0; border-bottom: 1px solid var(--color-border-light, #ededf3); background: transparent; color: inherit; cursor: pointer; text-align: left; }
.provider-diff-dialog__providers button:hover { background: #fff; }
.provider-diff-dialog__providers button.is-active { box-shadow: inset 3px 0 0 var(--color-primary, #6d5ef6); background: #fff; }
.provider-diff-dialog__providers button > span:first-child { display: grid; min-width: 0; gap: 2px; }
.provider-diff-dialog__providers strong { overflow: hidden; font-size: 12px; text-overflow: ellipsis; white-space: nowrap; }
.provider-diff-dialog__providers small { color: var(--color-text-secondary, #70707e); font-size: 10px; }
.provider-diff-dialog__details { min-width: 0; overflow-y: auto; padding: 16px; }
.provider-diff-dialog__details-header { display: flex; align-items: center; justify-content: space-between; gap: 12px; }
.provider-diff-dialog__details-header > div { display: flex; align-items: center; gap: 9px; min-width: 0; }
.provider-diff-dialog__details-header h3 { margin: 0; overflow: hidden; font-size: 15px; text-overflow: ellipsis; white-space: nowrap; }
.provider-diff-dialog__mobile-select { display: none; }
:global(.provider-diff-dialog .el-dialog__body) { max-height: calc(90vh - 120px); padding-top: 8px; overflow-y: auto; }
@media (max-width: 720px) {
  .provider-diff-dialog__summary { grid-template-columns: 1fr; }
  .provider-diff-dialog__workspace { display: flex; max-height: none; flex-direction: column; overflow: visible; border: 0; }
  .provider-diff-dialog__providers { display: none; }
  .provider-diff-dialog__mobile-select { display: block; width: 100%; margin-bottom: 12px; }
  .provider-diff-dialog__details { max-height: none; padding: 0; overflow: visible; }
  .provider-diff-dialog__details-header { align-items: flex-start; flex-direction: column; }
}
</style>
