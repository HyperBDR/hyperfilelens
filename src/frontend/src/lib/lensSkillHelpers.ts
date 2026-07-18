import type { LensSkill } from './lensApi'

export function isWorkspaceGuideSkill(row: LensSkill): boolean {
  return typeof row.slug === 'string' && row.slug.endsWith('-workspace-guide')
}

export function skillDescription(row: LensSkill): string {
  const definition = row.definition
  if (definition && typeof definition === 'object') {
    return definition.description || ''
  }
  return ''
}

export function skillContent(row: LensSkill): string {
  const definition = row.definition
  if (typeof definition === 'string') {
    return definition
  }
  if (definition && typeof definition === 'object') {
    return definition.content || definition.markdown || definition.skill_md || ''
  }
  return ''
}

export function skillContentPreview(row: LensSkill, maxLength = 96): string {
  const raw = skillContent(row).trim()
  if (!raw) return ''
  const line =
    raw
      .split('\n')
      .map((item) => item.trim())
      .find(Boolean) || ''
  const normalized = line.replace(/^#+\s*/, '').trim()
  if (normalized.length <= maxLength) return normalized
  return `${normalized.slice(0, maxLength - 1)}…`
}
