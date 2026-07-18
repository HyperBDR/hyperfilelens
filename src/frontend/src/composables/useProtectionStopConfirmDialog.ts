import { ref } from 'vue'
import type { ProtectionStopConfirmItem } from '../lib/protectionStopConfirm'

export function useProtectionStopConfirmDialog() {
  const open = ref(false)
  const kind = ref<'backup' | 'restore'>('backup')
  const items = ref<ProtectionStopConfirmItem[]>([])
  const loading = ref(false)

  let settled = false
  let resolver: ((confirmed: boolean) => void) | null = null

  function waitForConfirm(nextKind: 'backup' | 'restore', nextItems: ProtectionStopConfirmItem[]) {
    return new Promise<boolean>((resolve) => {
      settled = false
      kind.value = nextKind
      items.value = nextItems
      open.value = true
      resolver = resolve
    })
  }

  function settle(confirmed: boolean) {
    if (settled) return
    settled = true
    open.value = false
    items.value = []
    const resolve = resolver
    resolver = null
    resolve?.(confirmed)
  }

  function settleConfirm() {
    settle(true)
  }

  function settleCancel() {
    settle(false)
  }

  async function confirmStopBackup(nextItems: ProtectionStopConfirmItem[]) {
    if (!nextItems.length) return false
    return waitForConfirm('backup', nextItems)
  }

  async function confirmStopRestore(nextItems: ProtectionStopConfirmItem[]) {
    if (!nextItems.length) return false
    return waitForConfirm('restore', nextItems)
  }

  return {
    open,
    kind,
    items,
    loading,
    confirmStopBackup,
    confirmStopRestore,
    settleConfirm,
    settleCancel,
  }
}
