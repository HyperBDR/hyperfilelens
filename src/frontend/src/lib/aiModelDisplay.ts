import { aiProviderLabel } from './aiProviderDisplay'

export function defaultAiModelDisplayName(
  provider: string,
  model: string,
  providerLabel?: string,
  modelLabel?: string,
) {
  const providerPart = (providerLabel || aiProviderLabel(provider, provider)).trim() || provider || 'provider'
  const modelPart = (modelLabel || model).trim() || '—'
  return `${providerPart} · ${modelPart}`
}
