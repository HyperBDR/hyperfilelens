import { shallowRef } from 'vue'
import { i18n, registerLocale } from '../i18n'

export type InstalledLangPack = {
  id: string
  display_name: string
  frontend_code: string
  backend_code: string
  element_plus_locale?: string
  version: string
}

export const installedLangPacks = shallowRef<InstalledLangPack[]>([])

export function hasMultipleLocales(): boolean {
  return Object.keys(i18n.global.messages.value).length > 1
}

function isInstalledLangPack(value: unknown): value is InstalledLangPack {
  if (!value || typeof value !== 'object') return false
  const pack = value as Record<string, unknown>
  return (
    typeof pack.id === 'string' &&
    /^[a-z0-9]+(?:-[a-z0-9]+)*$/.test(pack.id) &&
    typeof pack.display_name === 'string' &&
    typeof pack.frontend_code === 'string' &&
    pack.frontend_code === pack.frontend_code.toLowerCase() &&
    /^[a-z]{2,3}(?:-[a-z0-9]{2,8})*$/i.test(pack.frontend_code) &&
    typeof pack.backend_code === 'string' &&
    pack.backend_code === pack.backend_code.toLowerCase() &&
    /^[a-z]{2,3}(?:-[a-z0-9]{2,8})*$/i.test(pack.backend_code) &&
    typeof pack.version === 'string' &&
    (pack.element_plus_locale === undefined ||
      (typeof pack.element_plus_locale === 'string' &&
        /^[A-Za-z0-9_-]+$/.test(pack.element_plus_locale)))
  )
}

function isMessageCatalog(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === 'object' && !Array.isArray(value)
}

export async function loadInstalledLangPacks(): Promise<void> {
  try {
    const res = await fetch('/locales/installed.json', { cache: 'no-cache' })
    if (!res.ok) return
    const data = (await res.json()) as { packs?: InstalledLangPack[] }
    const packs = (data.packs ?? []).filter(isInstalledLangPack)
    const loadedPacks: InstalledLangPack[] = []
    for (const pack of packs) {
      const messagesResponse = await fetch(
        `/locales/${encodeURIComponent(pack.id)}/frontend/messages.json`,
        { cache: 'no-cache' },
      )
      if (!messagesResponse.ok) continue
      const messages: unknown = await messagesResponse.json()
      if (!isMessageCatalog(messages)) continue
      registerLocale(pack.frontend_code, messages)
      loadedPacks.push(pack)
    }
    installedLangPacks.value = loadedPacks
  } catch {
    installedLangPacks.value = []
  }
}
