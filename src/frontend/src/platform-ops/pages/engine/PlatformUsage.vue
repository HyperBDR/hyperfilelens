<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { use } from 'echarts/core'
import { LineChart } from 'echarts/charts'
import { GridComponent, TooltipComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import VChart from 'vue-echarts'
import { ElMessage } from 'element-plus'
import {
  Activity,
  Building2,
  CircleDollarSign,
  Coins,
  Cpu,
  RefreshCw,
  Search,
} from 'lucide-vue-next'
import HflPagination from '../../../components/HflPagination.vue'
import OpsStatCard from '../../../components/ops/OpsStatCard.vue'
import { useResponsiveDrawerWidth } from '../../../composables/useResponsiveDrawerWidth'
import { apiErrorMessage } from '../../../lib/api'
import { formatLocalDateTime } from '../../../lib/dateTime'
import PlatformOpsOrgLink from '../../components/PlatformOpsOrgLink.vue'
import PlatformOpsStatusPill from '../../components/PlatformOpsStatusPill.vue'
import PlatformOpsUserLink from '../../components/PlatformOpsUserLink.vue'
import {
  fetchPlatformAiUsage,
  type PlatformAiOrganizationUsage,
  type PlatformAiUsagePayload,
  type PlatformAiUsageRun,
} from '../../lib/platformOpsApi'

use([CanvasRenderer, LineChart, GridComponent, TooltipComponent])

const emptySummary = {
  estimated_cost: 0,
  cost_currency: 'USD',
  total_tokens: 0,
  prompt_tokens: 0,
  completion_tokens: 0,
  cached_tokens: 0,
  reasoning_tokens: 0,
  model_calls: 0,
  requests: 0,
  successful_runs: 0,
  failed_runs: 0,
  success_rate: 0,
  organizations: 0,
  users: 0,
}

const loading = ref(false)
const data = ref<PlatformAiUsagePayload | null>(null)
const chartMetric = ref<'requests' | 'tokens' | 'cost'>('requests')
const periodPreset = ref<'today' | '7d' | '30d' | 'month' | 'custom'>('today')
const customRange = ref<[string, string] | null>(null)
const selected = ref<PlatformAiUsageRun | null>(null)
const drawerOpen = ref(false)
const { drawerSize } = useResponsiveDrawerWidth(3)
const pagination = reactive({ page: 1, pageSize: 20, count: 0 })
const filters = reactive({ search: '', org: '', status: '' })
const range = reactive({ startDate: '', endDate: '' })
let searchTimer: ReturnType<typeof setTimeout> | null = null
let clearingFilters = false

const summary = computed(() => data.value?.summary || emptySummary)
const organizationRows = computed(() => data.value?.by_organization || [])
const runRows = computed(() => data.value?.results || [])

function localDateValue(date: Date) {
  const year = date.getFullYear()
  const month = String(date.getMonth() + 1).padStart(2, '0')
  const day = String(date.getDate()).padStart(2, '0')
  return `${year}-${month}-${day}`
}

function presetRange(preset: 'today' | '7d' | '30d' | 'month') {
  const end = new Date()
  const start = new Date(end)
  if (preset === '7d') start.setDate(end.getDate() - 6)
  if (preset === '30d') start.setDate(end.getDate() - 29)
  if (preset === 'month') start.setDate(1)
  return [localDateValue(start), localDateValue(end)] as const
}

function selectPreset(preset: 'today' | '7d' | '30d' | 'month') {
  periodPreset.value = preset
  const values = presetRange(preset)
  range.startDate = values[0]
  range.endDate = values[1]
  customRange.value = null
  reloadFromFirstPage()
}

function applyCustomRange(value: [string, string] | null) {
  if (!value?.[0] || !value?.[1]) return
  periodPreset.value = 'custom'
  range.startDate = value[0]
  range.endDate = value[1]
  reloadFromFirstPage()
}

function formatNumber(value: number | null | undefined) {
  return new Intl.NumberFormat('en-US').format(Number(value || 0))
}

function formatCompact(value: number | null | undefined) {
  return new Intl.NumberFormat('en-US', {
    notation: 'compact',
    maximumFractionDigits: 2,
  }).format(Number(value || 0))
}

function formatAverage(value: number) {
  return new Intl.NumberFormat('en-US', { maximumFractionDigits: 2 }).format(value)
}

function formatCost(value: number | null | undefined, currency = 'USD') {
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency,
    minimumFractionDigits: 2,
    maximumFractionDigits: Number(value || 0) < 0.01 ? 6 : 4,
  }).format(Number(value || 0))
}

function formatTrendLabel(value: string) {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  const sameDay = range.startDate === range.endDate
  return new Intl.DateTimeFormat('en-US', sameDay
    ? { hour: '2-digit', minute: '2-digit', hour12: false }
    : { month: 'short', day: 'numeric' }).format(date)
}

function statusLabel(status: string) {
  if (['done', 'success', 'completed'].includes(status)) return 'Completed'
  if (['failed', 'error'].includes(status)) return 'Failed'
  if (status === 'cancelled') return 'Cancelled'
  if (status === 'queued') return 'Queued'
  if (['running', 'streaming'].includes(status)) return 'In Progress'
  return status || 'Unknown'
}

const tokenBreakdown = computed(() => {
  const total = Math.max(summary.value.total_tokens, 1)
  return [
    { label: 'Input Tokens', value: summary.value.prompt_tokens, color: '#6d5ef6' },
    { label: 'Output Tokens', value: summary.value.completion_tokens, color: '#16a085' },
    { label: 'Cached Input', value: summary.value.cached_tokens, color: '#2f7cf6' },
    { label: 'Reasoning', value: summary.value.reasoning_tokens, color: '#e39a24' },
  ].map((row) => ({ ...row, percent: Math.min(100, (row.value / total) * 100) }))
})

const chartOption = computed(() => {
  const rows = data.value?.trend || []
  const color = chartMetric.value === 'cost' ? '#e39a24' : chartMetric.value === 'tokens' ? '#6d5ef6' : '#2f7cf6'
  return {
    animationDuration: 240,
    grid: { left: 20, right: 18, top: 22, bottom: 12, containLabel: true },
    tooltip: {
      trigger: 'axis',
      formatter: (params: Array<{ axisValueLabel?: string; value?: number }>) => {
        const point = params[0]
        const value = Number(point?.value || 0)
        const formatted = chartMetric.value === 'cost'
          ? formatCost(value)
          : chartMetric.value === 'tokens'
            ? `${formatNumber(value)} tokens`
            : `${formatNumber(value)} requests`
        return `${point?.axisValueLabel || ''}\n${formatted}`
      },
    },
    xAxis: {
      type: 'category',
      boundaryGap: false,
      data: rows.map((row) => formatTrendLabel(row.bucket)),
      axisLine: { lineStyle: { color: '#d9dce5' } },
      axisTick: { show: false },
      axisLabel: { color: '#85899a', fontSize: 11 },
    },
    yAxis: {
      type: 'value',
      minInterval: chartMetric.value === 'cost' ? undefined : 1,
      axisLine: { show: false },
      axisTick: { show: false },
      splitLine: { lineStyle: { color: '#eceef4', type: 'dashed' } },
      axisLabel: {
        color: '#85899a',
        fontSize: 11,
        formatter: (value: number) => chartMetric.value === 'cost' ? `$${value}` : formatCompact(value),
      },
    },
    series: [{
      type: 'line',
      smooth: 0.3,
      symbol: 'circle',
      symbolSize: 6,
      showSymbol: rows.length < 16,
      lineStyle: { width: 2.5, color },
      itemStyle: { color },
      areaStyle: { color: `${color}18` },
      data: rows.map((row) => chartMetric.value === 'cost'
        ? row.estimated_cost
        : chartMetric.value === 'tokens'
          ? row.total_tokens
          : row.requests),
    }],
  }
})

async function load(showFeedback = false) {
  loading.value = true
  try {
    const payload = await fetchPlatformAiUsage({
      start_date: range.startDate,
      end_date: range.endDate,
      page: pagination.page,
      page_size: pagination.pageSize,
      ...filters,
    })
    data.value = payload
    pagination.count = payload.count
    if (showFeedback) ElMessage.success({ message: 'AI usage refreshed.', grouping: true })
  } catch (error) {
    ElMessage.error({ message: apiErrorMessage(error, 'Unable to load platform AI usage.'), grouping: true })
  } finally {
    loading.value = false
  }
}

function filterOrganization(row: PlatformAiOrganizationUsage) {
  filters.org = row.organization_key
}

function reloadFromFirstPage() {
  if (pagination.page !== 1) {
    pagination.page = 1
    return
  }
  void load()
}

function clearFilters() {
  clearingFilters = true
  if (searchTimer) clearTimeout(searchTimer)
  Object.assign(filters, { search: '', org: '', status: '' })
  void nextTick(() => {
    clearingFilters = false
    reloadFromFirstPage()
  })
}

function openRun(row: PlatformAiUsageRun) {
  selected.value = row
  drawerOpen.value = true
}

watch(() => [filters.org, filters.status], () => {
  if (!clearingFilters) reloadFromFirstPage()
})
watch(() => filters.search, () => {
  if (clearingFilters) return
  if (searchTimer) clearTimeout(searchTimer)
  searchTimer = setTimeout(() => {
    reloadFromFirstPage()
  }, 320)
})
watch(() => pagination.page, () => void load())
watch(() => pagination.pageSize, () => reloadFromFirstPage())

onMounted(() => {
  const values = presetRange('today')
  range.startDate = values[0]
  range.endDate = values[1]
  void load()
})

onBeforeUnmount(() => {
  if (searchTimer) clearTimeout(searchTimer)
})
</script>

<template>
  <div v-loading="loading && !data" class="platform-ai-usage">
    <div class="platform-ai-usage__lead">
      <div>
        <p>Monitor AI requests, tokens, cost, and reliability across all customer accounts.</p>
        <span>{{ summary.organizations }} active accounts · {{ summary.users }} active users in this period</span>
      </div>
      <div class="platform-ai-usage__period">
        <div class="platform-ai-usage__segments" aria-label="Usage period">
          <button :class="{ active: periodPreset === 'today' }" type="button" @click="selectPreset('today')">Today</button>
          <button :class="{ active: periodPreset === '7d' }" type="button" @click="selectPreset('7d')">Last 7 Days</button>
          <button :class="{ active: periodPreset === '30d' }" type="button" @click="selectPreset('30d')">Last 30 Days</button>
          <button :class="{ active: periodPreset === 'month' }" type="button" @click="selectPreset('month')">This Month</button>
        </div>
        <el-date-picker
          v-model="customRange"
          type="daterange"
          unlink-panels
          format="YYYY-MM-DD"
          value-format="YYYY-MM-DD"
          :name="['platform-usage-start-date', 'platform-usage-end-date']"
          range-separator="~"
          start-placeholder="Start date"
          end-placeholder="End date"
          @change="applyCustomRange"
        />
        <el-button class="hfl-refresh-button" title="Refresh" :disabled="loading" @click="load(true)">
          <RefreshCw :size="16" :class="{ 'is-spinning': loading }" />
        </el-button>
      </div>
    </div>

    <div class="platform-ai-usage__stats">
      <OpsStatCard label="Total Cost" :value="formatCost(summary.estimated_cost, summary.cost_currency)" :sub="`${summary.requests} AI requests`" accent="orange" accent-side="left"><template #icon><CircleDollarSign :size="16" /></template></OpsStatCard>
      <OpsStatCard label="AI Requests" :value="formatNumber(summary.requests)" :sub="`${summary.failed_runs} failed`" accent="blue" accent-side="left" :pulse="summary.failed_runs > 0"><template #icon><Activity :size="16" /></template></OpsStatCard>
      <OpsStatCard label="Model Calls" :value="formatNumber(summary.model_calls)" :sub="`${formatAverage(summary.requests ? summary.model_calls / summary.requests : 0)} per request`" accent="indigo" accent-side="left"><template #icon><Cpu :size="16" /></template></OpsStatCard>
      <OpsStatCard label="Total Tokens" :value="formatCompact(summary.total_tokens)" :sub="`${formatCompact(summary.prompt_tokens)} input`" accent="pink" accent-side="left"><template #icon><Coins :size="16" /></template></OpsStatCard>
      <OpsStatCard label="Success Rate" :value="`${summary.success_rate}%`" :sub="`${summary.successful_runs} successful`" :accent="summary.failed_runs ? 'orange' : 'green'" accent-side="left"><template #icon><Building2 :size="16" /></template></OpsStatCard>
    </div>

    <div class="platform-ai-usage__analysis-grid">
      <section class="platform-ai-usage__panel platform-ai-usage__trend">
        <header><div><h2>Platform Usage Trend</h2><p>Aggregated across all matching accounts</p></div><div class="platform-ai-usage__segments platform-ai-usage__segments--small"><button :class="{ active: chartMetric === 'requests' }" type="button" @click="chartMetric = 'requests'">Requests</button><button :class="{ active: chartMetric === 'tokens' }" type="button" @click="chartMetric = 'tokens'">Tokens</button><button :class="{ active: chartMetric === 'cost' }" type="button" @click="chartMetric = 'cost'">Cost</button></div></header>
        <VChart v-if="data?.trend.length" class="platform-ai-usage__chart" :option="chartOption" autoresize />
        <el-empty v-else description="No AI usage for this period" :image-size="68" />
      </section>
      <section class="platform-ai-usage__panel platform-ai-usage__tokens">
        <header><div><h2>Token Breakdown</h2><p>{{ formatNumber(summary.total_tokens) }} total tokens</p></div></header>
        <div class="platform-ai-usage__token-list"><div v-for="row in tokenBreakdown" :key="row.label"><div><span>{{ row.label }}</span><strong>{{ formatCompact(row.value) }}</strong></div><el-progress :percentage="row.percent" :show-text="false" :stroke-width="6" :color="row.color" /></div></div>
      </section>
    </div>

    <section class="platform-ai-usage__panel">
      <header><div><h2>Usage by Account</h2><p>Compare adoption, cost, and reliability across customer accounts</p></div></header>
      <el-table :data="organizationRows" stripe class="hfl-list-table" row-key="organization_id">
        <el-table-column label="Account" min-width="210"><template #default="{ row }"><button type="button" class="platform-ai-usage__account-button" @click="filterOrganization(row)">{{ row.organization_name }}</button><span class="platform-ai-usage__cell-meta">{{ row.organization_key }}</span></template></el-table-column>
        <el-table-column prop="users" label="Users" width="90" />
        <el-table-column prop="requests" label="Requests" width="105" />
        <el-table-column prop="model_calls" label="Model Calls" width="115" />
        <el-table-column label="Tokens" width="120"><template #default="{ row }">{{ formatCompact(row.total_tokens) }}</template></el-table-column>
        <el-table-column label="Success Rate" width="130"><template #default="{ row }"><span :class="{ 'is-attention': row.failed_runs > 0 }">{{ row.success_rate }}%</span></template></el-table-column>
        <el-table-column label="Cost" width="130"><template #default="{ row }">{{ formatCost(row.estimated_cost) }}</template></el-table-column>
        <template #empty><el-empty description="No account usage for this period" :image-size="68" /></template>
      </el-table>
    </section>

    <section class="platform-ai-usage__panel">
      <header><div><h2>AI Request History</h2><p>Investigate individual platform AI runs</p></div></header>
      <div class="platform-ai-usage__filters">
        <el-input v-model="filters.search" clearable placeholder="Search account, user, question, or source"><template #prefix><Search :size="15" /></template></el-input>
        <el-select v-model="filters.org" clearable filterable placeholder="Account"><el-option v-for="org in data?.organization_options || []" :key="org.key" :label="org.name" :value="org.key" /></el-select>
        <el-select v-model="filters.status" clearable placeholder="Status"><el-option v-for="status in data?.status_options || []" :key="status" :label="statusLabel(status)" :value="status" /></el-select>
        <el-button v-if="filters.search || filters.org || filters.status" text @click="clearFilters">Reset</el-button>
      </div>
      <el-table :data="runRows" stripe class="hfl-list-table" row-key="run_uuid">
        <el-table-column label="Time" width="170"><template #default="{ row }">{{ formatLocalDateTime(row.time, '—') }}</template></el-table-column>
        <el-table-column label="Request" min-width="280"><template #default="{ row }"><button type="button" class="platform-ai-usage__request-button" @click="openRun(row)">{{ row.question || row.chat_title || 'Untitled request' }}</button><span class="platform-ai-usage__cell-meta">{{ row.backup_source_name || row.chat_title || '—' }}</span></template></el-table-column>
        <el-table-column label="Account" min-width="150"><template #default="{ row }"><PlatformOpsOrgLink :org-id="row.organization_id" :org-key="row.organization_key" /></template></el-table-column>
        <el-table-column label="User" min-width="190"><template #default="{ row }"><PlatformOpsUserLink :user-id="row.user_id" :display-name="row.user_email || 'Deleted user'" /></template></el-table-column>
        <el-table-column label="Status" width="115"><template #default="{ row }"><PlatformOpsStatusPill :status="statusLabel(row.status)" /></template></el-table-column>
        <el-table-column label="Calls" width="80"><template #default="{ row }">{{ formatNumber(row.model_calls) }}</template></el-table-column>
        <el-table-column label="Tokens" width="105"><template #default="{ row }">{{ formatCompact(row.total_tokens) }}</template></el-table-column>
        <el-table-column label="Cost" width="120"><template #default="{ row }">{{ formatCost(row.estimated_cost, row.cost_currency) }}</template></el-table-column>
        <template #empty><el-empty description="No AI requests match the current filters" :image-size="68" /></template>
      </el-table>
      <div class="platform-ai-usage__pagination"><HflPagination v-model:current-page="pagination.page" v-model:page-size="pagination.pageSize" :total="pagination.count" /></div>
    </section>

    <el-drawer v-model="drawerOpen" :size="drawerSize" destroy-on-close>
      <template #header><div class="platform-monitoring-drawer__header"><h2>AI Request</h2><p>{{ selected?.organization_name }} · {{ selected?.status }}</p></div></template>
      <template v-if="selected"><section class="platform-monitoring-drawer__section"><h3>Request Context</h3><div class="platform-monitoring-drawer__grid"><div class="platform-monitoring-drawer__field"><span>Time</span><strong>{{ formatLocalDateTime(selected.time, '—') }}</strong></div><div class="platform-monitoring-drawer__field"><span>User</span><strong>{{ selected.user_email || 'Deleted user' }}</strong></div><div class="platform-monitoring-drawer__field"><span>Model Calls</span><strong>{{ formatNumber(selected.model_calls) }}</strong></div><div class="platform-monitoring-drawer__field"><span>Total Tokens</span><strong>{{ formatNumber(selected.total_tokens) }}</strong></div><div class="platform-monitoring-drawer__field"><span>Estimated Cost</span><strong>{{ formatCost(selected.estimated_cost, selected.cost_currency) }}</strong></div><div class="platform-monitoring-drawer__field"><span>Backup Source</span><strong>{{ selected.backup_source_name || '—' }}</strong></div></div></section><section class="platform-monitoring-drawer__section"><h3>Question</h3><p class="platform-monitoring-drawer__message">{{ selected.question || 'No question recorded.' }}</p></section><section v-if="selected.error" class="platform-monitoring-drawer__section"><h3>Error</h3><pre class="platform-monitoring-drawer__message">{{ selected.error }}</pre></section></template>
    </el-drawer>
  </div>
</template>

<style scoped>
.platform-ai-usage { display: flex; flex: 1 1 auto; min-width: 0; min-height: 0; flex-direction: column; gap: 16px; overflow-y: auto; }
.platform-ai-usage > * { flex-shrink: 0; }
.platform-ai-usage__lead { display: flex; align-items: flex-start; justify-content: space-between; gap: 20px; }
.platform-ai-usage__lead p { margin: 0; color: var(--page-text-secondary, #70707e); font-size: 13px; line-height: 1.5; }
.platform-ai-usage__lead span { display: block; margin-top: 4px; color: var(--color-text-tertiary, #9c9caa); font-size: 11px; }
.platform-ai-usage__period { display: flex; align-items: center; gap: 8px; }
.platform-ai-usage__period :deep(.el-date-editor) { width: 250px; }
.platform-ai-usage__segments { display: inline-flex; padding: 3px; border-radius: 8px; background: var(--color-grey-2, #f5f5f7); }
.platform-ai-usage__segments button { min-height: 30px; padding: 0 12px; border: 0; border-radius: 6px; background: transparent; color: var(--color-text-secondary, #70707e); cursor: pointer; font: inherit; font-size: 12px; }
.platform-ai-usage__segments button.active { background: var(--color-card-bg, #fff); color: var(--color-primary, #6d5ef6); box-shadow: 0 1px 3px rgba(15, 23, 42, 0.08); }
.platform-ai-usage__segments--small button { min-height: 27px; padding-inline: 10px; }
.platform-ai-usage__stats { display: grid; grid-template-columns: repeat(5, minmax(0, 1fr)); gap: 12px; }
.platform-ai-usage__analysis-grid { display: grid; grid-template-columns: minmax(0, 2fr) minmax(280px, 0.8fr); gap: 16px; }
.platform-ai-usage__panel { min-width: 0; overflow: hidden; border: 1px solid var(--color-border, #e9e9ef); border-radius: 10px; background: var(--color-card-bg, #fff); }
.platform-ai-usage__panel > header { display: flex; min-height: 58px; align-items: center; justify-content: space-between; gap: 12px; padding: 10px 16px; border-bottom: 1px solid var(--color-border-light, #f2f2f6); }
.platform-ai-usage__panel h2 { margin: 0; color: var(--color-text-title, #1c1c26); font-size: 14px; font-weight: 650; }
.platform-ai-usage__panel header p { margin: 3px 0 0; color: var(--color-text-secondary, #70707e); font-size: 11px; }
.platform-ai-usage__chart { height: 280px; }
.platform-ai-usage__tokens { min-height: 340px; }
.platform-ai-usage__token-list { display: grid; gap: 20px; padding: 24px 20px; }
.platform-ai-usage__token-list > div > div { display: flex; align-items: center; justify-content: space-between; margin-bottom: 8px; color: var(--color-text-secondary, #70707e); font-size: 12px; }
.platform-ai-usage__token-list strong { color: var(--color-text-title, #1c1c26); font-size: 13px; }
.platform-ai-usage__filters { display: grid; grid-template-columns: minmax(240px, 1fr) 180px 150px auto; gap: 8px; padding: 12px 16px; border-bottom: 1px solid var(--color-border-light, #f2f2f6); }
.platform-ai-usage__account-button,.platform-ai-usage__request-button { display: block; max-width: 100%; padding: 0; overflow: hidden; border: 0; background: transparent; color: var(--color-text-title, #1c1c26); cursor: pointer; font: inherit; font-weight: 600; text-align: left; text-overflow: ellipsis; white-space: nowrap; }
.platform-ai-usage__account-button:hover,.platform-ai-usage__request-button:hover { color: var(--color-primary, #6d5ef6); text-decoration: underline; text-underline-offset: 3px; }
.platform-ai-usage__cell-meta { display: block; margin-top: 2px; overflow: hidden; color: var(--color-text-secondary, #70707e); font-size: 11px; text-overflow: ellipsis; white-space: nowrap; }
.platform-ai-usage .is-attention { color: var(--color-warning, #e08b0b); font-weight: 600; }
.platform-ai-usage__pagination { padding: 10px 16px; border-top: 1px solid var(--color-border-light, #f2f2f6); }
@media (max-width: 1500px) { .platform-ai-usage__stats { grid-template-columns: repeat(3, minmax(0, 1fr)); } }
@media (max-width: 1100px) { .platform-ai-usage__lead { flex-direction: column; } .platform-ai-usage__period { width: 100%; flex-wrap: wrap; } .platform-ai-usage__analysis-grid { grid-template-columns: 1fr; } }
@media (max-width: 760px) { .platform-ai-usage__stats { grid-template-columns: 1fr; } .platform-ai-usage__period,.platform-ai-usage__segments { width: 100%; } .platform-ai-usage__segments button { flex: 1; padding-inline: 4px; } .platform-ai-usage__period :deep(.el-date-editor) { width: calc(100% - 44px); } .platform-ai-usage__filters { grid-template-columns: 1fr; } .platform-ai-usage__panel { overflow-x: auto; } }
@media (prefers-reduced-motion: reduce) { .platform-ai-usage * { animation-duration: 0.01ms !important; transition-duration: 0.01ms !important; } }
</style>
