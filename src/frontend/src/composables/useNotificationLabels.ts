import { useI18n } from 'vue-i18n'
import { formatLocalDateTime } from '../lib/dateTime'
import { lifecycleStatusTone, type StatusTagTone } from '../lib/statusTag'
import type { ChannelType, DeliveryStatus } from '../pages/ops/notificationTypes'

export function useNotificationLabels() {
  const { t } = useI18n()

  const channelTypeMap: Record<ChannelType, string> = {
    webhook: 'Webhook',
    email: 'Email',
    dingtalk: 'DingTalk',
    feishu: 'Feishu',
    wecom: 'WeCom',
    sms: 'SMS',
  }

  function channelTypeLabel(type: ChannelType): string {
    const key = `ops.notification.type${type.charAt(0).toUpperCase() + type.slice(1)}` as const
    return t(key) || channelTypeMap[type]
  }

  function eventTypeLabel(code: string): string {
    const camel = code.replace(/_([a-z])/g, (_, c) => c.toUpperCase())
    const key = `ops.notification.event${camel.charAt(0).toUpperCase() + camel.slice(1)}` as const
    const translated = t(key)
    if (translated !== key) return translated
    const map: Record<string, string> = {
      backup_failed: t('ops.notification.eventBackupFailed'),
      backup_completed: t('ops.notification.eventBackupCompleted'),
      restore_completed: t('ops.notification.eventRestoreCompleted'),
      restore_failed: t('ops.notification.eventRestoreFailed'),
      replication_timeout: t('ops.notification.eventReplicationTimeout'),
      policy_violated: t('ops.notification.eventPolicyViolated'),
      node_offline: t('ops.notification.eventNodeOffline'),
      node_online: t('ops.notification.eventNodeOnline'),
      storage_quota_warning: t('ops.notification.eventStorageQuotaWarning'),
      snapshot_created: t('ops.notification.eventSnapshotCreated'),
      snapshot_expired: t('ops.notification.eventSnapshotExpired'),
      classification_completed: t('ops.notification.eventClassificationCompleted'),
    }
    return map[code] || code
  }

  function statusType(status: DeliveryStatus): StatusTagTone {
    return lifecycleStatusTone(status)
  }

  function formatDateTime(iso?: string | null): string {
    return formatLocalDateTime(iso, t('ops.task.emptyMark'))
  }

  return {
    channelTypeLabel,
    eventTypeLabel,
    statusType,
    formatDateTime,
  }
}
