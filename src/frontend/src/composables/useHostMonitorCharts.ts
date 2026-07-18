import { computed, type Ref } from 'vue'
import type { SystemMetricSample } from '../lib/monitorApi'

type SeriesRow = SystemMetricSample

const CHART_COLORS = ['#6366f1', '#10b981', '#f59e0b', '#ef4444', '#06b6d4', '#8b5cf6', '#84cc16', '#f97316']

function diffSeries(items: SeriesRow[], key: 'disk_io' | 'networks', field: string) {
  const names = new Set<string>()
  items.forEach((sample) => {
    const rows = (sample[key] ?? sample[key === 'disk_io' ? 'diskIo' : key]) as Array<Record<string, unknown>> | undefined
    rows?.forEach((row) => names.add(String(row.name ?? row.mountpoint ?? row.device ?? '')))
  })
  return Array.from(names)
    .filter(Boolean)
    .map((name) => {
      let prev: number | null = null
      return {
        name,
        data: items.map((sample) => {
          const rows = (sample[key] ?? sample[key === 'disk_io' ? 'diskIo' : key]) as
            | Array<Record<string, unknown>>
            | undefined
          const row = rows?.find(
            (item) => String(item.name ?? item.mountpoint ?? item.device) === name,
          )
          const value = Number(row?.[field] ?? 0)
          const rate = prev === null ? 0 : Math.max(value - prev, 0)
          prev = value
          return rate
        }),
      }
    })
}

type ChartStyle = 'line' | 'area'

function chartOption(
  series: { name: string; data: number[] }[],
  labels: string[],
  opts: { max?: number; style?: ChartStyle; unit?: string } = {},
) {
  const style = opts.style ?? 'line'
  const isArea = style === 'area'
  return {
    color: CHART_COLORS,
    tooltip: {
      trigger: 'axis',
      backgroundColor: '#fff',
      borderWidth: 0,
      padding: [8, 12],
      textStyle: { fontSize: 11, color: '#475569' },
      extraCssText: 'box-shadow: 0 10px 15px -3px rgb(0 0 0 / 0.1); border-radius: 12px;',
    },
    legend: {
      top: 0,
      type: 'scroll',
      icon: 'circle',
      itemWidth: 8,
      itemHeight: 8,
      textStyle: { fontSize: 10, color: '#64748b' },
    },
    grid: { left: 42, right: 12, top: 42, bottom: 8 },
    xAxis: {
      type: 'category',
      data: labels,
      boundaryGap: false,
      show: false,
    },
    yAxis: {
      type: 'value',
      max: opts.max,
      axisLine: { show: false },
      axisTick: { show: false },
      splitLine: { lineStyle: { type: 'dashed', color: '#f1f5f9' } },
      axisLabel: {
        fontSize: 10,
        color: '#94a3b8',
        formatter: (val: number) => (opts.unit ? `${val}${opts.unit}` : String(val)),
      },
    },
    series: series.map((item, index) => ({
      name: item.name,
      type: 'line',
      smooth: true,
      showSymbol: false,
      lineStyle: { width: 2 },
      areaStyle: isArea
        ? {
            opacity: 0.2,
            color: {
              type: 'linear',
              x: 0,
              y: 0,
              x2: 0,
              y2: 1,
              colorStops: [
                { offset: 0.05, color: CHART_COLORS[index % CHART_COLORS.length] },
                { offset: 0.95, color: 'rgba(255,255,255,0)' },
              ],
            },
          }
        : { opacity: 0.08 },
      data: item.data,
    })),
  }
}

function cpuPercent(sample: SeriesRow) {
  return Number(sample.cpu?.usagePercent ?? sample.cpu?.usage_percent ?? 0)
}

export function useHostMonitorCharts(
  data: Ref<{ series: SeriesRow[]; current: SeriesRow }>,
  selectedDisk: Ref<string>,
  selectedNetwork: Ref<string>,
  t: (key: string) => string,
) {
  const labels = computed(() =>
    data.value.series.map((item) => new Date(item.timestamp).toLocaleTimeString()),
  )

  const current = computed(() => data.value.current || {})
  const currentDisks = computed(() => {
    const d = current.value.disks
    return Array.isArray(d) ? d : []
  })
  const currentNetworks = computed(() => {
    const n = current.value.networks
    return Array.isArray(n) ? n : []
  })

  const uniqueDiskNames = computed(() => {
    const names = new Set<string>()
    data.value.series.forEach((sample) => {
      sample.disks?.forEach((disk) => {
        const label = disk.mountpoint || disk.device
        if (label) names.add(label)
      })
    })
    return Array.from(names).sort()
  })

  const uniqueNetworkNames = computed(() => {
    const names = new Set<string>()
    data.value.series.forEach((sample) => {
      sample.networks?.forEach((nic) => {
        if (nic.name) names.add(String(nic.name))
      })
    })
    return Array.from(names).sort()
  })

  const totalDiskUsage = computed(() => {
    const disks = currentDisks.value
    if (!disks.length) return { used: 0, total: 0, percent: 0 }
    const used = disks.reduce((sum, d) => sum + Number(d.used || 0), 0)
    const total = disks.reduce((sum, d) => sum + Number(d.total || 0), 0)
    return { used, total, percent: total > 0 ? Math.round((used / total) * 100) : 0 }
  })

  const totalNetworkBytes = computed(() => {
    const nets = currentNetworks.value
    let recv = 0
    let sent = 0
    nets.forEach((nic) => {
      recv += Number(nic.bytes_recv ?? 0)
      sent += Number(nic.bytes_sent ?? 0)
    })
    return { recv, sent }
  })

  const cpuOption = computed(() =>
    chartOption(
      [{ name: t('ops.monitorPage.cpuUsage'), data: data.value.series.map(cpuPercent) }],
      labels.value,
      { max: 100, unit: '%' },
    ),
  )

  const loadOption = computed(() =>
    chartOption(
      [
        { name: '1m', data: data.value.series.map((s) => Number(s.loadAverage?.[0] ?? s.load_average?.[0] ?? 0)) },
        { name: '5m', data: data.value.series.map((s) => Number(s.loadAverage?.[1] ?? s.load_average?.[1] ?? 0)) },
        { name: '15m', data: data.value.series.map((s) => Number(s.loadAverage?.[2] ?? s.load_average?.[2] ?? 0)) },
      ],
      labels.value,
    ),
  )

  const memoryOption = computed(() =>
    chartOption(
      [
        { name: t('ops.monitorPage.memoryUsage'), data: data.value.series.map((s) => Number(s.memory?.percent ?? 0)) },
        { name: 'Swap', data: data.value.series.map((s) => Number(s.swap?.percent ?? 0)) },
      ],
      labels.value,
      { max: 100, unit: '%' },
    ),
  )

  const diskUsageOption = computed(() => {
    let series: { name: string; data: number[] }[] = []
    if (selectedDisk.value === 'all') {
      series = [
        {
          name: t('ops.monitorPage.total'),
          data: data.value.series.map((sample) => {
            const disks = sample.disks || []
            if (!disks.length) return 0
            const used = disks.reduce((sum, d) => sum + Number(d.used || 0), 0)
            const total = disks.reduce((sum, d) => sum + Number(d.total || 0), 0)
            return total > 0 ? Math.round((used / total) * 100) : 0
          }),
        },
      ]
    } else {
      series = [
        {
          name: selectedDisk.value,
          data: data.value.series.map((sample) => {
            const disk = sample.disks?.find(
              (d) => d.mountpoint === selectedDisk.value || d.device === selectedDisk.value,
            )
            return Number(disk?.percent ?? 0)
          }),
        },
      ]
    }
    return chartOption(series, labels.value, { max: 100, unit: '%' })
  })

  const diskThroughputOption = computed(() => {
    const allSeries = [
      ...diffSeries(data.value.series, 'disk_io', 'read_bytes').map((item) => ({
        name: `${item.name} read`,
        data: item.data.map((v) => Math.round(v / 1024)),
      })),
      ...diffSeries(data.value.series, 'disk_io', 'write_bytes').map((item) => ({
        name: `${item.name} write`,
        data: item.data.map((v) => Math.round(v / 1024)),
      })),
    ]
    const series =
      selectedDisk.value === 'all'
        ? allSeries
        : allSeries.filter((s) => s.name.startsWith(selectedDisk.value))
    return chartOption(series, labels.value, { style: 'area' })
  })

  const diskIopsOption = computed(() => {
    const allSeries = [
      ...diffSeries(data.value.series, 'disk_io', 'read_count').map((item) => ({
        name: `${item.name} read`,
        data: item.data,
      })),
      ...diffSeries(data.value.series, 'disk_io', 'write_count').map((item) => ({
        name: `${item.name} write`,
        data: item.data,
      })),
    ]
    const series =
      selectedDisk.value === 'all'
        ? allSeries
        : allSeries.filter((s) => s.name.startsWith(selectedDisk.value))
    return chartOption(series, labels.value, { style: 'area' })
  })

  const networkBytesOption = computed(() => {
    const allSeries = [
      ...diffSeries(data.value.series, 'networks', 'bytes_recv').map((item) => ({
        name: `${item.name} in`,
        data: item.data.map((v) => Math.round(v / 1024)),
      })),
      ...diffSeries(data.value.series, 'networks', 'bytes_sent').map((item) => ({
        name: `${item.name} out`,
        data: item.data.map((v) => Math.round(v / 1024)),
      })),
    ]
    const series =
      selectedNetwork.value === 'all'
        ? allSeries
        : allSeries.filter((s) => s.name.startsWith(selectedNetwork.value))
    return chartOption(series, labels.value, { style: 'area' })
  })

  const networkPacketsOption = computed(() => {
    const allSeries = [
      ...diffSeries(data.value.series, 'networks', 'packets_recv').map((item) => ({
        name: `${item.name} in`,
        data: item.data,
      })),
      ...diffSeries(data.value.series, 'networks', 'packets_sent').map((item) => ({
        name: `${item.name} out`,
        data: item.data,
      })),
    ]
    const series =
      selectedNetwork.value === 'all'
        ? allSeries
        : allSeries.filter((s) => s.name.startsWith(selectedNetwork.value))
    return chartOption(series, labels.value, { style: 'area' })
  })

  return {
    current,
    currentDisks,
    currentNetworks,
    uniqueDiskNames,
    uniqueNetworkNames,
    totalDiskUsage,
    totalNetworkBytes,
    cpuOption,
    loadOption,
    memoryOption,
    diskUsageOption,
    diskThroughputOption,
    diskIopsOption,
    networkBytesOption,
    networkPacketsOption,
  }
}
