import type { ComposerTranslation } from 'vue-i18n'
import type { ProtectionStopConfirmItem } from './protectionStopConfirm'

export function buildStopConfirmTitle(
  t: ComposerTranslation,
  kind: 'backup' | 'restore',
  count: number,
): string {
  if (kind === 'backup') {
    return count === 1
      ? t('protection.backupsPage.stopBackupConfirmTitle')
      : t('protection.backupsPage.stopBackupConfirmTitleBatch', { n: count })
  }
  return count === 1
    ? t('protection.backupsPage.stopRestoreConfirmTitle')
    : t('protection.backupsPage.stopRestoreConfirmTitleBatch', { n: count })
}

export function buildStopConfirmMessage(
  t: ComposerTranslation,
  kind: 'backup' | 'restore',
  items: ProtectionStopConfirmItem[],
): string {
  const count = items.length
  if (kind === 'backup') {
    return count === 1
      ? t('protection.backupsPage.stopBackupConfirmMessage')
      : t('protection.backupsPage.stopBackupConfirmMessageBatch', { n: count })
  }
  return count === 1
    ? t('protection.backupsPage.stopRestoreConfirmMessage')
    : t('protection.backupsPage.stopRestoreConfirmMessageBatch', { n: count })
}

export function stopConfirmDetailLabel(
  t: ComposerTranslation,
  kind: 'backup' | 'restore',
): string {
  return kind === 'backup'
    ? t('protection.backupsPage.flowSourceDetailHostname')
    : t('protection.backupsPage.stopRestoreConfirmItemTarget')
}
