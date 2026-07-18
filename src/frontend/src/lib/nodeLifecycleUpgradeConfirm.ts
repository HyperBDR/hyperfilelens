import type { ComposerTranslation } from 'vue-i18n'
import type { NodeOperationBatchPreview } from '../types/nodeLifecycle'

export function buildUpgradeConfirmSkipLines(
  t: ComposerTranslation,
  preview: NodeOperationBatchPreview,
): string[] {
  const lines: string[] = []
  if (preview.skipped_offline.length) {
    lines.push(t('nodeLifecycle.confirmSkipOffline', { n: preview.skipped_offline.length }))
  }
  if (preview.skipped_workload.length) {
    lines.push(t('nodeLifecycle.confirmSkipWorkload', { n: preview.skipped_workload.length }))
  }
  if (preview.skipped_not_upgradeable.length) {
    lines.push(
      t('nodeLifecycle.confirmSkipNotUpgradeable', {
        n: preview.skipped_not_upgradeable.length,
      }),
    )
  }
  if (preview.skipped_proxy_bound.length) {
    lines.push(t('nodeLifecycle.confirmSkipProxyBound', { n: preview.skipped_proxy_bound.length }))
  }
  return lines
}
