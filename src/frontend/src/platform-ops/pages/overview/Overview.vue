<script setup lang="ts">
import { computed, onMounted, ref, type Component } from 'vue'
import { useI18n } from 'vue-i18n'
import { RouterLink } from 'vue-router'
import { LineChart } from 'echarts/charts'
import { GridComponent, LegendComponent, TooltipComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import { use } from 'echarts/core'
import VChart from 'vue-echarts'
import {
  Activity,
  AlertTriangle,
  ArrowRight,
  Bot,
  Building2,
  CheckCircle2,
  CircleX,
  Clock3,
  HardDrive,
  ServerOff,
  TriangleAlert,
} from 'lucide-vue-next'
import ModulePage from '../../../components/ModulePage.vue'
import { formatLocalDateTime } from '../../../lib/dateTime'
import { apiErrorMessage } from '../../../lib/api'
import PlatformOpsRefreshButton from '../../components/PlatformOpsRefreshButton.vue'
import { usePlatformOpsSideNav } from '../../composables/usePlatformOpsSideNav'
import {
  fetchPlatformOverview,
  type PlatformOverviewMetricValue,
  type PlatformOverviewPayload,
} from '../../lib/platformOpsApi'

use([CanvasRenderer, LineChart, GridComponent, LegendComponent, TooltipComponent])

const { t, locale } = useI18n()
const sideNav = usePlatformOpsSideNav()

const payload = ref<PlatformOverviewPayload | null>(null)
const loading = ref(false)
const loadError = ref('')
const selectedHours = ref(24)

const rangeOptions = computed(() => [
  { value: 1, label: t('platformOps.overview.range1h') },
  { value: 24, label: t('platformOps.overview.range24h') },
  { value: 168, label: t('platformOps.overview.range7d') },
  { value: 720, label: t('platformOps.overview.range30d') },
])

function metric(key: string): PlatformOverviewMetricValue {
  return payload.value?.metrics[key] ?? 0
}

function metricNumber(key: string): number {
  const value = Number(metric(key))
  return Number.isFinite(value) ? value : 0
}

function formatPercent(value: PlatformOverviewMetricValue): string {
  if (value === null || value === undefined || value === '') return '—'
  const number = Number(value)
  return Number.isFinite(number) ? `${number.toFixed(number % 1 ? 1 : 0)}%` : '—'
}

type KpiCard = {
  key: string
  label: string
  value: string | number
  detail: string
  tone: 'danger' | 'warning' | 'info' | 'neutral'
  icon: Component
  to?: string | { path: string; query?: Record<string, string> }
}

const kpis = computed<KpiCard[]>(() => [
  {
    key: 'incidents',
    label: t('platformOps.overview.firingIncidents'),
    value: metricNumber('alerts_firing'),
    detail: t('platformOps.overview.acknowledgedCount', {
      count: metricNumber('alerts_acknowledged'),
    }),
    tone: metricNumber('alerts_firing') > 0 ? 'danger' : 'neutral',
    icon: AlertTriangle,
    to: { path: '/platform-ops/monitoring/incidents', query: { status: 'firing' } },
  },
  {
    key: 'tasks',
    label: t('platformOps.overview.failedTasks'),
    value: metricNumber('tasks_failed_in_range'),
    detail: rangeOptions.value.find((option) => option.value === selectedHours.value)?.label || '',
    tone: metricNumber('tasks_failed_in_range') > 0 ? 'danger' : 'neutral',
    icon: CircleX,
    to: { path: '/platform-ops/monitoring/tasks', query: { status: 'failed' } },
  },
  {
    key: 'nodes',
    label: t('platformOps.overview.offlineNodes'),
    value: metricNumber('nodes_offline'),
    detail: t('platformOps.overview.outdatedAgentsCount', {
      count: metricNumber('outdated_agents'),
    }),
    tone: metricNumber('nodes_offline') > 0 ? 'warning' : 'neutral',
    icon: ServerOff,
    to: { path: '/platform-ops/monitoring/nodes', query: { status: 'offline' } },
  },
  {
    key: 'repositories',
    label: t('platformOps.overview.repositoriesAtRisk'),
    value: metricNumber('repositories_at_risk'),
    detail:
      metric('repository_max_usage_percent') === null
        ? t('platformOps.overview.noCapacityData')
        : t('platformOps.overview.highestUsage', {
            value: formatPercent(metric('repository_max_usage_percent')),
          }),
    tone: metricNumber('repositories_at_risk') > 0 ? 'warning' : 'neutral',
    icon: HardDrive,
  },
])

const health = computed(() => payload.value?.system_health)
const overallStatus = computed(() => health.value?.overall_status || 'degraded')
const overallLabel = computed(() => t(`platformOps.overview.health.${overallStatus.value}`))

const activityChartOption = computed(() => {
  const rows = payload.value?.activity_series || []
  const formatter = new Intl.DateTimeFormat(locale.value, {
    month: selectedHours.value >= 168 ? 'short' : undefined,
    day: selectedHours.value >= 168 ? 'numeric' : undefined,
    hour: selectedHours.value < 168 ? '2-digit' : undefined,
    minute: selectedHours.value <= 24 ? '2-digit' : undefined,
  })
  return {
    animationDuration: 220,
    color: ['#ef4444', '#6d5ef6'],
    tooltip: { trigger: 'axis' },
    legend: {
      top: 0,
      right: 0,
      itemWidth: 18,
      itemHeight: 3,
      textStyle: { color: '#86909c', fontSize: 11 },
    },
    grid: { left: 36, right: 16, top: 38, bottom: 28 },
    xAxis: {
      type: 'category',
      boundaryGap: false,
      data: rows.map((row) => formatter.format(new Date(row.started_at))),
      axisLine: { lineStyle: { color: '#e5e7eb' } },
      axisTick: { show: false },
      axisLabel: { color: '#86909c', fontSize: 10, hideOverlap: true },
    },
    yAxis: {
      type: 'value',
      minInterval: 1,
      axisLine: { show: false },
      axisTick: { show: false },
      axisLabel: { color: '#86909c', fontSize: 10 },
      splitLine: { lineStyle: { color: '#eef0f4' } },
    },
    series: [
      {
        name: t('platformOps.overview.incidents'),
        type: 'line',
        smooth: 0.25,
        symbol: 'none',
        lineStyle: { width: 2 },
        data: rows.map((row) => row.alerts),
      },
      {
        name: t('platformOps.overview.failedTasks'),
        type: 'line',
        smooth: 0.25,
        symbol: 'none',
        lineStyle: { width: 2 },
        data: rows.map((row) => row.failed_tasks),
      },
    ],
  }
})

const needsAttention = computed(() => [
  {
    key: 'agents',
    label: t('platformOps.overview.outdatedAgents'),
    value: metricNumber('outdated_agents'),
    tone: 'warning',
    to: '/platform-ops/platform/agent-releases',
  },
  {
    key: 'capacity',
    label: t('platformOps.overview.repositoryCapacity'),
    value: metricNumber('repositories_capacity_warning'),
    tone: 'warning',
  },
  {
    key: 'notifications',
    label: t('platformOps.overview.notificationFailures'),
    value: metricNumber('notifications_failed_in_range'),
    tone: 'danger',
    to: '/platform-ops/monitoring/notification-deliveries?status=failed',
  },
  {
    key: 'subscriptions',
    label: t('platformOps.overview.expiringAccounts'),
    value: metricNumber('expiring_accounts'),
    tone: 'warning',
    to: '/platform-ops/orgs',
  },
])

const platformSummary = computed(() => [
  {
    key: 'accounts',
    label: t('platformOps.overview.activeAccounts'),
    value: metricNumber('organizations_active'),
    icon: Building2,
  },
  {
    key: 'tasks',
    label: t('platformOps.overview.runningTasks'),
    value: metricNumber('tasks_running'),
    icon: Activity,
  },
  {
    key: 'ai',
    label: t('platformOps.overview.aiSuccessRate'),
    value: formatPercent(metric('ai_success_rate')),
    icon: Bot,
  },
])

function statusLabel(status: string): string {
  return t(`platformOps.overview.health.${status}`)
}

function severityClass(severity: string): string {
  const normalized = severity.toLowerCase()
  if (normalized === 'critical' || normalized === 'error') return 'overview-pill--danger'
  if (normalized === 'warning' || normalized === 'high') return 'overview-pill--warning'
  return 'overview-pill--info'
}

function displayTime(value?: string | null): string {
  return formatLocalDateTime(value, '—')
}

async function load() {
  loading.value = true
  loadError.value = ''
  try {
    payload.value = await fetchPlatformOverview(selectedHours.value)
  } catch (error) {
    loadError.value = apiErrorMessage(error, t('platformOps.overview.loadFailed'))
  } finally {
    loading.value = false
  }
}

function onRangeChange() {
  void load()
}

onMounted(load)
</script>

<template>
  <ModulePage
    :menus="sideNav"
    body-fill
  >
    <div
      class="platform-overview"
      :aria-busy="loading"
    >
      <div class="platform-overview__toolbar">
        <div>
          <p class="platform-overview__subtitle">
            {{ t('platformOps.overview.subtitle') }}
          </p>
          <p
            v-if="payload"
            class="platform-overview__updated"
          >
            {{ t('platformOps.overview.updatedAt', { time: displayTime(payload.generated_at) }) }}
          </p>
        </div>
        <div class="platform-overview__controls">
          <el-select
            v-model="selectedHours"
            class="platform-overview__range"
            :aria-label="t('platformOps.overview.timeRange')"
            :disabled="loading"
            @change="onRangeChange"
          >
            <el-option
              v-for="option in rangeOptions"
              :key="option.value"
              :label="option.label"
              :value="option.value"
            />
          </el-select>
          <PlatformOpsRefreshButton
            :loading="loading"
            @click="load"
          />
        </div>
      </div>

      <div
        v-if="loadError && !payload"
        class="platform-overview__error"
        role="alert"
      >
        <TriangleAlert
          :size="18"
          aria-hidden="true"
        />
        <span>{{ loadError }}</span>
        <el-button
          size="small"
          @click="load"
        >
          {{ t('common.retry') }}
        </el-button>
      </div>

      <template v-if="payload">
        <section
          class="overview-health-banner"
          :class="`overview-health-banner--${overallStatus}`"
          :aria-label="t('platformOps.overview.platformStatus')"
        >
          <component
            :is="overallStatus === 'healthy' ? CheckCircle2 : TriangleAlert"
            :size="22"
            class="overview-health-banner__icon"
            aria-hidden="true"
          />
          <div class="overview-health-banner__body">
            <strong>{{ overallLabel }}</strong>
            <span>
              {{
                t('platformOps.overview.healthSummary', {
                  healthy: health?.healthy_count || 0,
                  degraded: health?.degraded_count || 0,
                  unavailable: health?.unavailable_count || 0,
                })
              }}
            </span>
          </div>
          <RouterLink
            class="overview-text-link"
            to="/platform-ops/monitoring/system-health"
          >
            {{ t('platformOps.overview.viewMonitor') }}
            <ArrowRight
              :size="14"
              aria-hidden="true"
            />
          </RouterLink>
        </section>

        <section
          class="overview-kpi-grid"
          :aria-label="t('platformOps.overview.keyMetrics')"
        >
          <component
            :is="card.to ? RouterLink : 'article'"
            v-for="card in kpis"
            :key="card.key"
            :to="card.to"
            class="overview-kpi-card"
            :class="[`overview-kpi-card--${card.tone}`, { 'overview-kpi-card--link': card.to }]"
          >
            <span class="overview-kpi-card__icon"><component
              :is="card.icon"
              :size="18"
            /></span>
            <span class="overview-kpi-card__body">
              <span class="overview-kpi-card__label">{{ card.label }}</span>
              <strong>{{ card.value }}</strong>
              <span class="overview-kpi-card__detail">{{ card.detail }}</span>
            </span>
            <ArrowRight
              v-if="card.to"
              :size="15"
              class="overview-kpi-card__arrow"
              aria-hidden="true"
            />
          </component>
        </section>

        <div class="overview-grid overview-grid--activity">
          <section class="overview-panel">
            <header class="overview-panel__header">
              <div>
                <h2>{{ t('platformOps.overview.operationalActivity') }}</h2>
                <p>{{ rangeOptions.find((option) => option.value === selectedHours)?.label }}</p>
              </div>
            </header>
            <VChart
              class="overview-activity-chart"
              :option="activityChartOption"
              autoresize
            />
          </section>

          <section class="overview-panel">
            <header class="overview-panel__header">
              <h2>{{ t('platformOps.overview.serviceHealth') }}</h2>
            </header>
            <ul class="overview-service-list">
              <li
                v-for="service in health?.services || []"
                :key="service.key"
              >
                <span class="overview-service-list__name">{{ service.label }}</span>
                <span
                  v-if="service.detail"
                  class="overview-service-list__detail"
                >{{ service.detail }}</span>
                <span
                  class="overview-status"
                  :class="`overview-status--${service.status}`"
                >
                  <span aria-hidden="true" />
                  {{ statusLabel(service.status) }}
                </span>
              </li>
            </ul>
            <RouterLink
              class="overview-text-link overview-panel__footer-link"
              to="/platform-ops/monitoring/system-health"
            >
              {{ t('platformOps.overview.viewMonitor') }}
              <ArrowRight
                :size="14"
                aria-hidden="true"
              />
            </RouterLink>
          </section>
        </div>

        <div class="overview-grid">
          <section class="overview-panel overview-panel--table">
            <header class="overview-panel__header">
              <h2>{{ t('platformOps.overview.recentIncidents') }}</h2>
              <RouterLink
                class="overview-text-link"
                to="/platform-ops/monitoring/incidents"
              >
                {{ t('platformOps.overview.viewAll') }}
                <ArrowRight
                  :size="14"
                  aria-hidden="true"
                />
              </RouterLink>
            </header>
            <div class="overview-table-wrap">
              <table class="overview-table">
                <thead>
                  <tr>
                    <th>{{ t('platformOps.monitoring.colSeverity') }}</th>
                    <th>{{ t('platformOps.overview.incident') }}</th>
                    <th>{{ t('platformOps.overview.account') }}</th>
                    <th>{{ t('platformOps.overview.updated') }}</th>
                  </tr>
                </thead>
                <tbody>
                  <tr
                    v-for="row in payload.recent_alerts"
                    :key="row.id"
                  >
                    <td>
                      <span
                        class="overview-pill"
                        :class="severityClass(row.severity)"
                      >{{ row.severity }}</span>
                    </td>
                    <td>
                      <span class="overview-table__primary">{{ row.title }}</span>
                      <span class="overview-table__secondary">{{ row.resource_name || row.resource_type || '—' }}</span>
                    </td>
                    <td>{{ row.organization_key }}</td>
                    <td class="overview-table__time">
                      {{ displayTime(row.last_triggered_at || row.created_at) }}
                    </td>
                  </tr>
                  <tr v-if="!payload.recent_alerts.length">
                    <td
                      colspan="4"
                      class="overview-table__empty"
                    >
                      {{ t('platformOps.overview.noActiveIncidents') }}
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
          </section>

          <section class="overview-panel">
            <header class="overview-panel__header">
              <h2>{{ t('platformOps.overview.needsAttention') }}</h2>
            </header>
            <ul class="overview-attention-list">
              <li
                v-for="item in needsAttention"
                :key="item.key"
              >
                <component
                  :is="item.to ? RouterLink : 'div'"
                  :to="item.to"
                  class="overview-attention-list__item"
                >
                  <span
                    class="overview-attention-list__marker"
                    :class="`is-${item.tone}`"
                    aria-hidden="true"
                  />
                  <span>{{ item.label }}</span>
                  <strong>{{ item.value }}</strong>
                  <ArrowRight
                    v-if="item.to"
                    :size="14"
                    aria-hidden="true"
                  />
                </component>
              </li>
            </ul>
          </section>
        </div>

        <div class="overview-grid">
          <section class="overview-panel overview-panel--table">
            <header class="overview-panel__header">
              <h2>{{ t('platformOps.overview.recentFailedTasks') }}</h2>
              <RouterLink
                class="overview-text-link"
                :to="{ path: '/platform-ops/monitoring/tasks', query: { status: 'failed' } }"
              >
                {{ t('platformOps.overview.viewAll') }}
                <ArrowRight
                  :size="14"
                  aria-hidden="true"
                />
              </RouterLink>
            </header>
            <div class="overview-table-wrap">
              <table class="overview-table">
                <thead>
                  <tr>
                    <th>{{ t('platformOps.monitoring.colTask') }}</th>
                    <th>{{ t('platformOps.overview.account') }}</th>
                    <th>{{ t('platformOps.monitoring.colTaskType') }}</th>
                    <th>{{ t('platformOps.monitoring.colFinished') }}</th>
                  </tr>
                </thead>
                <tbody>
                  <tr
                    v-for="row in payload.recent_failed_tasks"
                    :key="row.id"
                  >
                    <td>
                      <RouterLink
                        class="overview-table__task-link"
                        :to="{
                          path: '/platform-ops/monitoring/tasks',
                          query: { status: 'failed', org: row.organization_key },
                        }"
                      >
                        <span class="overview-table__primary">{{ row.display_name }}</span>
                        <span class="overview-table__secondary">{{ row.error_message || row.status }}</span>
                      </RouterLink>
                    </td>
                    <td>{{ row.organization_key }}</td>
                    <td>{{ row.task_type }}</td>
                    <td class="overview-table__time">
                      {{ displayTime(row.finished_at || row.created_at) }}
                    </td>
                  </tr>
                  <tr v-if="!payload.recent_failed_tasks.length">
                    <td
                      colspan="4"
                      class="overview-table__empty"
                    >
                      {{ t('platformOps.overview.noFailedTasks') }}
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
          </section>

          <section class="overview-panel">
            <header class="overview-panel__header">
              <h2>{{ t('platformOps.overview.platformSummary') }}</h2>
            </header>
            <ul class="overview-summary-list">
              <li
                v-for="item in platformSummary"
                :key="item.key"
              >
                <span class="overview-summary-list__icon"><component
                  :is="item.icon"
                  :size="16"
                /></span>
                <span>{{ item.label }}</span>
                <strong>{{ item.value }}</strong>
              </li>
            </ul>
            <RouterLink
              class="overview-text-link overview-panel__footer-link"
              to="/platform-ops/orgs"
            >
              {{ t('platformOps.overview.viewAccounts') }}
              <ArrowRight
                :size="14"
                aria-hidden="true"
              />
            </RouterLink>
          </section>
        </div>
      </template>

      <div
        v-else-if="loading"
        class="overview-skeleton"
        aria-hidden="true"
      >
        <span class="overview-skeleton__banner" />
        <span
          v-for="index in 8"
          :key="index"
          class="overview-skeleton__card"
        />
      </div>

      <p
        v-if="loadError && payload"
        class="platform-overview__stale-warning"
        role="status"
      >
        <Clock3
          :size="15"
          aria-hidden="true"
        />
        {{ loadError }}
      </p>
    </div>
  </ModulePage>
</template>

<style scoped>
.platform-overview {
  display: flex;
  flex: 1 1 auto;
  min-width: 0;
  min-height: 0;
  flex-direction: column;
  gap: 16px;
  overflow-y: auto;
  padding-bottom: 8px;
}

.platform-overview__toolbar {
  display: flex;
  flex-wrap: wrap;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
}

.platform-overview__subtitle,
.platform-overview__updated {
  margin: 0;
  color: var(--color-text-secondary, #64748b);
  font-size: 13px;
  line-height: 1.5;
}

.platform-overview__updated {
  margin-top: 2px;
  font-size: 11px;
  color: var(--page-text-secondary, var(--color-text-secondary, #64748b));
}

.platform-overview__controls {
  display: flex;
  align-items: center;
  gap: 8px;
}

.platform-overview__range {
  width: 154px;
}

.platform-overview__error,
.platform-overview__stale-warning {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 12px 14px;
  border: 1px solid var(--color-error-border, #fecaca);
  border-radius: 8px;
  background: var(--color-error-light, #fef2f2);
  color: var(--color-error, #dc2626);
  font-size: 13px;
}

.platform-overview__error span {
  flex: 1;
}

.platform-overview__stale-warning {
  position: sticky;
  bottom: 8px;
  align-self: flex-end;
  box-shadow: 0 6px 18px rgba(15, 23, 42, 0.12);
}

.overview-health-banner {
  display: flex;
  min-height: 68px;
  align-items: center;
  gap: 12px;
  padding: 12px 16px;
  border: 1px solid var(--color-success-border, #bbf7d0);
  border-radius: 10px;
  background: var(--color-success-light, #f0fdf4);
  color: var(--color-success, #15803d);
}

.overview-health-banner--degraded {
  border-color: var(--color-warning-border, #fde68a);
  background: var(--color-warning-light, #fffbeb);
  color: var(--color-warning-text, #8a5200);
}

.overview-health-banner--unavailable {
  border-color: var(--color-error-border, #fecaca);
  background: var(--color-error-light, #fef2f2);
  color: var(--color-error, #dc2626);
}

.overview-health-banner__icon {
  flex: 0 0 auto;
}

.overview-health-banner__body {
  display: flex;
  min-width: 0;
  flex: 1;
  flex-direction: column;
  gap: 2px;
}

.overview-health-banner__body strong {
  font-size: 14px;
  font-weight: 650;
  color: currentColor;
}

.overview-health-banner__body span {
  font-size: 12px;
  color: var(--color-text-secondary, #64748b);
}

.overview-text-link {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  color: var(--color-primary, #6d5ef6);
  font-size: 12px;
  font-weight: 600;
  text-decoration: none;
  white-space: nowrap;
}

.overview-text-link:hover,
.overview-text-link:focus-visible {
  text-decoration: underline;
  text-underline-offset: 3px;
}

.overview-kpi-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
}

.overview-kpi-card {
  display: flex;
  min-width: 0;
  min-height: 102px;
  align-items: flex-start;
  gap: 12px;
  padding: 15px;
  border: 1px solid var(--color-border, #e5e7eb);
  border-radius: 10px;
  background: var(--color-card-bg, #fff);
  color: var(--color-text-primary, #1d2129);
  text-decoration: none;
  box-shadow: 0 1px 2px rgba(15, 23, 42, 0.04);
  transition: border-color 150ms ease, box-shadow 150ms ease, transform 150ms ease;
}

.overview-kpi-card--link:hover,
.overview-kpi-card--link:focus-visible {
  border-color: color-mix(in srgb, var(--color-primary, #6d5ef6) 42%, transparent);
  box-shadow: 0 8px 20px rgba(15, 23, 42, 0.07);
  transform: translateY(-1px);
}

.overview-kpi-card__icon,
.overview-summary-list__icon {
  display: inline-flex;
  flex: 0 0 34px;
  width: 34px;
  height: 34px;
  align-items: center;
  justify-content: center;
  border-radius: 8px;
  background: var(--color-grey-2, #f5f5f7);
  color: var(--color-text-secondary, #64748b);
}

.overview-kpi-card--danger .overview-kpi-card__icon {
  background: var(--color-error-light, #fef2f2);
  color: var(--color-error, #dc2626);
}

.overview-kpi-card--warning .overview-kpi-card__icon {
  background: var(--color-warning-light, #fffbeb);
  color: var(--color-warning, #b45309);
}

.overview-kpi-card--info .overview-kpi-card__icon {
  background: var(--color-info-light, #eff6ff);
  color: var(--color-info, #2563eb);
}

.overview-kpi-card__body {
  display: flex;
  min-width: 0;
  flex: 1;
  flex-direction: column;
}

.overview-kpi-card__label {
  overflow: hidden;
  color: var(--color-text-secondary, #64748b);
  font-size: 12px;
  font-weight: 500;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.overview-kpi-card__body strong {
  margin-top: 5px;
  color: var(--color-text-title, #1d2129);
  font-size: 24px;
  font-weight: 650;
  line-height: 1.15;
}

.overview-kpi-card__detail {
  overflow: hidden;
  margin-top: 6px;
  color: var(--page-text-secondary, var(--color-text-secondary, #64748b));
  font-size: 11px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.overview-kpi-card__arrow {
  align-self: center;
  flex: 0 0 auto;
  color: var(--color-text-tertiary, #94a3b8);
}

.overview-grid {
  display: grid;
  grid-template-columns: minmax(0, 2fr) minmax(260px, 1fr);
  gap: 12px;
}

.overview-panel {
  min-width: 0;
  overflow: hidden;
  border: 1px solid var(--color-border, #e5e7eb);
  border-radius: 10px;
  background: var(--color-card-bg, #fff);
  box-shadow: 0 1px 2px rgba(15, 23, 42, 0.04);
}

.overview-panel__header {
  display: flex;
  min-height: 46px;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 11px 14px;
  border-bottom: 1px solid var(--color-border-light, #eef0f4);
}

.overview-panel__header h2 {
  margin: 0;
  color: var(--color-text-title, #1d2129);
  font-size: 13px;
  font-weight: 600;
  line-height: 20px;
}

.overview-panel__header p {
  margin: 1px 0 0;
  color: var(--page-text-secondary, var(--color-text-secondary, #64748b));
  font-size: 11px;
}

.overview-activity-chart {
  width: 100%;
  height: 238px;
}

.overview-service-list,
.overview-attention-list,
.overview-summary-list {
  margin: 0;
  padding: 0;
  list-style: none;
}

.overview-service-list li {
  display: grid;
  min-height: 40px;
  grid-template-columns: minmax(86px, 1fr) minmax(0, 1fr) auto;
  align-items: center;
  gap: 8px;
  padding: 0 14px;
  border-bottom: 1px solid var(--color-border-light, #eef0f4);
  font-size: 12px;
}

.overview-service-list__name {
  color: var(--color-text-title, #1d2129);
  font-weight: 500;
}

.overview-service-list__detail {
  overflow: hidden;
  color: var(--color-text-tertiary, #94a3b8);
  font-size: 10px;
  text-align: right;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.overview-status {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  color: var(--color-text-secondary, #64748b);
  font-size: 10px;
  font-weight: 600;
}

.overview-status > span {
  width: 7px;
  height: 7px;
  border-radius: 999px;
  background: currentColor;
}

.overview-status--healthy {
  color: var(--color-success, #16a34a);
}

.overview-status--degraded {
  color: var(--color-warning, #b45309);
}

.overview-status--unavailable {
  color: var(--color-error, #dc2626);
}

.overview-panel__footer-link {
  margin: 12px 14px;
}

.overview-table-wrap {
  width: 100%;
  overflow-x: auto;
}

.overview-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 11px;
}

.overview-table th,
.overview-table td {
  padding: 9px 12px;
  border-bottom: 1px solid var(--color-border-light, #eef0f4);
  text-align: left;
  vertical-align: middle;
}

.overview-table th {
  color: var(--color-text-tertiary, #94a3b8);
  font-size: 10px;
  font-weight: 600;
  white-space: nowrap;
}

.overview-table td {
  color: var(--color-text-secondary, #64748b);
}

.overview-table tbody tr:last-child td {
  border-bottom: 0;
}

.overview-table__primary,
.overview-table__secondary {
  display: block;
  min-width: 0;
  max-width: 320px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.overview-table__primary {
  color: var(--color-text-title, #1d2129);
  font-size: 12px;
  font-weight: 500;
}

.overview-table__secondary {
  margin-top: 2px;
  color: var(--color-text-tertiary, #94a3b8);
  font-size: 10px;
}

.overview-table__task-link {
  text-decoration: none;
}

.overview-table__task-link:hover .overview-table__primary,
.overview-table__task-link:focus-visible .overview-table__primary {
  color: var(--color-primary, #6d5ef6);
}

.overview-table__time {
  white-space: nowrap;
}

.overview-table__empty {
  height: 88px;
  text-align: center !important;
  color: var(--color-text-tertiary, #94a3b8) !important;
}

.overview-pill {
  display: inline-flex;
  padding: 2px 7px;
  border-radius: 6px;
  background: var(--color-grey-2, #f5f5f7);
  color: var(--color-text-secondary, #64748b);
  font-size: 9px;
  font-weight: 650;
  text-transform: capitalize;
}

.overview-pill--danger {
  background: var(--color-error-light, #fef2f2);
  color: var(--color-error, #dc2626);
}

.overview-pill--warning {
  background: var(--color-warning-light, #fffbeb);
  color: var(--color-warning, #b45309);
}

.overview-pill--info {
  background: var(--color-info-light, #eff6ff);
  color: var(--color-info, #2563eb);
}

.overview-attention-list__item {
  display: grid;
  min-height: 46px;
  grid-template-columns: 8px minmax(0, 1fr) auto auto;
  align-items: center;
  gap: 8px;
  padding: 0 14px;
  border-bottom: 1px solid var(--color-border-light, #eef0f4);
  color: var(--color-text-secondary, #64748b);
  font-size: 12px;
  text-decoration: none;
}

.overview-attention-list li:last-child .overview-attention-list__item {
  border-bottom: 0;
}

.overview-attention-list__item:hover,
.overview-attention-list__item:focus-visible {
  background: var(--color-grey-1, #fafafa);
}

.overview-attention-list__marker {
  width: 7px;
  height: 7px;
  border-radius: 999px;
  background: var(--color-text-tertiary, #94a3b8);
}

.overview-attention-list__marker.is-warning {
  background: var(--color-warning, #d97706);
}

.overview-attention-list__marker.is-danger {
  background: var(--color-error, #dc2626);
}

.overview-attention-list__item strong {
  color: var(--color-text-title, #1d2129);
  font-size: 13px;
}

.overview-summary-list li {
  display: grid;
  min-height: 54px;
  grid-template-columns: 30px minmax(0, 1fr) auto;
  align-items: center;
  gap: 10px;
  padding: 0 14px;
  border-bottom: 1px solid var(--color-border-light, #eef0f4);
  color: var(--color-text-secondary, #64748b);
  font-size: 12px;
}

.overview-summary-list__icon {
  width: 28px;
  height: 28px;
  flex-basis: 28px;
  color: var(--color-primary, #6d5ef6);
}

.overview-summary-list strong {
  color: var(--color-text-title, #1d2129);
  font-size: 14px;
  font-weight: 650;
}

.overview-skeleton {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
}

.overview-skeleton > span {
  position: relative;
  min-height: 102px;
  overflow: hidden;
  border: 1px solid var(--color-border-light, #eef0f4);
  border-radius: 10px;
  background: var(--color-card-bg, #fff);
}

.overview-skeleton > span::after {
  position: absolute;
  inset: 0;
  background: linear-gradient(90deg, transparent, rgba(109, 94, 246, 0.08), transparent);
  content: '';
  animation: overview-shimmer 1.15s ease-in-out infinite;
  transform: translateX(-100%);
}

.overview-skeleton__banner {
  min-height: 68px !important;
  grid-column: 1 / -1;
}

@keyframes overview-shimmer {
  to {
    transform: translateX(100%);
  }
}

@media (max-width: 1180px) {
  .overview-kpi-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 900px) {
  .overview-grid {
    grid-template-columns: minmax(0, 1fr);
  }

  .overview-service-list li {
    grid-template-columns: minmax(86px, 1fr) auto;
  }

  .overview-service-list__detail {
    display: none;
  }
}

@media (max-width: 640px) {
  .platform-overview__toolbar,
  .overview-health-banner {
    align-items: stretch;
    flex-direction: column;
  }

  .platform-overview__controls,
  .platform-overview__range {
    width: 100%;
  }

  .overview-kpi-grid,
  .overview-skeleton {
    grid-template-columns: minmax(0, 1fr);
  }

  .overview-activity-chart {
    height: 220px;
  }
}

@media (prefers-reduced-motion: reduce) {
  .overview-kpi-card,
  .overview-skeleton > span::after {
    animation: none;
    transition: none;
  }
}
</style>
