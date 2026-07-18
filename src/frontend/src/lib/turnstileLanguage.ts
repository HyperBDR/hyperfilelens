/** Map vue-i18n locale to a Cloudflare Turnstile language code. */
export function turnstileLanguageFromAppLocale(appLocale: string): string {
  return appLocale.trim().toLowerCase() || 'en'
}
