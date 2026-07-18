<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import { ChevronDown, RefreshCw, Search, Server } from 'lucide-vue-next'
import ModulePage from '../../../components/ModulePage.vue'
import SystemMonitorDashboard from '../../../components/monitor/SystemMonitorDashboard.vue'
import HflDateTimeRangePicker from '../../../components/HflDateTimeRangePicker.vue'
import { useDeploymentHostMonitor } from '../../composables/useDeploymentHostMonitor'
import { usePlatformOpsSideNav } from '../../composables/usePlatformOpsSideNav'
import { fetchPlatformDeploymentHosts, fetchPlatformHostMonitor } from '../../lib/platformOpsApi'

const { t } = useI18n()
const sideNav = usePlatformOpsSideNav()

const {
  loading,
  selectedHost,
  selectedHostId,
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
  cpuOption,
  loadOption,
  memoryOption,
  diskUsageOption,
  diskThroughputOption,
  diskIopsOption,
  networkBytesOption,
  networkPacketsOption,
  uniqueDiskNames,
  uniqueNetworkNames,
} = useDeploymentHostMonitor(
  t,
  fetchPlatformHostMonitor,
  fetchPlatformDeploymentHosts,
  'platformOps.monitoring.hostLoadFailed',
)
</script>

<template>
  <ModulePage :menus="sideNav" body-fill>
    <div class="platform-host-monitor">
      <header class="platform-host-monitor__toolbar">
        <div ref="entityDropdownRef" class="platform-host-monitor__host">
          <button
            type="button"
            class="platform-host-monitor__host-btn"
            :title="hostEntityTooltip"
            @click.stop="showEntityDropdown = !showEntityDropdown"
          >
            <Server :size="16" class="platform-host-monitor__host-icon" aria-hidden="true" />
            <span class="platform-host-monitor__host-btn-main">
              <span class="platform-host-monitor__host-text">
                <span class="platform-host-monitor__host-label">{{ t('platformOps.monitoring.hostTarget') }}</span>
                <span class="platform-host-monitor__host-name">{{ hostEntityLabel }}</span>
              </span>
              <span
                v-if="selectedHost"
                class="platform-host-monitor__host-status"
                :class="
                  isHostOnline(selectedHost.status)
                    ? 'platform-host-monitor__host-status--online'
                    : 'platform-host-monitor__host-status--offline'
                "
              >
                <span class="platform-host-monitor__host-status-dot" aria-hidden="true" />
                {{ hostStatusLabel(selectedHost.status) }}
              </span>
            </span>
            <ChevronDown
              :size="16"
              class="platform-host-monitor__chevron"
              :class="{ 'platform-host-monitor__chevron--open': showEntityDropdown }"
            />
          </button>

          <div v-if="showEntityDropdown" class="platform-host-monitor__host-panel">
            <div class="platform-host-monitor__host-search">
              <Search :size="16" class="platform-host-monitor__search-icon" />
              <input
                v-model="entitySearch"
                type="text"
                :placeholder="t('platformOps.monitoring.hostSearchPlaceholder')"
              />
            </div>
            <div class="platform-host-monitor__host-list">
              <p v-if="!filteredEntities.length" class="platform-host-monitor__host-empty">
                {{ t('platformOps.monitoring.hostNoHosts') }}
              </p>
              <button
                v-for="entity in filteredEntities"
                :key="entity.id"
                type="button"
                class="platform-host-monitor__host-item"
                :class="{ 'platform-host-monitor__host-item--active': entity.id === selectedHostId }"
                @click="selectHost(entity.id)"
              >
                <span class="platform-host-monitor__host-item-main">
                  <span class="platform-host-monitor__host-item-label">{{ entity.label }}</span>
                  <span v-if="entity.detail" class="platform-host-monitor__host-item-detail">{{ entity.detail }}</span>
                </span>
                <span
                  class="platform-host-monitor__host-status"
                  :class="
                    entity.isOnline
                      ? 'platform-host-monitor__host-status--online'
                      : 'platform-host-monitor__host-status--offline'
                  "
                >
                  <span class="platform-host-monitor__host-status-dot" aria-hidden="true" />
                  {{ hostStatusLabel(entity.status) }}
                </span>
              </button>
            </div>
          </div>
        </div>

        <div class="platform-host-monitor__toolbar-tail">
          <HflDateTimeRangePicker
            class="platform-host-monitor__time-range"
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
            :title="t('common.refresh')"
            :aria-label="t('common.refresh')"
            :disabled="loading"
            @click="onManualRefresh"
          >
            <RefreshCw :size="16" :class="{ 'is-spinning': loading }" />
          </el-button>
        </div>
      </header>

      <p class="platform-host-monitor__subtitle">{{ t('platformOps.monitoring.hostSubtitle') }}</p>

      <SystemMonitorDashboard
        :loading="loading"
        :kpi-cards="kpiCards"
        :has-chart-data="hasChartData"
        :cpu-option="cpuOption"
        :load-option="loadOption"
        :memory-option="memoryOption"
        :disk-usage-option="diskUsageOption"
        :disk-throughput-option="diskThroughputOption"
        :disk-iops-option="diskIopsOption"
        :network-bytes-option="networkBytesOption"
        :network-packets-option="networkPacketsOption"
        :unique-disk-names="uniqueDiskNames"
        :unique-network-names="uniqueNetworkNames"
        :selected-disk="selectedDisk"
        :selected-network="selectedNetwork"
        @update:selected-disk="selectedDisk = $event"
        @update:selected-network="selectedNetwork = $event"
      />
    </div>
  </ModulePage>
</template>

<style scoped>
.platform-host-monitor {
  display: flex;
  flex-direction: column;
  gap: 16px;
  width: 100%;
  min-width: 0;
}

.platform-host-monitor__toolbar {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
}

.platform-host-monitor__host {
  position: relative;
  min-width: 0;
  flex: 1 1 420px;
  max-width: 100%;
}

.platform-host-monitor__host-btn {
  display: flex;
  align-items: center;
  gap: 10px;
  width: 100%;
  min-height: 34px;
  height: auto;
  padding: 6px 12px;
  border: 0;
  border-radius: 8px;
  background: var(--el-fill-color-blank, #fff);
  box-shadow: 0 0 0 1px var(--el-border-color, #dcdfe6) inset;
  cursor: pointer;
  outline: none;
  transition: box-shadow 0.2s cubic-bezier(0.645, 0.045, 0.355, 1);
}

.platform-host-monitor__host-btn:hover,
.platform-host-monitor__host-btn:focus-visible {
  box-shadow: 0 0 0 1px var(--el-color-primary, #409eff) inset;
}

.platform-host-monitor__host-icon {
  flex-shrink: 0;
  color: rgb(79 70 229);
}

.platform-host-monitor__host-btn-main {
  display: flex;
  min-width: 0;
  flex: 1;
  align-items: center;
  gap: 8px;
}

.platform-host-monitor__host-text {
  display: flex;
  min-width: 0;
  flex: 1;
  flex-direction: column;
  gap: 1px;
}

.platform-host-monitor__host-label {
  font-size: 11px;
  line-height: 1.2;
  color: var(--color-text-secondary, #86909c);
  text-align: left;
}

.platform-host-monitor__host-name {
  font-size: 13px;
  font-weight: 600;
  line-height: 1.35;
  color: var(--color-text-title, #1d2129);
  text-align: left;
  word-break: break-word;
}

.platform-host-monitor__host-status {
  display: inline-flex;
  flex-shrink: 0;
  align-items: center;
  gap: 5px;
  font-size: 12px;
  font-weight: 500;
  line-height: 1;
}

.platform-host-monitor__host-status-dot {
  width: 6px;
  height: 6px;
  border-radius: 9999px;
  flex-shrink: 0;
}

.platform-host-monitor__host-status--online {
  color: #15803d;
}

.platform-host-monitor__host-status--online .platform-host-monitor__host-status-dot {
  background: #22c55e;
  box-shadow: 0 0 0 2px rgba(34, 197, 94, 0.22);
}

.platform-host-monitor__host-status--offline {
  color: #64748b;
}

.platform-host-monitor__host-status--offline .platform-host-monitor__host-status-dot {
  background: #94a3b8;
  box-shadow: 0 0 0 2px rgba(148, 163, 184, 0.2);
}

.platform-host-monitor__chevron {
  flex-shrink: 0;
  color: var(--color-text-secondary, #86909c);
  transition: transform 0.2s;
}

.platform-host-monitor__chevron--open {
  transform: rotate(180deg);
}

.platform-host-monitor__host-panel {
  position: absolute;
  top: calc(100% + 6px);
  left: 0;
  z-index: 2000;
  width: max(100%, 420px);
  max-width: min(720px, 92vw);
  padding: 6px;
  border: 1px solid var(--color-border, #d9d9d9);
  border-radius: var(--el-popper-border-radius, var(--el-border-radius-base, 8px));
  background: var(--el-popper-bg, var(--el-bg-color-overlay, #fff));
  box-shadow:
    0px 5px 5px -3px rgba(0, 0, 0, .2),
    0px 3px 14px 2px rgba(0, 0, 0, .12),
    0px 8px 10px 1px rgba(0, 0, 0, .14);
}

.platform-host-monitor__host-search {
  position: relative;
  margin-bottom: 4px;
}

.platform-host-monitor__search-icon {
  position: absolute;
  left: 10px;
  top: 50%;
  transform: translateY(-50%);
  color: var(--color-text-secondary, #86909c);
  pointer-events: none;
}

.platform-host-monitor__host-search input {
  width: 100%;
  height: 32px;
  padding: 0 10px 0 32px;
  border: 1px solid var(--el-border-color, #dcdfe6);
  border-radius: 6px;
  font-size: 13px;
  outline: none;
}

.platform-host-monitor__host-search input:focus {
  border-color: var(--el-color-primary, #409eff);
}

.platform-host-monitor__host-list {
  max-height: 280px;
  overflow-y: auto;
}

.platform-host-monitor__host-empty {
  margin: 0;
  padding: 12px 10px;
  font-size: 13px;
  color: var(--color-text-secondary, #86909c);
  text-align: center;
}

.platform-host-monitor__host-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  width: 100%;
  padding: 8px 10px;
  border: 0;
  border-radius: 6px;
  background: transparent;
  cursor: pointer;
  text-align: left;
}

.platform-host-monitor__host-item:hover,
.platform-host-monitor__host-item--active {
  background: var(--el-fill-color-light, #f5f7fa);
}

.platform-host-monitor__host-item-main {
  display: flex;
  min-width: 0;
  flex-direction: column;
  gap: 2px;
}

.platform-host-monitor__host-item-label {
  font-size: 13px;
  font-weight: 500;
  line-height: 1.35;
  color: var(--color-text-title, #1d2129);
  word-break: break-word;
}

.platform-host-monitor__host-item-detail {
  font-size: 12px;
  line-height: 1.35;
  color: var(--color-text-secondary, #86909c);
  word-break: break-word;
}

.platform-host-monitor__toolbar-tail {
  margin-left: auto;
  display: flex;
  align-items: center;
  gap: 8px;
  flex-shrink: 0;
}

.platform-host-monitor__time-range {
  min-width: 220px;
}

.platform-host-monitor__subtitle {
  margin: 0;
  font-size: 13px;
  color: var(--color-text-secondary, #86909c);
}

@media (max-width: 768px) {
  .platform-host-monitor__toolbar {
    flex-direction: column;
    align-items: stretch;
  }

  .platform-host-monitor__host {
    max-width: none;
  }

  .platform-host-monitor__toolbar-tail {
    margin-left: 0;
    width: 100%;
    justify-content: flex-end;
  }
}
</style>
