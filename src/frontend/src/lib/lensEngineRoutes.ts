import { getLensApiScope } from './lensApi'

/** Route prefixes for Lens Engine UI (Admin Console vs tenant Insights). */
export function lensEngineBase(): string {
  return getLensApiScope() === 'platform' ? '/platform-ops/engine' : '/insight'
}

export function lensEnginePath(segment: string): string {
  const base = lensEngineBase()
  const clean = segment.replace(/^\//, '')
  if (getLensApiScope() === 'platform') {
    return `${base}/${clean}`
  }
  // Tenant Insights only hosts copilot + gateways.
  if (clean.startsWith('gateways')) {
    return `/insight/gateways`
  }
  return `/platform-ops/engine/${clean}`
}

export function lensModelsPath(): string {
  return lensEnginePath('ai-settings')
}

export function lensGatewaysPath(): string {
  return getLensApiScope() === 'platform'
    ? '/platform-ops/engine/gateways'
    : '/insight/gateways'
}

export function lensKnowledgePath(): string {
  return lensEnginePath('knowledge-base')
}

export function lensAssistantsPath(): string {
  return lensEnginePath('assistants')
}

export function lensSkillsPath(): string {
  return lensEnginePath('skills')
}

export function lensMcpPath(): string {
  return lensEnginePath('mcp-servers')
}
