import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import type { ComposerTranslation } from 'vue-i18n'
import { ElMessage } from 'element-plus'
import { Activity, Clock, Cpu, Network } from 'lucide-vue-next'
import { useHostMonitorCharts } from '../../composables/useHostMonitorCharts'
import type { SystemMonitorPayload } from '../../lib/monitorApi'
import {
  formatDeploymentHostDetail,
  formatDeploymentHostLabel,
  formatDeploymentHostSummary,
  type DeploymentHostItem,
} from '../lib/platformOpsApi'
import { isAbortError } from '../../lib/api'

type FetchMonitorFn = (params?: {
  hours?: number
  startAt?: string
  endAt?: string
  hostId?: string
}) => Promise<SystemMonitorPayload>

type FetchHostsFn = () => Promise<DeploymentHostItem[]>

export function useDeploymentHostMonitor(
  t: ComposerTranslation,
  fetchMonitor: FetchMonitorFn,
  fetchHosts: FetchHostsFn,
  loadFailedKey = 'ops.monitorPage.loadFailed',
) {
  const loading = ref(false)
  const data = ref<SystemMonitorPayload>({
    host: {},
    range: {},
    current: {},
    series: [],
  })

  const hosts = ref<DeploymentHostItem[]>([])
  const selectedHostId = ref<string | null>(null)
  const entitySearch = ref('')
  const showEntityDropdown = ref(false)
  const entityDropdownRef = ref<HTMLElement | null>(null)

  const selectedTimeOption = ref('24h')
  const customTimeRange = ref({ start: '', end: '' })
  const selectedDisk = ref('all')
  const selectedNetwork = ref('all')

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

  const charts = useHostMonitorCharts(chartData, selectedDisk, selectedNetwork, t)

  const selectedHost = computed(() => hosts.value.find((host) => host.id === selectedHostId.value) || null)

  const hostEntityLabel = computed(() => {
    if (selectedHost.value) return formatDeploymentHostSummary(selectedHost.value)
    const h = data.value.host
    const name = h.nodeName || h.node_name || h.hostname || '—'
    return name
  })

  const hostEntityTooltip = computed(() => {
    if (selectedHost.value) {
      const label = formatDeploymentHostLabel(selectedHost.value)
      const detail = formatDeploymentHostDetail(selectedHost.value)
      const platform = selectedHost.value.platform || ''
      return [label, detail, platform].filter(Boolean).join('\n')
    }
    const h = data.value.host
    return [h.hostname, h.platform].filter(Boolean).join('\n')
  })

  const entityOptions = computed(() =>
    hosts.value.map((host) => ({
      id: host.id,
      label: formatDeploymentHostLabel(host),
      detail: formatDeploymentHostDetail(host),
      status: host.status,
      isOnline: host.status === 'online',
    })),
  )

  const filteredEntities = computed(() => {
    const q = entitySearch.value.trim().toLowerCase()
    if (!q) return entityOptions.value
    return entityOptions.value.filter(
      (item) =>
        item.label.toLowerCase().includes(q) ||
        item.detail.toLowerCase().includes(q),
    )
  })

  function isHostOnline(status: string): boolean {
    return status === 'online'
  }

  function hostStatusLabel(status: string): string {
    return isHostOnline(status) ? t('nodesPage.statusOnline') : t('nodesPage.statusOffline')
  }

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

  const kpiCards = computed(() => {
    const cores = charts.current.value.cpu?.logicalCores ?? charts.current.value.cpu?.logical_cores ?? '—'
    const memTotal = Number(charts.current.value.memory?.total ?? 0)
    const memAvail = Number(charts.current.value.memory?.available ?? 0)
    const { recv, sent } = charts.totalNetworkBytes.value
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

  function formatToUTC(date: Date) {
    return date.toISOString()
  }

  function monitorParams(hours?: number, range?: { startAt: string; endAt: string }) {
    const base = selectedHostId.value ? { hostId: selectedHostId.value } : {}
    if (range) {
      return { ...base, startAt: range.startAt, endAt: range.endAt }
    }
    if (hours !== undefined) {
      const now = new Date()
      const start = new Date(now.getTime() - hours * 60 * 60 * 1000)
      return { ...base, startAt: formatToUTC(start), endAt: formatToUTC(now) }
    }
    return { ...base, hours: 24 }
  }

  async function loadHosts() {
    try {
      hosts.value = await fetchHosts()
      if (!hosts.value.length) {
        selectedHostId.value = null
        data.value = { host: {}, range: {}, current: {}, series: [] }
        return
      }
      if (!hosts.value.some((host) => host.id === selectedHostId.value)) {
        selectedHostId.value = hosts.value[0].id
      }
    } catch (err) {
      if (isAbortError(err)) return
      ElMessage.error({ message: t('platformOps.monitoring.hostLoadHostsFailed'), grouping: true })
      hosts.value = []
      selectedHostId.value = null
    }
  }

  async function fetchData(hours?: number, silent = false) {
    if (!selectedHostId.value) return
    if (!silent) loading.value = true
    try {
      data.value = await fetchMonitor(monitorParams(hours))
    } catch (err) {
      if (isAbortError(err)) return
      ElMessage.error({ message: t(loadFailedKey), grouping: true })
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

  async function refreshCurrentSelection(reloadHosts = false) {
    if (loading.value) return
    loading.value = true
    try {
      if (reloadHosts) await loadHosts()
      if (!selectedHostId.value) return

      if (selectedTimeOption.value === 'custom') {
        const start = new Date(customTimeRange.value.start)
        const end = new Date(customTimeRange.value.end)
        if (
          customTimeRange.value.start
          && customTimeRange.value.end
          && !Number.isNaN(start.getTime())
          && !Number.isNaN(end.getTime())
        ) {
          await applyCustomRange(true)
          return
        }
      }

      const preset = timePresets.value.find((item) => item.value === selectedTimeOption.value)
      const fallbackPreset = timePresets.value.find((item) => item.value === '24h')
      selectedTimeOption.value = preset?.value ?? fallbackPreset?.value ?? '24h'
      await fetchData(preset?.hours ?? fallbackPreset?.hours ?? 24, true)
    } finally {
      loading.value = false
    }
  }

  function onManualRefresh() {
    void refreshCurrentSelection(true)
  }

  async function applyCustomRange(silent = false) {
    if (!selectedHostId.value) return
    if (!customTimeRange.value.start || !customTimeRange.value.end) return
    const start = new Date(customTimeRange.value.start)
    const end = new Date(customTimeRange.value.end)
    if (Number.isNaN(start.getTime()) || Number.isNaN(end.getTime())) return
    selectedTimeOption.value = 'custom'
    if (!silent) loading.value = true
    try {
      data.value = await fetchMonitor(
        monitorParams(undefined, {
          startAt: formatToUTC(start),
          endAt: formatToUTC(end),
        }),
      )
    } catch (err) {
      if (isAbortError(err)) return
      ElMessage.error({ message: t(loadFailedKey), grouping: true })
    } finally {
      if (!silent) loading.value = false
    }
  }

  function clearCustomRange() {
    customTimeRange.value = { start: '', end: '' }
    selectedTimeOption.value = ''
    data.value = { host: data.value.host, range: {}, current: {}, series: [] }
  }

  function onDocumentClick(event: MouseEvent) {
    const target = event.target as Node
    if (entityDropdownRef.value && !entityDropdownRef.value.contains(target)) {
      showEntityDropdown.value = false
    }
  }

  function selectHost(hostId: string) {
    selectedHostId.value = hostId
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
    await refreshCurrentSelection(true)
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

  return {
    loading,
    data,
    hosts,
    selectedHostId,
    selectedHost,
    entitySearch,
    showEntityDropdown,
    entityDropdownRef,
    filteredEntities,
    hostEntityLabel,
    hostEntityTooltip,
    hostStatusLabel,
    isHostOnline,
    selectedTimeOption,
    customTimeRange,
    selectedDisk,
    selectedNetwork,
    timePresets,
    timeRangeLabel,
    kpiCards,
    hasChartData,
    onPresetSelect,
    onTimeRangeApply,
    onManualRefresh,
    clearCustomRange,
    selectHost,
    ...charts,
  }
}
