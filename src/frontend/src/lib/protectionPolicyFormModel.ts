
import type {
  BackupPolicy,
  BackupPolicyRetention,
  BackupPolicyWritePayload,
  FileFilterRule,
  FileFilterRuleWritePayload,
} from './protectionPolicyApi'

export type MessageLocale = 'en'

export type FreqMode = 'simple' | 'advanced'

export type SimpleIntervalUnit = 'minute' | 'hour' | 'day'

export interface SimpleIntervalUnitMeta {
  value: SimpleIntervalUnit
  label: string
  valueLabel: string
  unitText: string
  min: number
  max: number
  defaultValue: number
}

const INTERVAL_BASE: Record<
  SimpleIntervalUnit,
  Omit<SimpleIntervalUnitMeta, 'label' | 'valueLabel' | 'unitText'>
> = {
  minute: { value: 'minute', min: 1, max: 59, defaultValue: 10 },
  hour: { value: 'hour', min: 1, max: 23, defaultValue: 1 },
  day: { value: 'day', min: 1, max: 365, defaultValue: 1 },
}

const INTERVAL_LABELS: Record<MessageLocale, Record<SimpleIntervalUnit, Pick<SimpleIntervalUnitMeta, 'label' | 'valueLabel' | 'unitText'>>> = {
  en: {
    minute: { label: 'Minutes', valueLabel: 'Minutes', unitText: 'minutes' },
    hour: { label: 'Hours', valueLabel: 'Hours', unitText: 'hours' },
    day: { label: 'Days', valueLabel: 'Days', unitText: 'days' },
  },
}

export function getSimpleIntervalUnitOptions(locale: MessageLocale = 'en'): SimpleIntervalUnitMeta[] {
  return (['minute', 'hour', 'day'] as const).map((u) => ({
    ...INTERVAL_BASE[u],
    ...INTERVAL_LABELS[locale][u],
  }))
}

export const SIMPLE_INTERVAL_UNIT_OPTIONS: SimpleIntervalUnitMeta[] = getSimpleIntervalUnitOptions('en')

export function getSimpleIntervalUnitMeta(unit: SimpleIntervalUnit, locale: MessageLocale = 'en'): SimpleIntervalUnitMeta {
  return getSimpleIntervalUnitOptions(locale).find((opt) => opt.value === unit) ?? getSimpleIntervalUnitOptions(locale)[0]!
}

function formatSimpleIntervalUnitText(unit: SimpleIntervalUnit, value: number, locale: MessageLocale): string {
  const meta = getSimpleIntervalUnitMeta(unit, locale)
  const singular: Record<SimpleIntervalUnit, string> = {
    minute: 'minute',
    hour: 'hour',
    day: 'day',
  }
  return Number(value) === 1 ? singular[unit] : meta.unitText
}

export type LargeFileUnit = 'KB' | 'MB' | 'GB'

export interface BackupPolicyForm {
  name: string
  policyActive: boolean
  sectionScheduleEnabled: boolean
  sectionRetentionEnabled: boolean
  sectionRateLimitEnabled: boolean
  sectionErrorHandlingEnabled: boolean
  freqMode: FreqMode
  simpleIntervalUnit: SimpleIntervalUnit
  simpleIntervalValue: number
  cronExpr: string
  retentionRecentPoints: number
  retentionHourlyEnabled: boolean
  retentionHourlyHours: number
  retentionDailyEnabled: boolean
  retentionDailyDays: number
  retentionWeeklyEnabled: boolean
  retentionWeeklyWeeks: number
  retentionMonthlyEnabled: boolean
  retentionMonthlyMonths: number
  retentionAnnualEnabled: boolean
  retentionAnnualYears: number
  /** Legacy UI compatibility: short-term hourly window in days. */
  retentionShortDaysMax: number
  /** Legacy UI compatibility: mid-term daily window in days. */
  retentionMidDaysMax: number
  /** Legacy UI compatibility: long-term monthly retention in months. */
  retentionLongMonths: number
  /** Legacy UI compatibility: hourly retention toggle. */
  retentionShortHourly: boolean
  /** Legacy UI compatibility: daily retention toggle. */
  retentionMidDaily: boolean
  /** Legacy UI compatibility: monthly retention toggle. */
  retentionLongMonthly: boolean
  globalIgnorePatterns: string
  ignoreCacheDirectories: boolean
  largeFileMax: number
  largeFileUnit: LargeFileUnit
  currentFilesystemOnly: boolean
  rateLimitUnlimited: boolean
  rateLimitMbps: number
  errorIgnoreDirectory: boolean
  errorIgnoreFile: boolean
  errorIgnoreUnknownEntries: boolean
}

function formatPolicyNameTimestamp(date = new Date()): string {
  const year = date.getFullYear()
  const month = String(date.getMonth() + 1).padStart(2, '0')
  const day = String(date.getDate()).padStart(2, '0')
  const hour = String(date.getHours()).padStart(2, '0')
  const minute = String(date.getMinutes()).padStart(2, '0')
  return `${year}${month}${day}${hour}${minute}`
}

export function generateDefaultPolicyName(_locale: MessageLocale = 'en'): string {
  void _locale
  return `Backup Policy-${formatPolicyNameTimestamp()}`
}

export function generateDefaultFilterName(_locale: MessageLocale = 'en'): string {
  void _locale
  return `File Filter-${formatPolicyNameTimestamp()}`
}

export function createEmptyPolicyForm(): BackupPolicyForm {
  return {
    name: '',
    policyActive: true,
    sectionScheduleEnabled: true,
    sectionRetentionEnabled: true,
    sectionRateLimitEnabled: false,
    sectionErrorHandlingEnabled: true,
    freqMode: 'simple',
    simpleIntervalUnit: 'hour',
    simpleIntervalValue: 1,
    cronExpr: '0 2 * * *',
    retentionRecentPoints: 10,
    retentionHourlyEnabled: true,
    retentionHourlyHours: 48,
    retentionDailyEnabled: true,
    retentionDailyDays: 30,
    retentionWeeklyEnabled: true,
    retentionWeeklyWeeks: 4,
    retentionMonthlyEnabled: true,
    retentionMonthlyMonths: 12,
    retentionAnnualEnabled: true,
    retentionAnnualYears: 5,
    retentionShortDaysMax: 2,
    retentionMidDaysMax: 30,
    retentionLongMonths: 12,
    retentionShortHourly: true,
    retentionMidDaily: true,
    retentionLongMonthly: true,
    globalIgnorePatterns: '',
    ignoreCacheDirectories: true,
    largeFileMax: 1,
    largeFileUnit: 'GB',
    currentFilesystemOnly: false,
    rateLimitUnlimited: true,
    rateLimitMbps: 100,
    errorIgnoreDirectory: true,
    errorIgnoreFile: false,
    errorIgnoreUnknownEntries: true,
  }
}

export type CronValidationReason = 'empty' | 'format' | null

export interface CronValidationResult {
  ok: boolean
  reason: CronValidationReason
}

export function validateCronExpression(raw: string): CronValidationResult {
  const trimmed = raw.trim()
  if (!trimmed) return { ok: false, reason: 'empty' }
  const fields = trimmed.split(/\s+/)
  if (fields.length !== 5) return { ok: false, reason: 'format' }
  const fieldRe = /^(\*|\d+(-\d+)?)(\/\d+)?(,(\*|\d+(-\d+)?)(\/\d+)?)*$/
  for (const f of fields) {
    if (!fieldRe.test(f)) return { ok: false, reason: 'format' }
  }
  return { ok: true, reason: null }
}

const CRON_WEEKDAY_NAMES_EN = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday'] as const

function cronWeekdayLabel(value: string): string | null {
  const numeric = Number(value)
  if (!Number.isInteger(numeric) || numeric < 0 || numeric > 6) return null
  return CRON_WEEKDAY_NAMES_EN[numeric]!
}

function cronTimeLabel(hour: number, minute: number): string {
  return `${String(hour).padStart(2, '0')}:${String(minute).padStart(2, '0')}`
}

export function humanizeCronExpression(raw: string, locale: MessageLocale = 'en'): string {
  void locale
  const expr = raw.trim()
  if (!expr) return 'Not set'

  const parts = expr.split(/\s+/)
  if (parts.length !== 5) return 'Custom schedule'

  const [min, hour, dom, mon, dow] = parts
  const isStar = (field: string) => field === '*'

  const minuteStep = min.match(/^\*\/(\d+)$/)
  if (minuteStep && isStar(hour) && isStar(dom) && isStar(mon) && isStar(dow)) {
    const n = Number(minuteStep[1])
    return `Every ${n} minute${n === 1 ? '' : 's'}`
  }

  const hourStep = hour.match(/^\*\/(\d+)$/)
  if ((min === '0' || min === '00') && hourStep && isStar(dom) && isStar(mon) && isStar(dow)) {
    const n = Number(hourStep[1])
    return `Every ${n} hour${n === 1 ? '' : 's'}`
  }

  const domStep = dom.match(/^\*\/(\d+)$/)
  if ((min === '0' || min === '00') && (hour === '0' || hour === '00') && domStep && isStar(mon) && isStar(dow)) {
    const n = Number(domStep[1])
    return `Every ${n} day${n === 1 ? '' : 's'}`
  }

  if (/^\d+$/.test(min) && /^\d+$/.test(hour) && isStar(dom) && isStar(mon) && isStar(dow)) {
    const time = cronTimeLabel(Number(hour), Number(min))
    return `Daily at ${time}`
  }

  if (/^\d+$/.test(min) && isStar(hour) && isStar(dom) && isStar(mon) && isStar(dow)) {
    const minute = Number(min)
    return `At minute ${minute} of every hour`
  }

  if ((min === '0' || min === '00') && /^\d+$/.test(hour) && isStar(dom) && isStar(mon) && !isStar(dow)) {
    const weekday = cronWeekdayLabel(dow)
    const time = cronTimeLabel(Number(hour), 0)
    if (weekday) {
      return `Weekly on ${weekday} at ${time}`
    }
  }

  if ((min === '0' || min === '00') && /^\d+$/.test(hour) && /^\d+$/.test(dom) && isStar(mon) && isStar(dow)) {
    const time = cronTimeLabel(Number(hour), 0)
    const day = Number(dom)
    return `Monthly on day ${day} at ${time}`
  }

  return 'Custom schedule'
}

export function summarizeSchedule(f: BackupPolicyForm, locale: MessageLocale = 'en'): string {
  if (!f.sectionScheduleEnabled) {
    return 'Not configured'
  }
  if (f.freqMode === 'simple') {
    const unitText = formatSimpleIntervalUnitText(f.simpleIntervalUnit, f.simpleIntervalValue, locale)
    return `Every ${f.simpleIntervalValue} ${unitText}`
  }
  return humanizeCronExpression(f.cronExpr, locale)
}

function resolveHourlyHours(raw: Partial<BackupPolicyRetention>, fallback: number): number {
  if (raw.hourly_hours != null) {
    const hours = Number(raw.hourly_hours)
    if (Number.isFinite(hours) && hours > 0) return hours
  }
  if (raw.hourly_days != null) {
    const days = Number(raw.hourly_days)
    if (Number.isFinite(days) && days > 0) return days * 24
  }
  return fallback
}

/** Resolve hourly retention for display (supports legacy hourly_days). */
export function resolveRetentionHourlyHours(
  retention: Partial<BackupPolicyRetention> | undefined,
  fallback = 0,
): number {
  return resolveHourlyHours(retention || {}, fallback)
}

function normalizeLegacyRetention(raw: Partial<BackupPolicyRetention>): Partial<BackupPolicyRetention> {
  if (raw.hourly_enabled !== undefined || raw.hourly_hours !== undefined || raw.hourly_days !== undefined) {
    return raw
  }
  const migrated: Partial<BackupPolicyRetention> = { ...raw }
  if ('short_hourly_enabled' in raw) {
    migrated.hourly_enabled = Boolean((raw as Record<string, unknown>).short_hourly_enabled)
    const shortDays = Number((raw as Record<string, unknown>).short_days) || 2
    migrated.hourly_hours = shortDays * 24
  }
  if ('mid_daily_enabled' in raw) {
    migrated.daily_enabled = Boolean((raw as Record<string, unknown>).mid_daily_enabled)
    migrated.daily_days = Number((raw as Record<string, unknown>).mid_days) || 30
  }
  if ('long_monthly_enabled' in raw) {
    migrated.monthly_enabled = Boolean((raw as Record<string, unknown>).long_monthly_enabled)
    migrated.monthly_months = Number((raw as Record<string, unknown>).long_months) || 12
  }
  return migrated
}

export function applyRetentionFromApi(
  retention: Partial<BackupPolicyRetention> | undefined,
  base: BackupPolicyForm,
): Pick<
  BackupPolicyForm,
  | 'sectionRetentionEnabled'
  | 'retentionRecentPoints'
  | 'retentionHourlyEnabled'
  | 'retentionHourlyHours'
  | 'retentionDailyEnabled'
  | 'retentionDailyDays'
  | 'retentionWeeklyEnabled'
  | 'retentionWeeklyWeeks'
  | 'retentionMonthlyEnabled'
  | 'retentionMonthlyMonths'
  | 'retentionAnnualEnabled'
  | 'retentionAnnualYears'
  | 'retentionShortDaysMax'
  | 'retentionMidDaysMax'
  | 'retentionLongMonths'
  | 'retentionShortHourly'
  | 'retentionMidDaily'
  | 'retentionLongMonthly'
> {
  const normalized = normalizeLegacyRetention(retention || {})
  const hourlyHours = resolveHourlyHours(normalized, base.retentionHourlyHours)
  const dailyDays = Number(normalized.daily_days) || base.retentionDailyDays
  const monthlyMonths = Number(normalized.monthly_months) || base.retentionMonthlyMonths
  return {
    sectionRetentionEnabled: Boolean(normalized.enabled),
    retentionRecentPoints: Number(normalized.recent_points) || base.retentionRecentPoints,
    retentionHourlyEnabled: normalized.hourly_enabled ?? false,
    retentionHourlyHours: hourlyHours,
    retentionDailyEnabled: normalized.daily_enabled ?? false,
    retentionDailyDays: dailyDays,
    retentionWeeklyEnabled: normalized.weekly_enabled ?? false,
    retentionWeeklyWeeks: Number(normalized.weekly_weeks) || base.retentionWeeklyWeeks,
    retentionMonthlyEnabled: normalized.monthly_enabled ?? false,
    retentionMonthlyMonths: monthlyMonths,
    retentionAnnualEnabled: normalized.annual_enabled ?? false,
    retentionAnnualYears: Number(normalized.annual_years) || base.retentionAnnualYears,
    retentionShortHourly: normalized.hourly_enabled ?? false,
    retentionShortDaysMax: hourlyHoursToLegacyDays(hourlyHours),
    retentionMidDaily: normalized.daily_enabled ?? false,
    retentionMidDaysMax: dailyDays,
    retentionLongMonthly: normalized.monthly_enabled ?? false,
    retentionLongMonths: monthlyMonths,
  }
}

export function hourlyHoursToLegacyDays(hours: number): number {
  return Math.max(1, Math.ceil(Math.max(1, hours) / 24))
}

export function retentionFormToApi(f: BackupPolicyForm): BackupPolicyRetention {
  const hourlyHours = Math.max(
    1,
    Number.isFinite(Number(f.retentionShortDaysMax))
      ? Math.ceil(Math.max(1, Number(f.retentionShortDaysMax)) * 24)
      : Number(f.retentionHourlyHours) || 1,
  )
  const dailyDays = Math.max(1, Number(f.retentionMidDaysMax) || Number(f.retentionDailyDays) || 1)
  const monthlyMonths = Math.max(1, Number(f.retentionLongMonths) || Number(f.retentionMonthlyMonths) || 1)
  return {
    enabled: f.sectionRetentionEnabled,
    recent_points: Math.max(1, Number(f.retentionRecentPoints) || 1),
    hourly_enabled: f.retentionShortHourly,
    hourly_hours: hourlyHours,
    hourly_days: hourlyHoursToLegacyDays(hourlyHours),
    daily_enabled: f.retentionMidDaily,
    daily_days: dailyDays,
    weekly_enabled: f.retentionWeeklyEnabled,
    weekly_weeks: Math.max(1, Number(f.retentionWeeklyWeeks) || 1),
    monthly_enabled: f.retentionLongMonthly,
    monthly_months: monthlyMonths,
    annual_enabled: f.retentionAnnualEnabled,
    annual_years: Math.max(1, Number(f.retentionAnnualYears) || 1),
  }
}

export function throttlingFormToApi(f: BackupPolicyForm): {
  enabled: boolean
  unlimited: boolean
  rate_mbps: number
} {
  const enabled = f.sectionRateLimitEnabled && !f.rateLimitUnlimited
  return {
    enabled,
    unlimited: !enabled,
    rate_mbps: enabled ? Math.max(1, Number(f.rateLimitMbps) || 1) : 0,
  }
}

export function errorHandlingFormToApi(f: BackupPolicyForm): {
  enabled: boolean
  ignore_directory_read_errors: boolean
  ignore_file_read_errors: boolean
  ignore_unknown_entries: boolean
} {
  const enabled = f.errorIgnoreDirectory || f.errorIgnoreFile || f.errorIgnoreUnknownEntries
  return {
    enabled,
    ignore_directory_read_errors: f.errorIgnoreDirectory,
    ignore_file_read_errors: f.errorIgnoreFile,
    ignore_unknown_entries: f.errorIgnoreUnknownEntries,
  }
}

export function summarizeRetention(f: BackupPolicyForm, _locale: MessageLocale = 'en'): string {
  void _locale
  if (!f.sectionRetentionEnabled) {
    return 'Not configured'
  }
  if (
    f.retentionShortDaysMax !== undefined
    && f.retentionMidDaysMax !== undefined
    && f.retentionLongMonths !== undefined
  ) {
    const recent = `Last ${f.retentionRecentPoints} restore point(s)`
    const parts: string[] = [recent]
    if (f.retentionShortHourly) {
      parts.push(`0-${f.retentionShortDaysMax} d -> hourly tier`)
    }
    if (f.retentionMidDaily) {
      parts.push(`${f.retentionShortDaysMax}-${f.retentionMidDaysMax} d -> daily tier`)
    }
    if (f.retentionLongMonthly) {
      parts.push(`>${f.retentionMidDaysMax} d -> monthly, keep ${f.retentionLongMonths} month(s)`)
    }
    return parts.join('; ')
  }
  const parts: string[] = [`Latest ${f.retentionRecentPoints}`]
  if (f.retentionHourlyEnabled) {
    parts.push(`H ${f.retentionHourlyHours}h`)
  }
  if (f.retentionDailyEnabled) {
    parts.push(`D ${f.retentionDailyDays}d`)
  }
  if (f.retentionWeeklyEnabled) {
    parts.push(`W ${f.retentionWeeklyWeeks}w`)
  }
  if (f.retentionMonthlyEnabled) {
    parts.push(`M ${f.retentionMonthlyMonths}mo`)
  }
  if (f.retentionAnnualEnabled) {
    parts.push(`Y ${f.retentionAnnualYears}y`)
  }
  return parts.join(' · ')
}

export function validateRetentionForm(f: BackupPolicyForm, locale: MessageLocale = 'en'): string {
  if (!f.sectionRetentionEnabled) return ''
  const midRetentionError = validateMidRetention(f, locale)
  if (midRetentionError) return midRetentionError
  const longVsShortRetentionError = validateLongVsShortRetention(f, locale)
  if (longVsShortRetentionError) return longVsShortRetentionError
  const checks: Array<[boolean, number, string]> = [
    [f.retentionHourlyEnabled, f.retentionHourlyHours, 'hourly'],
    [f.retentionDailyEnabled, f.retentionDailyDays, 'daily'],
    [f.retentionWeeklyEnabled, f.retentionWeeklyWeeks, 'weekly'],
    [f.retentionMonthlyEnabled, f.retentionMonthlyMonths, 'monthly'],
    [f.retentionAnnualEnabled, f.retentionAnnualYears, 'annual'],
  ]
  for (const [enabled, value, label] of checks) {
    if (!enabled) continue
    if (typeof value !== 'number' || value < 1) {
      return `${label} retention must be at least 1 when enabled.`
    }
  }
  if (typeof f.retentionRecentPoints !== 'number' || f.retentionRecentPoints < 1) {
    return 'Latest restore points must be at least 1.'
  }
  return ''
}

/** Validate the legacy short/mid retention layout used by the one-week-old UI. */
export function validateMidRetention(f: BackupPolicyForm, _locale: MessageLocale = 'en'): string {
  void _locale
  if (!f.sectionRetentionEnabled) return ''
  if (typeof f.retentionMidDaysMax !== 'number' || typeof f.retentionShortDaysMax !== 'number') {
    return ''
  }
  if (f.retentionMidDaysMax <= f.retentionShortDaysMax) {
    return `Mid-term upper limit must exceed short-term upper limit (current short-term: ${f.retentionShortDaysMax} days).`
  }
  return ''
}

const DAYS_PER_MONTH = 30

/** Validate the legacy long/month retention layout used by the one-week-old UI. */
export function validateLongVsShortRetention(f: BackupPolicyForm, _locale: MessageLocale = 'en'): string {
  void _locale
  if (!f.sectionRetentionEnabled) return ''
  if (!f.retentionLongMonthly) return ''
  const months = f.retentionLongMonths
  const shortDays = f.retentionShortDaysMax
  if (typeof months !== 'number' || typeof shortDays !== 'number') return ''
  if (months * DAYS_PER_MONTH <= shortDays) {
    return `Long-term months (as ~${DAYS_PER_MONTH} d/month) must exceed the short-term cap (${shortDays} d). Increase months or lower the short-term cap.`
  }
  return ''
}

export function summarizeFilters(_f: BackupPolicyForm, _locale: MessageLocale = 'en'): string {
  void _locale
  return '—'
}

export type FilterCustomRuleType = 'exclude' | 'include'
export type FileFilterOsScope = 'all' | 'linux' | 'windows'

export interface FilterCustomRuleEntry {
  type: FilterCustomRuleType
  pattern: string
}

export const FILTER_PRESET_TEMP_PATTERNS = [
  '*.tmp',
  '*.log',
  '*.bak',
  '*.old',
  '*.swp',
  '*~',
  '.DS_Store',
  'Thumbs.db',
  'desktop.ini',
] as const

export const FILTER_PRESET_DEV_PATTERNS = [
  '**/node_modules/**',
  '**/.git/**',
  '**/.cache/**',
  '**/__pycache__/**',
  '**/.venv/**',
  '**/venv/**',
] as const

export const FILTER_PRESET_SYSTEM_PATTERNS = [
  '**/$RECYCLE.BIN/**',
  '**/$Recycle.Bin/**',
  '**/System Volume Information/**',
  '**/.Trash/**',
  '**/.Trashes/**',
] as const

export interface FileFilterRuleForm {
  name: string
  policyActive: boolean
  osScope: FileFilterOsScope
  presetTempFiles: boolean
  presetDevDeps: boolean
  presetSystemJunk: boolean
  customRules: FilterCustomRuleEntry[]
  globalIgnorePatterns: string
  largeFileLimitEnabled: boolean
  ignoreCacheDirectories: boolean
  largeFileMax: number
  largeFileUnit: LargeFileUnit
  currentFilesystemOnly: boolean
}

export function createEmptyFilterCustomRule(): FilterCustomRuleEntry {
  return { type: 'exclude', pattern: '' }
}

export function compileFilterIgnorePatterns(
  form: Pick<FileFilterRuleForm, 'presetTempFiles' | 'presetDevDeps' | 'presetSystemJunk' | 'customRules'>,
): string {
  const lines: string[] = []
  if (form.presetTempFiles) lines.push(...FILTER_PRESET_TEMP_PATTERNS)
  if (form.presetDevDeps) lines.push(...FILTER_PRESET_DEV_PATTERNS)
  if (form.presetSystemJunk) lines.push(...FILTER_PRESET_SYSTEM_PATTERNS)
  for (const rule of form.customRules) {
    const pattern = rule.pattern.trim()
    if (!pattern) continue
    if (rule.type === 'include') {
      lines.push(pattern.startsWith('!') ? pattern : `!${pattern}`)
    } else {
      lines.push(pattern)
    }
  }
  const seen = new Set<string>()
  return lines.filter((line) => {
    if (seen.has(line)) return false
    seen.add(line)
    return true
  }).join('\n')
}

function hasAllPatterns(lines: string[], patterns: readonly string[]) {
  return patterns.every((pattern) => lines.includes(pattern))
}

function removePatterns(lines: string[], patterns: readonly string[]) {
  for (const pattern of patterns) {
    const index = lines.indexOf(pattern)
    if (index >= 0) lines.splice(index, 1)
  }
}

export function parseFilterIgnorePatterns(text: string): Pick<FileFilterRuleForm, 'presetTempFiles' | 'presetDevDeps' | 'presetSystemJunk' | 'customRules'> {
  const remaining = text.split(/\r?\n/).map((line) => line.trim()).filter(Boolean)
  const presetTempFiles = hasAllPatterns(remaining, FILTER_PRESET_TEMP_PATTERNS)
  if (presetTempFiles) removePatterns(remaining, FILTER_PRESET_TEMP_PATTERNS)
  const presetDevDeps = hasAllPatterns(remaining, FILTER_PRESET_DEV_PATTERNS)
  if (presetDevDeps) removePatterns(remaining, FILTER_PRESET_DEV_PATTERNS)
  const presetSystemJunk = hasAllPatterns(remaining, FILTER_PRESET_SYSTEM_PATTERNS)
  if (presetSystemJunk) removePatterns(remaining, FILTER_PRESET_SYSTEM_PATTERNS)
  const customRules = remaining.map((line) => ({ type: 'exclude' as const, pattern: line }))
  return {
    presetTempFiles,
    presetDevDeps,
    presetSystemJunk,
    customRules: customRules.length ? customRules : [createEmptyFilterCustomRule()],
  }
}

export function syncFilterFormIgnorePatterns(form: FileFilterRuleForm) {
  form.globalIgnorePatterns = compileFilterIgnorePatterns(form)
}

export function applyFilterIgnorePatternsToForm(form: FileFilterRuleForm, text: string) {
  Object.assign(form, parseFilterIgnorePatterns(text))
  form.globalIgnorePatterns = compileFilterIgnorePatterns(form)
}

function collectPresetExtensionPatterns(patterns: readonly string[]): string[] {
  return patterns.filter((pattern) => pattern.includes('*.'))
}

function collectPresetPathPatterns(patterns: readonly string[]): string[] {
  return patterns
    .filter((pattern) => !pattern.includes('*.'))
    .map((pattern) => pattern.replace(/^\*\*\//, '').replace(/\/\*\*$/, '/'))
}

function joinFilterRuleParts(ext: string, paths: string, locale: MessageLocale): string {
  void locale
  const none = 'None'
  if (ext === none && paths === none) return none
  if (ext === none) return paths
  if (paths === none) return ext
  return `${ext} · ${paths}`
}

export function getFilterExcludedExtensions(
  form: Pick<FileFilterRuleForm, 'presetTempFiles' | 'presetDevDeps' | 'presetSystemJunk' | 'customRules'>,
  locale: MessageLocale = 'en',
): string {
  void locale
  const exts: string[] = []
  if (form.presetTempFiles) exts.push(...collectPresetExtensionPatterns(FILTER_PRESET_TEMP_PATTERNS))
  if (form.presetDevDeps) exts.push(...collectPresetExtensionPatterns(FILTER_PRESET_DEV_PATTERNS))
  if (form.presetSystemJunk) exts.push(...collectPresetExtensionPatterns(FILTER_PRESET_SYSTEM_PATTERNS))
  for (const rule of form.customRules) {
    if (rule.type !== 'exclude') continue
    const pattern = rule.pattern.trim()
    if (!pattern.includes('*.')) continue
    exts.push(pattern.substring(pattern.indexOf('*.')))
  }
  if (!exts.length) return 'None'
  return exts.join(', ')
}

export function getFilterExcludedPaths(
  form: Pick<FileFilterRuleForm, 'presetTempFiles' | 'presetDevDeps' | 'presetSystemJunk' | 'customRules'>,
  locale: MessageLocale = 'en',
): string {
  void locale
  const paths: string[] = []
  if (form.presetTempFiles) paths.push(...collectPresetPathPatterns(FILTER_PRESET_TEMP_PATTERNS))
  if (form.presetDevDeps) paths.push(...collectPresetPathPatterns(FILTER_PRESET_DEV_PATTERNS))
  if (form.presetSystemJunk) paths.push(...collectPresetPathPatterns(FILTER_PRESET_SYSTEM_PATTERNS))
  for (const rule of form.customRules) {
    if (rule.type !== 'exclude') continue
    const pattern = rule.pattern.trim()
    if (!pattern || pattern.includes('*.')) continue
    paths.push(pattern)
  }
  if (!paths.length) return 'None'
  return paths.join(', ')
}

export function getFilterIncludedExtensions(
  form: Pick<FileFilterRuleForm, 'customRules'>,
  locale: MessageLocale = 'en',
): string {
  void locale
  const exts: string[] = []
  for (const rule of form.customRules) {
    if (rule.type !== 'include') continue
    const pattern = rule.pattern.trim()
    if (!pattern.includes('*.')) continue
    exts.push(pattern.substring(pattern.indexOf('*.')))
  }
  if (!exts.length) return 'None'
  return exts.join(', ')
}

export function getFilterIncludedPaths(
  form: Pick<FileFilterRuleForm, 'customRules'>,
  locale: MessageLocale = 'en',
): string {
  void locale
  const paths: string[] = []
  for (const rule of form.customRules) {
    if (rule.type !== 'include') continue
    const pattern = rule.pattern.trim()
    if (!pattern || pattern.includes('*.')) continue
    paths.push(pattern)
  }
  if (!paths.length) return 'None'
  return paths.join(', ')
}

export function buildFilterPresetsPreviewSummary(
  form: Pick<FileFilterRuleForm, 'presetTempFiles' | 'presetDevDeps' | 'presetSystemJunk'>,
  locale: MessageLocale = 'en',
): string {
  void locale
  const short = { temp: 'Temp', dev: 'Dev', system: 'System' }
  const parts: string[] = []
  if (form.presetTempFiles) parts.push(short.temp)
  if (form.presetDevDeps) parts.push(short.dev)
  if (form.presetSystemJunk) parts.push(short.system)
  return parts.length ? parts.join(' · ') : 'None'
}

export function buildFilterExcludePreviewSummary(
  form: Pick<FileFilterRuleForm, 'presetTempFiles' | 'presetDevDeps' | 'presetSystemJunk' | 'customRules'>,
  locale: MessageLocale = 'en',
): string {
  return joinFilterRuleParts(
    getFilterExcludedExtensions(form, locale),
    getFilterExcludedPaths(form, locale),
    locale,
  )
}

export function buildFilterIncludePreviewSummary(
  form: Pick<FileFilterRuleForm, 'customRules'>,
  locale: MessageLocale = 'en',
): string {
  return joinFilterRuleParts(
    getFilterIncludedExtensions(form, locale),
    getFilterIncludedPaths(form, locale),
    locale,
  )
}

export function buildFilterAdvancedPreviewSummary(
  form: Pick<
    FileFilterRuleForm,
    | 'largeFileLimitEnabled'
    | 'largeFileMax'
    | 'largeFileUnit'
    | 'ignoreCacheDirectories'
    | 'currentFilesystemOnly'
  >,
  locale: MessageLocale = 'en',
): string {
  void locale
  const parts: string[] = []
  parts.push(
    form.largeFileLimitEnabled
      ? `>${form.largeFileMax} ${form.largeFileUnit}`
      : 'No size limit',
  )
  parts.push(
    form.ignoreCacheDirectories
      ? 'Skip cache directories'
      : 'Include cache directories',
  )
  parts.push(
    form.currentFilesystemOnly
      ? 'Current filesystem only'
      : 'Cross filesystems',
  )
  return parts.join(' · ')
}

export function applyLegacyFileFilterCacheFlag(form: FileFilterRuleForm, ignoreCacheDirectories: boolean) {
  form.ignoreCacheDirectories = ignoreCacheDirectories
}

export function createEmptyFileFilterForm(): FileFilterRuleForm {
  const form: FileFilterRuleForm = {
    name: '',
    policyActive: true,
    osScope: 'all',
    presetTempFiles: true,
    presetDevDeps: true,
    presetSystemJunk: true,
    customRules: [createEmptyFilterCustomRule()],
    globalIgnorePatterns: '',
    largeFileLimitEnabled: false,
    ignoreCacheDirectories: false,
    largeFileMax: 500,
    largeFileUnit: 'MB',
    currentFilesystemOnly: false,
  }
  syncFilterFormIgnorePatterns(form)
  return form
}

export interface FileFilterListSummaryLine {
  prefix: string
  value: string
}

export function buildFileFilterListSummaryLines(
  f: FileFilterRuleForm,
  locale: MessageLocale = 'en',
): FileFilterListSummaryLine[] {
  syncFilterFormIgnorePatterns(f)
  const excludePrefix = 'Exclude'
  return [
    {
      prefix: excludePrefix,
      value: buildFilterExcludePreviewSummary(f, locale),
    },
    {
      prefix: 'Advanced',
      value: buildFilterAdvancedPreviewSummary(f, locale),
    },
  ]
}

export function summarizeFileFilterRuleForm(f: FileFilterRuleForm, locale: MessageLocale = 'en'): string {
  return buildFileFilterListSummaryLines(f, locale)
    .map((line) => `${line.prefix}: ${line.value}`)
    .join('\n')
}

const LARGE_FILE_UNIT_BYTES = {
  KB: 1024,
  MB: 1024 * 1024,
  GB: 1024 * 1024 * 1024,
} as const

export function simpleIntervalToCron(policyForm: BackupPolicyForm): string {
  const value = Math.max(1, Number(policyForm.simpleIntervalValue) || 1)
  if (policyForm.simpleIntervalUnit === 'minute') return `*/${value} * * * *`
  if (policyForm.simpleIntervalUnit === 'hour') return `0 */${value} * * *`
  return `0 0 */${value} * *`
}

export function parseSimpleIntervalFromCron(raw: string): {
  unit: SimpleIntervalUnit
  value: number
} | null {
  const cron = raw.trim().replace(/\s+/g, ' ')
  const minute = /^\*\/(\d+) \* \* \* \*$/.exec(cron)
  if (minute) {
    const value = Number(minute[1])
    if (Number.isFinite(value) && value >= 1) return { unit: 'minute', value }
  }
  const hour = /^0 \*\/(\d+) \* \* \*$/.exec(cron)
  if (hour) {
    const value = Number(hour[1])
    if (Number.isFinite(value) && value >= 1) return { unit: 'hour', value }
  }
  const day = /^0 0 \*\/(\d+) \* \*$/.exec(cron)
  if (day) {
    const value = Number(day[1])
    if (Number.isFinite(value) && value >= 1) return { unit: 'day', value }
  }
  return null
}

function applyScheduleFromApi(
  cronExpr: string | undefined,
  base: BackupPolicyForm,
): Pick<BackupPolicyForm, 'freqMode' | 'simpleIntervalUnit' | 'simpleIntervalValue' | 'cronExpr'> {
  const expr = (cronExpr || base.cronExpr).trim()
  const parsed = parseSimpleIntervalFromCron(expr)
  if (parsed) {
    return {
      freqMode: 'simple',
      simpleIntervalUnit: parsed.unit,
      simpleIntervalValue: parsed.value,
      cronExpr: expr,
    }
  }
  return {
    freqMode: 'advanced',
    simpleIntervalUnit: base.simpleIntervalUnit,
    simpleIntervalValue: base.simpleIntervalValue,
    cronExpr: expr || base.cronExpr,
  }
}

export function backupPolicyToForm(policy: BackupPolicy): BackupPolicyForm {
  const base = createEmptyPolicyForm()
  return {
    ...base,
    name: policy.name,
    policyActive: policy.is_active,
    sectionScheduleEnabled: Boolean(policy.schedule?.enabled),
    ...applyScheduleFromApi(policy.schedule?.cron_expr, base),
    ...applyRetentionFromApi(policy.retention, base),
    sectionRateLimitEnabled: Boolean(policy.throttling?.enabled),
    rateLimitUnlimited: Boolean(policy.throttling?.unlimited),
    rateLimitMbps: Number(policy.throttling?.rate_mbps) || base.rateLimitMbps,
    sectionErrorHandlingEnabled: Boolean(policy.error_handling?.enabled),
    errorIgnoreDirectory: Boolean(policy.error_handling?.ignore_directory_read_errors),
    errorIgnoreFile: Boolean(policy.error_handling?.ignore_file_read_errors),
    errorIgnoreUnknownEntries: Boolean(policy.error_handling?.ignore_unknown_entries),
  }
}

/** Keep the schedule mode the user chose after save; API only stores cron. */
export function preserveScheduleFormMode(
  form: BackupPolicyForm,
  saved: BackupPolicyForm,
): BackupPolicyForm {
  if (saved.freqMode === 'simple') {
    return {
      ...form,
      freqMode: 'simple',
      simpleIntervalUnit: saved.simpleIntervalUnit,
      simpleIntervalValue: saved.simpleIntervalValue,
    }
  }
  return {
    ...form,
    freqMode: 'advanced',
    cronExpr: saved.cronExpr.trim() || form.cronExpr,
  }
}

export function policyFormToWritePayload(policyForm: BackupPolicyForm): BackupPolicyWritePayload {
  const cronExpr = policyForm.freqMode === 'advanced'
    ? policyForm.cronExpr.trim()
    : simpleIntervalToCron(policyForm)
  return {
    name: policyForm.name.trim(),
    is_active: policyForm.policyActive,
    schedule: {
      enabled: policyForm.sectionScheduleEnabled,
      cron_expr: cronExpr || '0 0 * * *',
    },
    retention: retentionFormToApi(policyForm),
    throttling: throttlingFormToApi(policyForm),
    error_handling: errorHandlingFormToApi(policyForm),
  }
}

function largeFileBytesToForm(bytes: number): Pick<FileFilterRuleForm, 'largeFileMax' | 'largeFileUnit'> {
  const safe = Math.max(0, Number(bytes) || 0)
  if (safe >= LARGE_FILE_UNIT_BYTES.GB && safe % LARGE_FILE_UNIT_BYTES.GB === 0) {
    return { largeFileMax: safe / LARGE_FILE_UNIT_BYTES.GB, largeFileUnit: 'GB' }
  }
  if (safe >= LARGE_FILE_UNIT_BYTES.MB && safe % LARGE_FILE_UNIT_BYTES.MB === 0) {
    return { largeFileMax: safe / LARGE_FILE_UNIT_BYTES.MB, largeFileUnit: 'MB' }
  }
  return {
    largeFileMax: safe > 0 ? Math.max(1, Math.round(safe / LARGE_FILE_UNIT_BYTES.KB)) : 1,
    largeFileUnit: 'KB',
  }
}

export function fileFilterRuleToForm(rule: FileFilterRule): FileFilterRuleForm {
  const large = largeFileBytesToForm(Number(rule.large_file_bytes_max) || 0)
  const form = {
    ...createEmptyFileFilterForm(),
    name: rule.name,
    policyActive: rule.is_active,
    largeFileLimitEnabled: Boolean(rule.large_file_limit_enabled),
    largeFileMax: large.largeFileMax,
    largeFileUnit: large.largeFileUnit,
    currentFilesystemOnly: Boolean(rule.current_filesystem_only),
  }
  applyFilterIgnorePatternsToForm(form, rule.ignore_patterns || '')
  applyLegacyFileFilterCacheFlag(form, Boolean(rule.ignore_cache_directories))
  return form
}

export function fileFilterFormToWritePayload(value: FileFilterRuleForm): FileFilterRuleWritePayload {
  syncFilterFormIgnorePatterns(value)
  const unit = value.largeFileUnit
  return {
    name: value.name.trim(),
    is_active: value.policyActive,
    ignore_patterns: value.globalIgnorePatterns.trim(),
    large_file_limit_enabled: value.largeFileLimitEnabled,
    large_file_bytes_max: value.largeFileLimitEnabled
      ? Math.max(0, Number(value.largeFileMax) || 0) * LARGE_FILE_UNIT_BYTES[unit]
      : 0,
    ignore_cache_directories: value.ignoreCacheDirectories,
    current_filesystem_only: value.currentFilesystemOnly,
  }
}
