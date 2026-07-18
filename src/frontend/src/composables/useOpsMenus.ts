import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { Laptop, AlertTriangle, BellRing, Radio, FileText, History, ScrollText } from 'lucide-vue-next'
import type { MenuItem } from '../components/ModulePage.vue'

export function useOpsMenus() {
  const { t } = useI18n()
  return computed<MenuItem[]>(() => [
    {
      label: t('ops.nav.groupObserve'),
      children: [{ label: t('ops.nav.monitor'), to: '/ops/host-monitor', icon: Laptop }],
    },
    {
      label: t('ops.nav.groupAlerts'),
      children: [
        { label: t('ops.nav.alertIncidents'), to: '/ops/alerts/incidents', icon: AlertTriangle },
        { label: t('ops.nav.alertRules'), to: '/ops/alerts/rules', icon: BellRing },
        { label: t('ops.nav.notificationChannels'), to: '/ops/channels', icon: Radio },
        { label: t('ops.nav.notificationRecords'), to: '/ops/notification-records', icon: ScrollText },
      ],
    },
    {
      label: t('ops.nav.groupEvents'),
      children: [
        { label: t('ops.task.sideAudit'), to: '/ops/audit', icon: FileText },
        { label: t('ops.task.sideTasks'), to: '/ops/task', icon: History },
      ],
    },
  ])
}
