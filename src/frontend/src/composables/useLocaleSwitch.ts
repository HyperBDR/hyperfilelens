import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { DEFAULT_LOCALE, getAvailableLocaleCodes, LANG_STORAGE_KEY } from '../i18n'
import { hasMultipleLocales, installedLangPacks } from '../lib/langPacks'

export function useLocaleSwitch() {
  const { locale } = useI18n()
  const canSwitchLocale = computed(() => hasMultipleLocales())
  const nextLocaleCode = computed(() => {
    const available = getAvailableLocaleCodes()
    const currentIndex = available.indexOf(String(locale.value))
    return available[(currentIndex + 1) % available.length] ?? DEFAULT_LOCALE
  })
  const nextLocaleLabel = computed(() => {
    if (nextLocaleCode.value === DEFAULT_LOCALE) return 'English'
    return (
      installedLangPacks.value.find(
        (pack) => pack.frontend_code === nextLocaleCode.value,
      )?.display_name ?? nextLocaleCode.value
    )
  })

  function toggleLocale() {
    if (!canSwitchLocale.value) return
    locale.value = nextLocaleCode.value
    try {
      localStorage.setItem(LANG_STORAGE_KEY, nextLocaleCode.value)
      document.documentElement.lang = nextLocaleCode.value
    } catch {
      // Storage may be unavailable in privacy-restricted browser contexts.
    }
  }

  return {
    canSwitchLocale,
    nextLocaleCode,
    nextLocaleLabel,
    toggleLocale,
    locale,
  }
}
