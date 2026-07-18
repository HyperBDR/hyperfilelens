import { createI18n } from 'vue-i18n'
import { en } from './locales'

export const LANG_STORAGE_KEY = 'hfl.lang'
export const DEFAULT_LOCALE = 'en'

export const i18n = createI18n({
  legacy: false,
  locale: DEFAULT_LOCALE,
  fallbackLocale: DEFAULT_LOCALE,
  messages: { en },
})

export function registerLocale(code: string, messages: Record<string, unknown>) {
  i18n.global.setLocaleMessage(code, messages)
}

export function getAvailableLocaleCodes(): string[] {
  return Object.keys(i18n.global.messages.value)
}

export function normalizeStoredLocale(stored: string | null | undefined): string {
  if (!stored) return DEFAULT_LOCALE
  return getAvailableLocaleCodes().includes(stored) ? stored : DEFAULT_LOCALE
}

function readStoredLocale(): string {
  try {
    return normalizeStoredLocale(localStorage.getItem(LANG_STORAGE_KEY))
  } catch {
    return DEFAULT_LOCALE
  }
}

export function applyStoredLocale() {
  i18n.global.locale.value = readStoredLocale()
}

export function resolveLocaleAfterPacksLoaded() {
  const resolved = normalizeStoredLocale(
    typeof localStorage !== 'undefined' ? localStorage.getItem(LANG_STORAGE_KEY) : null,
  )
  i18n.global.locale.value = resolved
  try {
    localStorage.setItem(LANG_STORAGE_KEY, resolved)
  } catch {
    /* ignore */
  }
}
