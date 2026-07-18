/** Minimal fields needed to format offline backup-plan guard messages. */
export type OfflineBackupSourcePick = {
  type: 'host' | 'nas'
  name: string
  nodeName: string
}

type TranslateFn = (key: string, params?: Record<string, string>) => string

const HOST_OFFLINE_KEY = 'protection.backupsPage.msgCreateBackupHostOffline'
const NAS_OFFLINE_KEY = 'protection.backupsPage.msgCreateBackupNasOffline'

function joinQuotedNames(names: string[]) {
  return names.map((n) => n.trim()).filter(Boolean).join(', ')
}

/** User-facing toast when offline sources block creating a backup plan. */
export function formatOfflineBackupPlanMessage(
  rows: OfflineBackupSourcePick[],
  t: TranslateFn,
  opts?: { hostOfflineKey?: string; nasOfflineKey?: string },
): string {
  const hostKey = opts?.hostOfflineKey ?? HOST_OFFLINE_KEY
  const nasKey = opts?.nasOfflineKey ?? NAS_OFFLINE_KEY
  const hosts = rows.filter((row) => row.type === 'host')
  const nasRows = rows.filter((row) => row.type === 'nas')
  const parts: string[] = []

  if (hosts.length > 0) {
    parts.push(
      t(hostKey, { names: joinQuotedNames(hosts.map((row) => row.name)) }),
    )
  }

  if (nasRows.length > 0) {
    const byNode = new Map<string, string[]>()
    for (const row of nasRows) {
      const node = (row.nodeName || row.name).trim() || row.name
      const names = byNode.get(node) ?? []
      names.push(row.name)
      byNode.set(node, names)
    }
    for (const [node, names] of byNode) {
      parts.push(
        t(nasKey, {
          names: joinQuotedNames(names),
          node,
        }),
      )
    }
  }

  return parts.join(' ')
}
