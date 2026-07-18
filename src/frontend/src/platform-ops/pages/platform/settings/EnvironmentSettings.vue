<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { ElMessage } from 'element-plus'
import ModulePage from '../../../../components/ModulePage.vue'
import PlatformOpsDetailSection from '../../../components/PlatformOpsDetailSection.vue'
import PlatformOpsRefreshButton from '../../../components/PlatformOpsRefreshButton.vue'
import { usePlatformOpsSideNav } from '../../../composables/usePlatformOpsSideNav'
import { fetchPlatformEnvironment, type PlatformEnvironmentSettings } from '../../../lib/platformOpsApi'
import { apiErrorMessage } from '../../../../lib/api'

const { t } = useI18n()
const sideNav = usePlatformOpsSideNav()

const busy = ref(false)
const payload = ref<PlatformEnvironmentSettings | null>(null)

const effectiveEntries = computed(() =>
  Object.entries(payload.value?.effective || {}).map(([key, value]) => ({
    key,
    value: formatValue(value),
  })),
)

const sourceEntries = computed(() =>
  Object.entries(payload.value?.sources || {}).map(([key, value]) => ({
    key,
    value,
  })),
)

const health = computed(() => (payload.value?.health || {}) as Record<string, unknown>)

function formatValue(value: unknown): string {
  if (value === null || value === undefined) return '—'
  if (typeof value === 'boolean') return value ? t('common.yes') : t('common.no')
  if (Array.isArray(value)) return value.length ? value.join(', ') : '—'
  if (typeof value === 'object') return JSON.stringify(value)
  return String(value)
}

async function load() {
  busy.value = true
  try {
    payload.value = await fetchPlatformEnvironment()
  } catch (err) {
    payload.value = null
    ElMessage.error({ message: apiErrorMessage(err, t('platformOps.settings.loadFailed')), grouping: true })
  } finally {
    busy.value = false
  }
}

onMounted(load)
</script>

<template>
  <ModulePage :menus="sideNav" body-fill>
    <div v-loading="busy" class="platform-env">
      <div class="platform-env__toolbar">
        <PlatformOpsRefreshButton :loading="busy" @click="load" />
      </div>

      <div v-if="payload" class="hfl-detail-sections">
        <PlatformOpsDetailSection :title="t('platformOps.settings.environmentTitle')">
          <div class="hfl-detail-grid">
            <div class="hfl-detail-row">
              <span class="hfl-detail-row__label">{{ t('platformOps.settings.environment.appVersion') }}</span>
              <span class="hfl-detail-row__value hfl-detail-row__value--mono">{{ payload.app_version || '—' }}</span>
            </div>
            <div class="hfl-detail-row">
              <span class="hfl-detail-row__label">{{ t('platformOps.settings.environment.agentVersion') }}</span>
              <span class="hfl-detail-row__value hfl-detail-row__value--mono">{{ payload.agent_version || '—' }}</span>
            </div>
            <div class="hfl-detail-row">
              <span class="hfl-detail-row__label">{{ t('platformOps.settings.environment.djangoDebug') }}</span>
              <span class="hfl-detail-row__value">{{ payload.django_debug ? t('common.yes') : t('common.no') }}</span>
            </div>
          </div>
        </PlatformOpsDetailSection>

        <PlatformOpsDetailSection :title="t('platformOps.settings.environment.effectiveTitle')">
          <div v-if="effectiveEntries.length" class="hfl-detail-grid">
            <div v-for="entry in effectiveEntries" :key="entry.key" class="hfl-detail-row hfl-detail-row--full">
              <span class="hfl-detail-row__label">{{ entry.key }}</span>
              <span class="hfl-detail-row__value hfl-detail-row__value--mono hfl-detail-row__value--break">{{ entry.value }}</span>
            </div>
          </div>
          <el-empty v-else :description="t('platformOps.settings.environment.emptyEffective')" :image-size="80" />
        </PlatformOpsDetailSection>

        <PlatformOpsDetailSection :title="t('platformOps.settings.environment.sourcesTitle')">
          <div v-if="sourceEntries.length" class="hfl-detail-grid">
            <div v-for="entry in sourceEntries" :key="entry.key" class="hfl-detail-row hfl-detail-row--full">
              <span class="hfl-detail-row__label">{{ entry.key }}</span>
              <span class="hfl-detail-row__value">{{ entry.value }}</span>
            </div>
          </div>
          <el-empty v-else :description="t('platformOps.settings.environment.emptySources')" :image-size="80" />
        </PlatformOpsDetailSection>

        <PlatformOpsDetailSection :title="t('platformOps.settings.environment.healthTitle')">
          <div v-if="Object.keys(health).length" class="hfl-detail-grid">
            <div v-for="(value, key) in health" :key="key" class="hfl-detail-row hfl-detail-row--full">
              <span class="hfl-detail-row__label">{{ String(key) }}</span>
              <span class="hfl-detail-row__value hfl-detail-row__value--mono">{{ formatValue(value) }}</span>
            </div>
          </div>
          <el-empty v-else :description="t('platformOps.settings.environment.emptyHealth')" :image-size="80" />
        </PlatformOpsDetailSection>
      </div>
    </div>
  </ModulePage>
</template>
