export function parseSemver(value: string | null | undefined): [number, number, number] | null {
  const s = String(value || '').trim().replace(/^v/i, '')
  const m = s.match(/^(\d+)\.(\d+)\.(\d+)/)
  if (!m) return null
  return [Number(m[1]), Number(m[2]), Number(m[3])]
}

export function semverCompare(a: string, b: string): number {
  const pa = parseSemver(a)
  const pb = parseSemver(b)
  if (!pa || !pb) return 0
  for (let i = 0; i < 3; i += 1) {
    if (pa[i] !== pb[i]) return pa[i] - pb[i]
  }
  return 0
}

export function needsAgentUpgrade(
  current: string | null | undefined,
  latest: string | null | undefined,
): boolean {
  if (!latest || !parseSemver(latest)) return false
  const cur = String(current || '').trim()
  if (!cur || !parseSemver(cur)) return false
  return semverCompare(cur, latest) < 0
}

/** Remote upgrade allowed when current <= published (no downgrade). */
export function canRemoteAgentUpgrade(
  current: string | null | undefined,
  latest: string | null | undefined,
): boolean {
  if (!latest || !parseSemver(latest)) return false
  const cur = String(current || '').trim()
  if (!cur || !parseSemver(cur)) return false
  return semverCompare(cur, latest) <= 0
}

export function isSameVersionReinstall(
  current: string | null | undefined,
  latest: string | null | undefined,
): boolean {
  if (!canRemoteAgentUpgrade(current, latest)) return false
  const cur = String(current || '').trim()
  return semverCompare(cur, latest) === 0
}

export function publishedAgentVersionLabel(version: string | null | undefined): string {
  const trimmed = String(version || '').trim()
  if (!trimmed || trimmed === '0.0.0' || !parseSemver(trimmed)) return ''
  return trimmed
}
