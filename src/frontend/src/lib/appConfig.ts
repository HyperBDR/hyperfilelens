function envBool(value: string | undefined): boolean {
  return ['1', 'true', 'yes', 'on'].includes(value?.trim().toLowerCase() || '')
}

export const appConfig = {
  showEula: envBool(import.meta.env.VITE_SHOW_EULA),
}
