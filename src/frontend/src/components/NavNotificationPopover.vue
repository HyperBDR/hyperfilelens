<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { ArrowUpRight, Bell } from 'lucide-vue-next'
import {
  acknowledgeRecord,
  listRecords,
  type AlertRecord,
} from '../lib/alertApi'

const { t } = useI18n()
const router = useRouter()
const visible = ref(false)
const loading = ref(false)
const markingAll = ref(false)
const alerts = ref<AlertRecord[]>([])
const totalCount = ref(0)

type Severity = 'critical' | 'warning' | 'insight' | 'info'

const POLL_MS = 30000
const PAGE_SIZE = 10

let cancelled = false
let interval: ReturnType<typeof setInterval> | undefined

const unreadCount = computed(
  () => alerts.value.filter((a) => a.status === 'firing').length,
)

const badgeCount = computed(() => totalCount.value)

const badgeText = computed(() => (badgeCount.value > 99 ? '99+' : String(badgeCount.value)))

const popperOptions = {
  modifiers: [
    {
      name: 'preventOverflow',
      options: {
        boundary: 'viewport',
        padding: 12,
      },
    },
    {
      name: 'flip',
      options: {
        fallbackPlacements: ['bottom-start', 'top-end', 'top-start'],
      },
    },
  ],
}

function severityClass(alert: AlertRecord): Severity {
  if (alert.severity === 'critical') return 'critical'
  if (alert.severity === 'warning') return 'warning'
  if (alert.type === 'event') return 'insight'
  return 'info'
}

function alertSummary(alert: AlertRecord) {
  const resource = alert.resourceName || alert.resource_name
  if (resource) return resource
  const message = alert.message?.trim()
  if (message) return message
  return alert.resourceType || alert.resource_type || '—'
}

function alertTimestamp(alert: AlertRecord) {
  return alert.lastTriggeredAt || alert.last_triggered_at || alert.createdAt || alert.created_at
}

function formatRelativeTime(iso?: string) {
  if (!iso) return '—'
  const date = new Date(iso)
  if (Number.isNaN(date.getTime())) return '—'

  const diffSec = Math.max(0, Math.floor((Date.now() - date.getTime()) / 1000))
  if (diffSec < 60) return t('nav.notificationPopover.relative.justNow')

  const minutes = Math.floor(diffSec / 60)
  if (minutes < 60) return t('nav.notificationPopover.relative.minutesAgo', { n: minutes })

  const hours = Math.floor(minutes / 60)
  if (hours < 24) return t('nav.notificationPopover.relative.hoursAgo', { n: hours })

  const days = Math.floor(hours / 24)
  if (days === 1) return t('nav.notificationPopover.relative.yesterday')

  return t('nav.notificationPopover.relative.daysAgo', { n: days })
}

async function loadAlerts() {
  loading.value = true
  try {
    const res = await listRecords({ status: 'firing', page_size: PAGE_SIZE })
    if (cancelled) return
    alerts.value = res.results
    totalCount.value = res.count
  } catch {
    if (!cancelled) {
      alerts.value = []
      totalCount.value = 0
    }
  } finally {
    if (!cancelled) loading.value = false
  }
}

async function onItemClick(alert: AlertRecord) {
  visible.value = false
  if (alert.status === 'firing') {
    try {
      await acknowledgeRecord(alert.id)
      await loadAlerts()
    } catch {
      /* ignore */
    }
  }
  router.push('/ops/alerts/incidents')
}

async function markAllRead() {
  const firing = alerts.value.filter((a) => a.status === 'firing')
  if (!firing.length || markingAll.value) return

  markingAll.value = true
  try {
    await Promise.all(firing.map((a) => acknowledgeRecord(a.id)))
    await loadAlerts()
  } catch {
    await loadAlerts()
  } finally {
    markingAll.value = false
  }
}

function viewAll() {
  visible.value = false
  router.push('/ops/alerts/incidents')
}

watch(visible, (open) => {
  if (open) loadAlerts()
})

onMounted(() => {
  loadAlerts()
  interval = setInterval(loadAlerts, POLL_MS)
})

onUnmounted(() => {
  cancelled = true
  if (interval) clearInterval(interval)
})
</script>

<template>
  <div class="nav-notification-wrap">
    <HflPopover
      v-model:visible="visible"
      trigger="click"
      placement="bottom-end"
      :width="380"
      :show-arrow="false"
      effect="light"
      popper-class="nav-dropdown-popover"
      :popper-options="popperOptions"
      :offset="8"
    >
      <template #reference>
        <button
          type="button"
          class="nav-notification-trigger"
          :aria-label="t('nav.notificationPopover.bellAria')"
        >
          <Bell :size="18" />
          <span v-if="badgeCount > 0" class="nav-notification-badge">{{ badgeText }}</span>
        </button>
      </template>

      <div class="nav-dropdown-panel">
        <header class="nav-dropdown-panel__head">
          <h3 class="nav-dropdown-panel__title">
            {{ t('nav.notificationPopover.title') }} ({{ badgeCount }})
          </h3>
          <ElButton
            v-if="unreadCount > 0"
            text
            type="primary"
            size="small"
            class="nav-dropdown-panel__head-action"
            :loading="markingAll"
            @click="markAllRead"
          >
            {{ t('nav.notificationPopover.markAllRead') }}
          </ElButton>
        </header>

        <div class="nav-dropdown-panel__body nav-dropdown-panel__body--flush">
          <div v-if="loading && !alerts.length" class="nav-dropdown-panel__empty">
            {{ t('nav.notificationPopover.loading') }}
          </div>
          <div v-else-if="!alerts.length" class="nav-dropdown-panel__empty">
            {{ t('nav.notificationPopover.empty') }}
          </div>
          <ul v-else class="nav-dropdown-panel__list nn-list" role="list">
            <li
              v-for="alert in alerts"
              :key="alert.id"
              class="nn-item"
              role="button"
              tabindex="0"
              @click="onItemClick(alert)"
              @keydown.enter.prevent="onItemClick(alert)"
            >
              <span
                class="nn-icon"
                :class="`nn-icon--${severityClass(alert)}`"
                aria-hidden="true"
              />
              <div class="nn-item-body">
                <div class="nn-item-title">{{ alert.title }}</div>
                <div class="nn-item-meta">
                  <span class="nn-item-summary">{{ alertSummary(alert) }}</span>
                  <span class="nn-item-sep">|</span>
                  <span class="nn-item-time">{{ formatRelativeTime(alertTimestamp(alert)) }}</span>
                </div>
              </div>
              <span v-if="alert.status === 'firing'" class="nn-unread-dot" aria-hidden="true" />
            </li>
          </ul>
        </div>

        <footer class="nav-dropdown-panel__foot">
          <button type="button" class="nav-dropdown-panel__foot-link" @click="viewAll">
            <span>{{ t('nav.notificationPopover.viewAll') }}</span>
            <ArrowUpRight :size="14" aria-hidden="true" />
          </button>
        </footer>
      </div>
    </HflPopover>
  </div>
</template>

<style scoped>
.nav-notification-wrap {
  position: relative;
  display: flex;
  align-items: center;
}

.nav-notification-trigger {
  position: relative;
  display: flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 32px;
  padding: 0;
  border: none;
  border-radius: 6px;
  background: transparent;
  color: var(--nav-notification-color, rgba(255, 255, 255, 0.8));
  cursor: pointer;
  transition:
    background-color 0.15s ease,
    color 0.15s ease;
}

.nav-notification-trigger:hover {
  background: var(--icon-btn-hover-bg, rgba(255, 255, 255, 0.08));
  color: var(--nav-notification-hover-color, #fff);
}

@media (max-width: 1023.98px) {
  .nav-notification-trigger {
    width: 44px;
    height: 44px;
  }
}

.nav-notification-badge {
  position: absolute;
  top: -4px;
  right: -2px;
  min-width: 18px;
  height: 18px;
  padding: 0 4px;
  font-size: 11px;
  font-weight: 600;
  line-height: 18px;
  color: #fff;
  text-align: center;
  background-color: var(--color-error);
  border-radius: 9px;
}

.nn-list {
  padding: 4px 0;
}

.nn-item {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  padding: 10px 16px;
  cursor: pointer;
  transition: background-color 0.15s ease;
}

.nn-item:hover {
  background-color: rgba(69, 125, 176, 0.08);
}

.nn-item:focus-visible {
  outline: 2px solid var(--color-primary, #457ab0);
  outline-offset: -2px;
}

.nn-icon {
  flex-shrink: 0;
  width: 10px;
  height: 10px;
  margin-top: 5px;
  border-radius: 50%;
}

.nn-icon--critical {
  background-color: var(--color-error);
}

.nn-icon--warning {
  background-color: var(--color-warning);
}

.nn-icon--insight {
  background-color: var(--color-primary, #457ab0);
}

.nn-icon--info {
  background-color: var(--color-grey-5, #bfbfbf);
}

.nn-item-body {
  flex: 1;
  min-width: 0;
}

.nn-item-title {
  font-size: 14px;
  font-weight: 600;
  line-height: 1.35;
  color: var(--color-text-title, #303133);
}

.nn-item-meta {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 6px;
  margin-top: 4px;
  font-size: 12px;
  color: var(--color-text-tertiary, #909399);
}

.nn-item-sep {
  color: var(--color-border, #d9d9d9);
}

.nn-unread-dot {
  flex-shrink: 0;
  width: 8px;
  height: 8px;
  margin-top: 6px;
  background-color: var(--color-primary, #457ab0);
  border-radius: 50%;
}
</style>
