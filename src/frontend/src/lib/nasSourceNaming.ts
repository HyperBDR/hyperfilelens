export function normalizeNasSourceName(value: string): string {
  return value.trim().toLowerCase()
}

export function hasNasSourceNameConflict(
  existingNames: Iterable<string>,
  candidateName: string,
): boolean {
  const normalized = normalizeNasSourceName(candidateName)
  if (!normalized) return false
  for (const name of existingNames) {
    if (normalizeNasSourceName(name) === normalized) return true
  }
  return false
}

export function resolveNasSubmitName(
  name: string,
  generatedName: string,
  nameTouched: boolean,
): string {
  if (!name.trim() || !nameTouched) return generatedName.trim()
  return name.trim()
}
