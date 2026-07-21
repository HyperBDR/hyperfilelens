<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { ElMessage } from 'element-plus'
import { RefreshCw } from 'lucide-vue-next'
import ModulePage from '../../../components/ModulePage.vue'
import HflPagination from '../../../components/HflPagination.vue'
import { usePlatformOpsSideNav } from '../../composables/usePlatformOpsSideNav'
import { fetchAgentReleases } from '../../lib/platformOpsApi'
import { PLATFORM_OPS_LIST_TABLE_MAX_HEIGHT, PLATFORM_OPS_TABLE_HEADER_STYLE } from '../../lib/tableUi'
import { apiErrorMessage } from '../../../lib/api'

const { t } = useI18n()
const sideNav = usePlatformOpsSideNav()

type ArtifactKind = 'binary' | 'bootstrap' | 'enroll' | 'other'
type ArtifactRow = { version: string; name: string; kind: ArtifactKind; size_bytes: number }
type BootstrapInfo = {
  active_source: 'published' | 'fallback'
  active_path: string
  fallback_path: string
  version: string
}

const busy = ref(false)
const pinnedVersion = ref<string | null>(null)
const latestVersion = ref<string | null>(null)
const root = ref('')
const bootstrap = ref<BootstrapInfo | null>(null)
const rows = ref<ArtifactRow[]>([])
const currentPage = ref(1)
const pageSize = ref(20)
const totalCount = ref(0)

const bootstrapSourceLabel = computed(() => {
  if (!bootstrap.value) return ''
  return bootstrap.value.active_source === 'published'
    ? t('platformOps.platform.bootstrapSourcePublished', { version: bootstrap.value.version })
    : t('platformOps.platform.bootstrapSourceFallback')
})

function formatBytes(n: number) {
  if (!n) return '—'
  if (n < 1024) return `${n} B`
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`
  return `${(n / (1024 * 1024)).toFixed(1)} MB`
}

function kindLabel(kind: ArtifactKind) {
  return t(`platformOps.platform.kind${kind.charAt(0).toUpperCase()}${kind.slice(1)}`)
}

async function load() {
  busy.value = true
  try {
    const data = await fetchAgentReleases({
      page: currentPage.value,
      page_size: pageSize.value,
    })
    pinnedVersion.value = (data.pinned_version as string | null) ?? null
    latestVersion.value = (data.latest_version as string | null) ?? null
    root.value = String(data.root || '')
    bootstrap.value = (data.bootstrap as BootstrapInfo | undefined) ?? null
    rows.value = (data.results as ArtifactRow[]) || []
    totalCount.value = data.count ?? 0
  } catch (err) {
    pinnedVersion.value = null
    latestVersion.value = null
    root.value = ''
    bootstrap.value = null
    rows.value = []
    totalCount.value = 0
    ElMessage.error({ message: apiErrorMessage(err, t('platformOps.platform.loadFailed')), grouping: true })
  } finally {
    busy.value = false
  }
}

onMounted(load)
watch([currentPage, pageSize], load)
</script>

<template>
  <ModulePage :menus="sideNav" body-fill>
    <div class="hfl-list-shell hfl-list-shell--fill">
      <div class="hfl-list-panel hfl-list-panel--fill">
        <div class="hfl-list-toolbar">
          <div class="hfl-list-toolbar__right hfl-list-toolbar__right--solo">
            <el-button
              class="hfl-refresh-button"
              :title="t('common.refresh')"
              :aria-label="t('common.refresh')"
              :disabled="busy"
              @click="load"
            >
              <RefreshCw :size="16" :class="{ 'is-spinning': busy }" />
            </el-button>
          </div>
        </div>

        <div
          v-if="pinnedVersion || latestVersion || root || bootstrap"
          class="platform-ops-release-meta"
        >
          <div v-if="pinnedVersion" class="platform-ops-release-meta__item">
            <span class="platform-ops-release-meta__label">{{ t('platformOps.platform.pinnedVersion') }}</span>
            <span class="platform-ops-release-meta__value">{{ pinnedVersion }}</span>
          </div>
          <div v-if="latestVersion" class="platform-ops-release-meta__item">
            <span class="platform-ops-release-meta__label">{{ t('platformOps.platform.latestVersion') }}</span>
            <span class="platform-ops-release-meta__value">{{ latestVersion }}</span>
          </div>
          <div v-if="root" class="platform-ops-release-meta__item">
            <span class="platform-ops-release-meta__label">{{ t('platformOps.platform.releaseRoot') }}</span>
            <span class="platform-ops-release-meta__value">{{ root }}</span>
          </div>
          <div v-if="bootstrap" class="platform-ops-release-meta__item">
            <span class="platform-ops-release-meta__label">{{ t('platformOps.platform.bootstrapActiveSource') }}</span>
            <span class="platform-ops-release-meta__value">{{ bootstrapSourceLabel }}</span>
          </div>
          <div v-if="bootstrap?.active_path" class="platform-ops-release-meta__item">
            <span class="platform-ops-release-meta__label">{{ t('platformOps.platform.bootstrapActivePath') }}</span>
            <span class="platform-ops-release-meta__value">{{ bootstrap.active_path }}</span>
          </div>
          <div
            v-if="bootstrap && bootstrap.active_source === 'published' && bootstrap.fallback_path !== bootstrap.active_path"
            class="platform-ops-release-meta__item"
          >
            <span class="platform-ops-release-meta__label">{{ t('platformOps.platform.bootstrapFallbackPath') }}</span>
            <span class="platform-ops-release-meta__value">{{ bootstrap.fallback_path }}</span>
          </div>
        </div>

        <el-table
          v-table-column-resize="'platformOps.platform.agentReleases'"
          v-loading="busy"
          :data="rows"
          stripe
          :row-key="(row: ArtifactRow) => `${row.version}::${row.name}`"
          class="hfl-list-table"
          :max-height="PLATFORM_OPS_LIST_TABLE_MAX_HEIGHT"
          :header-cell-style="PLATFORM_OPS_TABLE_HEADER_STYLE"
        >
          <el-table-column prop="version" :label="t('platformOps.platform.colVersion')" min-width="120" />
          <el-table-column :label="t('platformOps.platform.colKind')" min-width="120">
            <template #default="{ row }">{{ kindLabel(row.kind) }}</template>
          </el-table-column>
          <el-table-column prop="name" :label="t('platformOps.platform.colArtifact')" min-width="220" />
          <el-table-column :label="t('platformOps.platform.colSize')" min-width="120">
            <template #default="{ row }">{{ formatBytes(row.size_bytes) }}</template>
          </el-table-column>
          <template #empty>
            <el-empty :description="t('platformOps.platform.emptyAgents')" :image-size="80" />
          </template>
        </el-table>

        <div class="hfl-list-footer">
          <HflPagination
            v-model:current-page="currentPage"
            v-model:page-size="pageSize"
            class="hfl-list-footer__pagination"
            :total="totalCount"
          />
        </div>
      </div>
    </div>
  </ModulePage>
</template>
