export function restoreDirectoryBrowseSourceId(targetId: string) {
  const value = String(targetId || '').trim()
  const match = /^(agent|nas):(\d+)$/.exec(value)
  if (!match) return value
  return `${match[1]}:${Number(match[2])}`
}
