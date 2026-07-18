export type LocalDateTimeInput = string | number | Date | null | undefined

export type FormatDateTimeOptions = {
  /** IANA timezone; defaults to the browser local timezone */
  timeZone?: string
  /** Format in UTC and append " UTC" */
  utc?: boolean
}

export function normalizeDateTimeLocale(locale?: string) {
  if (!locale) return undefined
  return locale
}

export function parseLocalDateTime(value: Exclude<LocalDateTimeInput, null | undefined>) {
  const normalized = typeof value === 'string'
    ? value.trim().replace(/^(\d{4}-\d{2}-\d{2})\s+/, '$1T')
    : value
  return normalized instanceof Date ? normalized : new Date(normalized)
}

function dateTimeParts(date: Date, options?: FormatDateTimeOptions) {
  const timeZone = options?.utc ? 'UTC' : options?.timeZone
  const parts = new Intl.DateTimeFormat('en-GB', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false,
    ...(timeZone ? { timeZone } : {}),
  }).formatToParts(date)
  const get = (type: Intl.DateTimeFormatPartTypes) =>
    parts.find((part) => part.type === type)?.value || ''
  return {
    year: get('year'),
    month: get('month'),
    day: get('day'),
    hour: get('hour'),
    minute: get('minute'),
    second: get('second'),
  }
}

/** App-wide datetime: `YYYY-MM-DD HH:mm:ss` in local time (or the given timezone). */
export function formatAppDateTime(
  value: LocalDateTimeInput,
  fallback = '—',
  options?: FormatDateTimeOptions,
): string {
  if (value === null || value === undefined || value === '') return fallback
  const date = parseLocalDateTime(value)
  if (Number.isNaN(date.getTime())) return String(value)
  const parts = dateTimeParts(date, options)
  const formatted = `${parts.year}-${parts.month}-${parts.day} ${parts.hour}:${parts.minute}:${parts.second}`
  return options?.utc ? `${formatted} UTC` : formatted
}

/** App-wide date-only: `YYYY-MM-DD`. */
export function formatAppDate(
  value: LocalDateTimeInput,
  fallback = '—',
  options?: Pick<FormatDateTimeOptions, 'timeZone'>,
): string {
  if (value === null || value === undefined || value === '') return fallback
  const date = parseLocalDateTime(value)
  if (Number.isNaN(date.getTime())) return String(value)
  const parts = dateTimeParts(date, options)
  return `${parts.year}-${parts.month}-${parts.day}`
}

/** App-wide time-only: `HH:mm:ss`. */
export function formatAppTime(
  value: LocalDateTimeInput,
  fallback = '—',
  options?: FormatDateTimeOptions,
): string {
  if (value === null || value === undefined || value === '') return fallback
  const date = parseLocalDateTime(value)
  if (Number.isNaN(date.getTime())) return String(value)
  const parts = dateTimeParts(date, options)
  return `${parts.hour}:${parts.minute}:${parts.second}`
}

/** UTC datetime for audit/export surfaces: `YYYY-MM-DD HH:mm:ss UTC`. */
export function formatAppDateTimeUtc(value: LocalDateTimeInput, fallback = '—'): string {
  return formatAppDateTime(value, fallback, { utc: true })
}

/**
 * Backward-compatible alias for table/detail timestamps.
 * `locale` and legacy Intl options are ignored; use `options` for timezone/UTC.
 */
export function formatLocalDateTime(
  value: LocalDateTimeInput,
  fallback = '—',
  _locale?: string,
  _legacyOptions?: Intl.DateTimeFormatOptions,
  options?: FormatDateTimeOptions,
) {
  return formatAppDateTime(value, fallback, options)
}
