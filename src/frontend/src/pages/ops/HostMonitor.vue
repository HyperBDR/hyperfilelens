<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { LineChart } from 'echarts/charts'
import { GridComponent, LegendComponent, TooltipComponent } from 'echarts/components'
import VChart from 'vue-echarts'
import {
  Activity,
  ChartSpline,
  ChevronDown,
  Clock,
  Cpu,
  Network,
  RefreshCw,
  Search,
} from 'lucide-vue-next'
import { ElMessage } from 'element-plus'
import ModulePage from '../../components/ModulePage.vue'
import OpsStatCard from '../../components/ops/OpsStatCard.vue'
import HflDateTimeRangePicker from '../../components/HflDateTimeRangePicker.vue'
import { useOpsMenus } from '../../composables/useOpsMenus'
import { debouncedNodeStatus } from '../../composables/useNodeConnectionDisplay'
import { useHostMonitorCharts } from '../../composables/useHostMonitorCharts'
import { resolveHostMonitorRefreshTarget } from './hostMonitorRefresh'
import {
  fetchMonitorNodes,
  fetchNodeMonitor,
  formatNodeEntityLabel,
  type MonitorNodeItem,
  type NodeMonitorRole,
  type SystemMonitorPayload,
} from '../../lib/monitorApi'
import { apiErrorMessageI18n, isAbortError } from '../../lib/api'
import type { NodeStatus } from '../../types/node'

use([CanvasRenderer, LineChart, GridComponent, LegendComponent, TooltipComponent])

const { t } = useI18n()
const opsMenus = useOpsMenus()

const loading = ref(false)
const data = ref<SystemMonitorPayload>({
  host: {},
  range: {},
  current: {},
  series: [],
})

const sourceType = ref<NodeMonitorRole>('agent')
const nodes = ref<MonitorNodeItem[]>([])
const selectedNodeId = ref<number | null>(null)
const entitySearch = ref('')
const showEntityDropdown = ref(false)
const entityDropdownRef = ref<HTMLElement | null>(null)

const selectedTimeOption = ref('24h')
const customTimeRange = ref({ start: '', end: '' })
const selectedDisk = ref('all')
const selectedNetwork = ref('all')

const sourceTypes = computed(() => [
  { id: 'agent' as NodeMonitorRole, label: t('ops.monitorPage.sourceTypeHost') },
  { id: 'proxy' as NodeMonitorRole, label: t('ops.monitorPage.sourceTypeAgent') },
  { id: 'gateway' as NodeMonitorRole, label: t('ops.monitorPage.sourceTypeGateway') },
])

const timePresets = computed(() => [
  { value: '5m', label: t('ops.monitorPage.preset.5m'), hours: 5 / 60 },
  { value: '15m', label: t('ops.monitorPage.preset.15m'), hours: 15 / 60 },
  { value: '30m', label: t('ops.monitorPage.preset.30m'), hours: 30 / 60 },
  { value: '1h', label: t('ops.monitorPage.preset.1h'), hours: 1 },
  { value: '3h', label: t('ops.monitorPage.preset.3h'), hours: 3 },
  { value: '6h', label: t('ops.monitorPage.preset.6h'), hours: 6 },
  { value: '12h', label: t('ops.monitorPage.preset.12h'), hours: 12 },
  { value: '24h', label: t('ops.monitorPage.preset.24h'), hours: 24 },
  { value: '2d', label: t('ops.monitorPage.preset.2d'), hours: 48 },
  { value: '7d', label: t('ops.monitorPage.preset.7d'), hours: 168 },
  { value: '15d', label: t('ops.monitorPage.preset.15d'), hours: 360 },
  { value: '30d', label: t('ops.monitorPage.preset.30d'), hours: 720 },
])

const chartData = computed(() => ({
  series: data.value.series || [],
  current: data.value.current || {},
}))

const {
  current,
  uniqueDiskNames,
  uniqueNetworkNames,
  totalNetworkBytes,
  cpuOption,
  loadOption,
  memoryOption,
  diskUsageOption,
  diskThroughputOption,
  diskIopsOption,
  networkBytesOption,
  networkPacketsOption,
} = useHostMonitorCharts(chartData, selectedDisk, selectedNetwork, t)

const selectedNode = computed(() => nodes.value.find((n) => n.id === selectedNodeId.value) || null)

const hostEntityLabel = computed(() => {
  if (selectedNode.value) return formatNodeEntityLabel(selectedNode.value)
  const h = data.value.host
  const name = h.hostname || h.nodeName || h.node_name || '—'
  return h.platform ? `${name} (${h.platform})` : name
})

function isNodeOnline(status: string): boolean {
  return status === 'online'
}

function nodeStatusLabel(node: Pick<MonitorNodeItem, 'id' | 'status'> & { status: NodeStatus | string }): string {
  const status = debouncedNodeStatus({
    id: node.id,
    status: node.status as NodeStatus,
  })
  if (status === 'reconnecting') return t('nodesPage.statusReconnecting')
  return isNodeOnline(status) ? t('nodesPage.statusOnline') : t('nodesPage.statusOffline')
}

const entityOptions = computed(() =>
  nodes.value.map((node) => ({
    id: node.id,
    label: formatNodeEntityLabel(node),
    status: node.status,
    isOnline: isNodeOnline(node.status),
  })),
)

const filteredEntities = computed(() => {
  const q = entitySearch.value.trim().toLowerCase()
  if (!q) return entityOptions.value
  return entityOptions.value.filter((item) => item.label.toLowerCase().includes(q))
})

const timeRangeLabel = computed(() => {
  const range = data.value.range
  const startRaw = range.startAt ?? range.start_at
  const endRaw = range.endAt ?? range.end_at
  if (!startRaw || !endRaw) return '—'
  const fmt = (iso: string) => {
    const d = new Date(iso)
    const pad = (n: number) => String(n).padStart(2, '0')
    return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`
  }
  return `${fmt(startRaw)} ~ ${fmt(endRaw)}`
})

const uptimeText = computed(() => {
  const boot =
    data.value.current?.bootTime ??
    data.value.current?.boot_time ??
    data.value.host.bootTime ??
    data.value.host.boot_time
  if (!boot) return '—'
  const seconds = Math.max(0, Math.floor(Date.now() / 1000 - boot))
  const days = Math.floor(seconds / 86400)
  const hours = Math.floor((seconds % 86400) / 3600)
  const minutes = Math.floor((seconds % 3600) / 60)
  const secs = seconds % 60
  if (days > 0) return t('ops.monitorPage.uptimeDays', { days, hours, minutes, secs })
  if (hours > 0) return t('ops.monitorPage.uptimeHours', { hours, minutes, secs })
  return t('ops.monitorPage.uptimeMinutes', { minutes, secs })
})

const kpiCards = computed(() => {
  const cores = current.value.cpu?.logicalCores ?? current.value.cpu?.logical_cores ?? '—'
  const memTotal = Number(current.value.memory?.total ?? 0)
  const memAvail = Number(current.value.memory?.available ?? 0)
  const { recv, sent } = totalNetworkBytes.value
  return [
    {
      label: t('ops.monitorPage.uptime'),
      value: uptimeText.value,
      sub: t('ops.monitorPage.uptimeSub'),
      accent: 'indigo' as const,
      icon: Clock,
    },
    {
      label: t('ops.monitorPage.cpuCores'),
      value: String(cores),
      sub: `${t('ops.monitorPage.logicalCores')}: ${cores}`,
      accent: 'green' as const,
      icon: Cpu,
    },
    {
      label: t('ops.monitorPage.memoryInfo'),
      value: bytes(memTotal),
      sub: `${t('ops.monitorPage.memoryAvailable')}: ${bytes(memAvail)}`,
      accent: 'orange' as const,
      icon: Activity,
    },
    {
      label: t('ops.monitorPage.networkInfo'),
      value: `${bytes(recv)} / ${bytes(sent)}`,
      sub: t('ops.monitorPage.networkRxTx'),
      accent: 'pink' as const,
      icon: Network,
    },
  ]
})

function hasChartData(option: unknown): boolean {
  const series = (option as { series?: Array<{ data?: unknown[] }> } | undefined)?.series
  return Array.isArray(series) && series.some((item) => Array.isArray(item.data) && item.data.length > 0)
}

function onDocumentClick(event: MouseEvent) {
  const target = event.target as Node
  if (entityDropdownRef.value && !entityDropdownRef.value.contains(target)) {
    showEntityDropdown.value = false
  }
}

function formatToUTC(date: Date) {
  return date.toISOString()
}

function bytes(value: number) {
  if (!value) return '0 B'
  const units = ['B', 'KB', 'MB', 'GB', 'TB']
  let index = 0
  let size = value
  while (size >= 1024 && index < units.length - 1) {
    size /= 1024
    index += 1
  }
  return `${size.toFixed(size >= 10 ? 1 : 2)} ${units[index]}`
}

async function loadNodes() {
  try {
    nodes.value = await fetchMonitorNodes(sourceType.value)
    if (!nodes.value.length) {
      selectedNodeId.value = null
      data.value = { host: {}, range: {}, current: {}, series: [] }
      return
    }
    if (!nodes.value.some((n) => n.id === selectedNodeId.value)) {
      selectedNodeId.value = nodes.value[0].id
    }
  } catch (err) {
    if (isAbortError(err)) return
    ElMessage.error({
      message: apiErrorMessageI18n(err, t, t('ops.monitorPage.loadNodesFailed')),
      grouping: true,
    })
    nodes.value = []
    selectedNodeId.value = null
  }
}

async function fetchData(hours?: number, silent = false) {
  if (!selectedNodeId.value) return
  if (!silent) loading.value = true
  try {
    if (hours !== undefined) {
      const now = new Date()
      const start = new Date(now.getTime() - hours * 60 * 60 * 1000)
      data.value = await fetchNodeMonitor(selectedNodeId.value, {
        startAt: formatToUTC(start),
        endAt: formatToUTC(now),
      })
    } else {
      data.value = await fetchNodeMonitor(selectedNodeId.value, { hours: 24 })
    }
  } catch (err) {
    if (isAbortError(err)) return
    ElMessage.error({
      message: apiErrorMessageI18n(err, t, t('ops.monitorPage.loadFailed')),
      grouping: true,
    })
  } finally {
    if (!silent) loading.value = false
  }
}

function onPresetSelect(value: string, hours?: number) {
  selectedTimeOption.value = value
  const presetHours = hours ?? timePresets.value.find((p) => p.value === value)?.hours
  if (presetHours !== undefined) void fetchData(presetHours)
}

function onTimeRangeApply(start: string, end: string) {
  customTimeRange.value = { start, end }
  selectedTimeOption.value = 'custom'
  void applyCustomRange()
}

async function onManualRefresh() {
  if (loading.value) return
  loading.value = true
  try {
    await loadNodes()
    if (!selectedNodeId.value) return

    const target = resolveHostMonitorRefreshTarget(
      selectedTimeOption.value,
      customTimeRange.value,
      timePresets.value,
    )
    if (target.kind === 'custom') {
      await applyCustomRange(true)
      return
    }
    selectedTimeOption.value = target.value
    await fetchData(target.hours, true)
  } finally {
    loading.value = false
  }
}

async function applyCustomRange(silent = false) {
  if (!selectedNodeId.value) return
  if (!customTimeRange.value.start || !customTimeRange.value.end) return
  const start = new Date(customTimeRange.value.start)
  const end = new Date(customTimeRange.value.end)
  if (Number.isNaN(start.getTime()) || Number.isNaN(end.getTime())) return
  selectedTimeOption.value = 'custom'
  if (!silent) loading.value = true
  try {
    data.value = await fetchNodeMonitor(selectedNodeId.value, {
      startAt: formatToUTC(start),
      endAt: formatToUTC(end),
    })
  } catch (err) {
    if (isAbortError(err)) return
    ElMessage.error({
      message: apiErrorMessageI18n(err, t, t('ops.monitorPage.loadFailed')),
      grouping: true,
    })
  } finally {
    if (!silent) loading.value = false
  }
}

function clearCustomRange() {
  customTimeRange.value = { start: '', end: '' }
  selectedTimeOption.value = ''
  data.value = { host: data.value.host, range: {}, current: {}, series: [] }
}

async function onSourceTypeChange(value: NodeMonitorRole) {
  sourceType.value = value
  entitySearch.value = ''
  await loadNodes()
  if (selectedNodeId.value) {
    await fetchData(24)
  }
}

function selectEntity(nodeId: number) {
  selectedNodeId.value = nodeId
  showEntityDropdown.value = false
  entitySearch.value = ''
  void fetchData(24)
}

onMounted(async () => {
  document.addEventListener('click', onDocumentClick)
  const now = new Date()
  const start = new Date(now.getTime() - 24 * 60 * 60 * 1000)
  const fmt = (d: Date) => {
    const pad = (n: number) => String(n).padStart(2, '0')
    return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`
  }
  customTimeRange.value = { start: fmt(start), end: fmt(now) }
  await loadNodes()
  if (selectedNodeId.value) {
    await fetchData(24)
  }
})

onUnmounted(() => {
  document.removeEventListener('click', onDocumentClick)
})

watch(
  () => data.value.range,
  (range) => {
    const startRaw = range.startAt ?? range.start_at
    const endRaw = range.endAt ?? range.end_at
    if (!startRaw || !endRaw) return
    const toLocal = (iso: string) => {
      const d = new Date(iso)
      const pad = (n: number) => String(n).padStart(2, '0')
      return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`
    }
    customTimeRange.value = { start: toLocal(startRaw), end: toLocal(endRaw) }
  },
  { deep: true },
)
</script>

<template>
  <ModulePage :menus="opsMenus">
    <div v-loading="loading" class="host-monitor">
      <header class="host-monitor__toolbar">
        <ElSelect
          v-model="sourceType"
          class="host-monitor__source-select"
          @change="onSourceTypeChange"
        >
          <ElOption
            v-for="item in sourceTypes"
            :key="item.id"
            :label="item.label"
            :value="item.id"
          />
        </ElSelect>

        <div ref="entityDropdownRef" class="host-monitor__entity">
          <button
            type="button"
            class="host-monitor__entity-btn"
            @click.stop="showEntityDropdown = !showEntityDropdown"
          >
            <span class="host-monitor__entity-btn-main">
              <span class="host-monitor__entity-label">{{ hostEntityLabel }}</span>
              <span
                v-if="selectedNode"
                class="host-monitor__entity-status"
                :class="
                  isNodeOnline(selectedNode.status)
                    ? 'host-monitor__entity-status--online'
                    : 'host-monitor__entity-status--offline'
                "
              >
                <span class="host-monitor__entity-status-dot" aria-hidden="true" />
                {{ selectedNode ? nodeStatusLabel(selectedNode) : '' }}
              </span>
            </span>
            <ChevronDown
              :size="16"
              class="host-monitor__chevron"
              :class="{ 'host-monitor__chevron--open': showEntityDropdown }"
            />
          </button>
          <div v-if="showEntityDropdown" class="host-monitor__entity-panel">
            <div class="host-monitor__entity-search">
              <Search :size="16" class="host-monitor__search-icon" />
              <input
                v-model="entitySearch"
                type="text"
                :placeholder="t('ops.monitorPage.searchPlaceholder')"
              />
            </div>
            <div class="host-monitor__entity-list">
              <p v-if="!filteredEntities.length" class="host-monitor__entity-empty">
                {{ t('ops.monitorPage.noNodes') }}
              </p>
              <button
                v-for="entity in filteredEntities"
                :key="entity.id"
                type="button"
                class="host-monitor__entity-item"
                :class="{ 'host-monitor__entity-item--active': entity.id === selectedNodeId }"
                @click="selectEntity(entity.id)"
              >
                <span class="host-monitor__entity-item-label">{{ entity.label }}</span>
                <span
                  class="host-monitor__entity-status"
                  :class="
                    entity.isOnline
                      ? 'host-monitor__entity-status--online'
                      : 'host-monitor__entity-status--offline'
                  "
                >
                  <span class="host-monitor__entity-status-dot" aria-hidden="true" />
                  {{ nodeStatusLabel({ id: entity.id, status: entity.status }) }}
                </span>
              </button>
            </div>
          </div>
        </div>

        <div class="host-monitor__toolbar-tail">
          <HflDateTimeRangePicker
            class="host-monitor__time-range"
            :label="timeRangeLabel"
            :presets="timePresets"
            :selected-preset="selectedTimeOption"
            :start="customTimeRange.start"
            :end="customTimeRange.end"
            :clear-text="t('ops.monitorPage.clearRange')"
            :apply-text="t('ops.monitorPage.applyRange')"
            @preset="onPresetSelect"
            @apply="onTimeRangeApply"
            @clear="clearCustomRange"
          />

          <el-button
            class="hfl-refresh-button"
            :title="t('ops.task.btnRefresh')"
            :aria-label="t('ops.task.btnRefresh')"
            :disabled="loading"
            @click="onManualRefresh()"
          >
            <RefreshCw :size="16" :class="{ 'is-spinning': loading }" />
          </el-button>
        </div>
      </header>

      <div class="host-monitor__kpi">
        <OpsStatCard
          v-for="(card, index) in kpiCards"
          :key="index"
          class="host-monitor__kpi-card"
          :label="card.label"
          :value="card.value"
          :sub="card.sub"
          :accent="card.accent"
          accent-side="left"
        >
          <template #icon>
            <component :is="card.icon" :size="17" />
          </template>
        </OpsStatCard>
      </div>

      <section class="host-monitor__section">
        <div class="host-monitor__section-head">
          <span class="host-monitor__section-bar" />
          <h2>{{ t('ops.monitorPage.systemResources') }}</h2>
        </div>
        <div class="host-monitor__charts host-monitor__charts--quad">
          <div class="chart-card">
            <div class="chart-card__head">
              <h3>{{ t('ops.monitorPage.cpuUsage') }}</h3>
            </div>
            <VChart v-if="hasChartData(cpuOption)" class="chart-card__chart" :option="cpuOption" autoresize />
            <div v-else class="chart-card__empty">
              <ChartSpline :size="28" />
              <span>{{ t('ops.monitorPage.noChartData') }}</span>
            </div>
          </div>
          <div class="chart-card">
            <div class="chart-card__head">
              <h3>{{ t('ops.monitorPage.loadAverage') }}</h3>
            </div>
            <VChart v-if="hasChartData(loadOption)" class="chart-card__chart" :option="loadOption" autoresize />
            <div v-else class="chart-card__empty">
              <ChartSpline :size="28" />
              <span>{{ t('ops.monitorPage.noChartData') }}</span>
            </div>
          </div>
          <div class="chart-card">
            <div class="chart-card__head">
              <h3>{{ t('ops.monitorPage.memoryUsage') }}</h3>
            </div>
            <VChart v-if="hasChartData(memoryOption)" class="chart-card__chart" :option="memoryOption" autoresize />
            <div v-else class="chart-card__empty">
              <ChartSpline :size="28" />
              <span>{{ t('ops.monitorPage.noChartData') }}</span>
            </div>
          </div>
          <div class="chart-card">
            <div class="chart-card__head">
              <h3>{{ t('ops.monitorPage.diskUsage') }}</h3>
              <ElSelect
                v-if="uniqueDiskNames.length"
                v-model="selectedDisk"
                size="small"
                class="chart-card__filter"
              >
                <ElOption :label="t('ops.monitorPage.all')" value="all" />
                <ElOption v-for="name in uniqueDiskNames" :key="name" :label="name" :value="name" />
              </ElSelect>
            </div>
            <VChart v-if="hasChartData(diskUsageOption)" class="chart-card__chart" :option="diskUsageOption" autoresize />
            <div v-else class="chart-card__empty">
              <ChartSpline :size="28" />
              <span>{{ t('ops.monitorPage.noChartData') }}</span>
            </div>
          </div>
        </div>
      </section>

      <section class="host-monitor__section">
        <div class="host-monitor__section-head">
          <span class="host-monitor__section-bar" />
          <h2>{{ t('ops.monitorPage.storageSection') }}</h2>
        </div>
        <div class="host-monitor__charts host-monitor__charts--pair">
          <div class="chart-card">
            <div class="chart-card__head">
              <h3>{{ t('ops.monitorPage.diskThroughput') }}</h3>
            </div>
            <VChart v-if="hasChartData(diskThroughputOption)" class="chart-card__chart" :option="diskThroughputOption" autoresize />
            <div v-else class="chart-card__empty">
              <ChartSpline :size="28" />
              <span>{{ t('ops.monitorPage.noChartData') }}</span>
            </div>
          </div>
          <div class="chart-card">
            <div class="chart-card__head">
              <h3>{{ t('ops.monitorPage.diskIops') }}</h3>
            </div>
            <VChart v-if="hasChartData(diskIopsOption)" class="chart-card__chart" :option="diskIopsOption" autoresize />
            <div v-else class="chart-card__empty">
              <ChartSpline :size="28" />
              <span>{{ t('ops.monitorPage.noChartData') }}</span>
            </div>
          </div>
        </div>
      </section>

      <section class="host-monitor__section">
        <div class="host-monitor__section-head">
          <span class="host-monitor__section-bar" />
          <h2>{{ t('ops.monitorPage.networkSection') }}</h2>
        </div>
        <div class="host-monitor__charts host-monitor__charts--pair">
          <div class="chart-card">
            <div class="chart-card__head">
              <h3>{{ t('ops.monitorPage.networkTraffic') }}</h3>
              <ElSelect
                v-if="uniqueNetworkNames.length"
                v-model="selectedNetwork"
                size="small"
                class="chart-card__filter"
              >
                <ElOption :label="t('ops.monitorPage.all')" value="all" />
                <ElOption
                  v-for="name in uniqueNetworkNames"
                  :key="name"
                  :label="name"
                  :value="name"
                />
              </ElSelect>
            </div>
            <VChart v-if="hasChartData(networkBytesOption)" class="chart-card__chart" :option="networkBytesOption" autoresize />
            <div v-else class="chart-card__empty">
              <ChartSpline :size="28" />
              <span>{{ t('ops.monitorPage.noChartData') }}</span>
            </div>
          </div>
          <div class="chart-card">
            <div class="chart-card__head">
              <h3>{{ t('ops.monitorPage.networkPackets') }}</h3>
            </div>
            <VChart v-if="hasChartData(networkPacketsOption)" class="chart-card__chart" :option="networkPacketsOption" autoresize />
            <div v-else class="chart-card__empty">
              <ChartSpline :size="28" />
              <span>{{ t('ops.monitorPage.noChartData') }}</span>
            </div>
          </div>
        </div>
      </section>
    </div>
  </ModulePage>
</template>

<style scoped>
.host-monitor {
  --hm-gap: 16px;
  --hm-control-h: 34px;
  --hm-card-radius: 10px;
  display: flex;
  flex-direction: column;
  gap: 20px;
  width: 100%;
  min-width: 0;
}

.host-monitor__toolbar {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.host-monitor__source-select {
  width: 148px;
  height: var(--hm-control-h) !important;
  flex-shrink: 0;
}

.host-monitor__source-select :deep(.el-select__wrapper) {
  min-height: var(--hm-control-h) !important;
  height: var(--hm-control-h);
}

.host-monitor__entity {
  position: relative;
  width: 360px;
  max-width: min(360px, 42vw);
  flex-shrink: 0;
}

.host-monitor__toolbar-tail {
  margin-left: auto;
  display: flex;
  align-items: center;
  gap: 8px;
  flex-shrink: 0;
}

.host-monitor__time-range {
  min-width: 220px;
}

.host-monitor__entity-btn {
  display: flex;
  align-items: center;
  justify-content: space-between;
  width: 100%;
  height: var(--hm-control-h);
  padding: 0 12px;
  border: 0;
  border-radius: var(--el-border-radius-base, 8px);
  background: var(--el-fill-color-blank, #fff);
  box-shadow: 0 0 0 1px var(--el-border-color, #dcdfe6) inset;
  color: var(--el-text-color-regular, #606266);
  font-size: var(--el-font-size-base, 14px);
  line-height: var(--hm-control-h);
  cursor: pointer;
  outline: none;
  transition: box-shadow 0.2s cubic-bezier(0.645, 0.045, 0.355, 1);
}

.host-monitor__entity-btn:hover,
.host-monitor__entity-btn:focus-visible {
  box-shadow: 0 0 0 1px var(--el-color-primary, #409eff) inset;
}

.host-monitor__entity-btn:focus-visible {
  outline: 2px solid var(--el-color-primary-light-7, rgba(64, 158, 255, 0.35));
  outline-offset: 1px;
}

.host-monitor__entity-btn-main {
  display: flex;
  min-width: 0;
  flex: 1;
  align-items: center;
  gap: 8px;
  overflow: hidden;
}

.host-monitor__entity-label {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  text-align: left;
  flex: 1;
  min-width: 0;
}

.host-monitor__entity-status {
  display: inline-flex;
  flex-shrink: 0;
  align-items: center;
  gap: 5px;
  font-size: 12px;
  font-weight: 500;
  line-height: 1;
}

.host-monitor__entity-status-dot {
  width: 6px;
  height: 6px;
  border-radius: 9999px;
  flex-shrink: 0;
}

.host-monitor__entity-status--online {
  color: #15803d;
}

.host-monitor__entity-status--online .host-monitor__entity-status-dot {
  background: #22c55e;
  box-shadow: 0 0 0 2px rgba(34, 197, 94, 0.22);
}

.host-monitor__entity-status--offline {
  color: #64748b;
}

.host-monitor__entity-status--offline .host-monitor__entity-status-dot {
  background: #94a3b8;
  box-shadow: 0 0 0 2px rgba(148, 163, 184, 0.2);
}

.host-monitor__chevron {
  flex-shrink: 0;
  margin-left: 8px;
  color: var(--color-text-secondary, #86909c);
  transition: transform 0.2s;
}

.host-monitor__chevron--open {
  transform: rotate(180deg);
}

.host-monitor__entity-panel {
  position: absolute;
  top: calc(var(--hm-control-h) + 6px);
  left: 0;
  z-index: 2000;
  width: 100%;
  min-width: 320px;
  padding: 6px;
  border: 1px solid var(--color-border, #d9d9d9);
  border-radius: var(--el-popper-border-radius, var(--el-border-radius-base, 8px));
  background: var(--el-popper-bg, var(--el-bg-color-overlay, #fff));
  box-shadow:
    0px 5px 5px -3px rgba(0, 0, 0, .2),
    0px 3px 14px 2px rgba(0, 0, 0, .12),
    0px 8px 10px 1px rgba(0, 0, 0, .14);
}

.host-monitor__entity-search {
  position: relative;
  margin-bottom: 6px;
}

.host-monitor__search-icon {
  position: absolute;
  left: 12px;
  top: 50%;
  transform: translateY(-50%);
  color: var(--color-text-secondary, #86909c);
}

.host-monitor__entity-search input {
  width: 100%;
  height: var(--hm-control-h);
  padding: 0 12px 0 36px;
  border: 0;
  border-radius: var(--el-border-radius-base, 8px);
  background: var(--el-fill-color-blank, #fff);
  box-shadow: 0 0 0 1px var(--el-border-color, #dcdfe6) inset;
  color: var(--el-text-color-regular, #606266);
  font-size: 12px;
  outline: none;
  box-sizing: border-box;
  transition: box-shadow 0.2s cubic-bezier(0.645, 0.045, 0.355, 1);
}

.host-monitor__entity-search input:focus {
  box-shadow: 0 0 0 1px var(--el-color-primary, #409eff) inset;
}

.host-monitor__entity-list {
  max-height: 240px;
  overflow-y: auto;
}

.host-monitor__entity-empty {
  margin: 0;
  padding: 12px;
  font-size: 12px;
  color: var(--el-text-color-secondary, #909399);
  text-align: center;
}

.host-monitor__entity-item {
  display: flex;
  width: 100%;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  min-height: 34px;
  padding: 0 12px;
  border: none;
  border-radius: var(--el-border-radius-base, 8px);
  background: transparent;
  text-align: left;
  font-size: 12px;
  line-height: 34px;
  color: var(--el-text-color-regular, #606266);
  cursor: pointer;
}

.host-monitor__entity-item-label {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.host-monitor__entity-item:hover,
.host-monitor__entity-item--active {
  background: var(--el-fill-color-light, #f5f7fa);
  color: var(--el-color-primary, #409eff);
  font-weight: 500;
}

.host-monitor__entity-item--active .host-monitor__entity-item-label {
  font-weight: 500;
}

.host-monitor__kpi {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: var(--hm-gap);
}

.host-monitor__kpi-card {
  min-height: 108px;
}

.host-monitor__kpi-card :deep(.hfl-ops-stat-card__value) {
  font-family: ui-monospace, monospace;
  word-break: break-all;
}

.host-monitor__section {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.host-monitor__section-head {
  display: flex;
  align-items: center;
  gap: 8px;
}

.host-monitor__section-bar {
  width: 3px;
  height: 14px;
  border-radius: 2px;
  background: #4f46e5;
  flex-shrink: 0;
}

.host-monitor__section-head h2 {
  margin: 0;
  font-size: 14px;
  font-weight: 600;
  color: var(--color-text-title, #1d2129);
}

.host-monitor__charts {
  display: grid;
  gap: var(--hm-gap);
}

.host-monitor__charts--quad {
  grid-template-columns: repeat(4, minmax(0, 1fr));
}

.host-monitor__charts--pair {
  grid-template-columns: repeat(2, minmax(0, 1fr));
}

.chart-card {
  display: flex;
  flex-direction: column;
  min-height: 280px;
  padding: 14px 16px 12px;
  border-radius: var(--hm-card-radius);
  border: 1px solid var(--color-border, #e2e8f0);
  background: var(--color-bg-card, #fff);
  min-width: 0;
}

.chart-card__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  flex-shrink: 0;
  min-height: 28px;
  margin-bottom: 4px;
}

.chart-card__head h3 {
  margin: 0;
  font-size: 12px;
  font-weight: 600;
  color: var(--color-text-title, #1d2129);
  white-space: nowrap;
}

.chart-card__filter {
  width: 112px;
  flex-shrink: 0;
}

.chart-card__chart {
  flex: 1;
  min-height: 220px;
  width: 100%;
}

.chart-card__empty {
  display: flex;
  flex: 1;
  min-height: 220px;
  align-items: center;
  justify-content: center;
  flex-direction: column;
  gap: 10px;
  color: var(--color-text-secondary, #86909c);
  font-size: 13px;
  font-weight: 500;
  text-align: center;
}

.chart-card__empty svg {
  color: #94a3b8;
  stroke-width: 1.7;
}

@media (max-width: 1280px) {
  .host-monitor__kpi,
  .host-monitor__charts--quad {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 768px) {
  .host-monitor__toolbar {
    flex-direction: column;
    align-items: stretch;
  }

  .host-monitor__source-select,
  .host-monitor__entity {
    width: 100%;
    max-width: none;
  }

  .host-monitor__toolbar-tail {
    margin-left: 0;
    width: 100%;
    justify-content: flex-end;
  }

  .host-monitor__toolbar-tail :deep(.hfl-date-time-range-picker) {
    flex: 1;
    min-width: 0;
  }

  .host-monitor__toolbar-tail :deep(.hfl-date-time-range-picker__trigger) {
    width: 100%;
    justify-content: center;
  }

  .host-monitor__kpi,
  .host-monitor__charts--quad,
  .host-monitor__charts--pair {
    grid-template-columns: 1fr;
  }
}
</style>
