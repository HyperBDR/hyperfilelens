import type { ComposerTranslation } from 'vue-i18n'

export const BACKUP_SOURCE_RESET_CONFIRMATION = 'RESET'

export function resetSourceCountLabel(count: number, t: ComposerTranslation): string {
  return count === 1
    ? t('protection.backupsPage.resetSelectedSourceSingular', { n: count })
    : t('protection.backupsPage.resetSelectedSourcePlural', { n: count })
}

export function buildResetImpactItems(t: ComposerTranslation): string[] {
  return [
    t('protection.backupsPage.resetWarningItemReturn'),
    t('protection.backupsPage.resetWarningItemDelete'),
    t('protection.backupsPage.resetWarningItemCleanup'),
  ]
}
