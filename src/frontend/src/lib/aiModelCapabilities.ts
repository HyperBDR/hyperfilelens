export type AiCatalogCapability = string | { id?: string; name?: string }

export type AiCatalogModelRef = {
  id: string
  label?: string
  name?: string
  capabilities?: AiCatalogCapability[]
}

export type AiCatalogProviderRef = {
  id: string
  models?: AiCatalogModelRef[]
}

export const CAPABILITY_TAG_CLASS: Record<string, string> = {
  'text-to-text': 'cap-sky',
  code: 'cap-emerald',
  vision: 'cap-violet',
  multimodal: 'cap-indigo',
  reasoning: 'cap-rose',
  embedding: 'cap-teal',
}

export function normalizeCapabilities(raw?: AiCatalogCapability[]): string[] {
  if (!raw?.length) return []
  return raw
    .map((item) => {
      if (typeof item === 'string') return item
      return item.id || item.name || ''
    })
    .filter(Boolean)
}

export function capabilityClass(key: string): string {
  return CAPABILITY_TAG_CLASS[key] || 'cap-gray'
}

export function lookupModelCapabilities(
  catalogRaw: unknown,
  providerId: string,
  modelId: string,
): { capabilities: string[]; labels: Record<string, string> } {
  const empty = { capabilities: [] as string[], labels: {} as Record<string, string> }
  if (!catalogRaw || !providerId.trim() || !modelId.trim()) return empty

  let providers: AiCatalogProviderRef[] = []
  let labels: Record<string, string> = {}

  if (typeof catalogRaw === 'object' && !Array.isArray(catalogRaw)) {
    const catalog = catalogRaw as {
      providers?: AiCatalogProviderRef[]
      capability_labels?: Record<string, string>
    }
    providers = catalog.providers ?? []
    labels = catalog.capability_labels ?? {}
  } else if (Array.isArray(catalogRaw)) {
    providers = catalogRaw as AiCatalogProviderRef[]
  }

  const provider = providers.find((row) => row.id === providerId)
  const model = provider?.models?.find((row) => row.id === modelId)
  if (!model) return { capabilities: [], labels }

  return {
    capabilities: normalizeCapabilities(model.capabilities),
    labels,
  }
}
