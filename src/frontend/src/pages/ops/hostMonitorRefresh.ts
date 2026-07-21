export type HostMonitorTimePreset = {
  value: string
  hours: number
}

export type HostMonitorRefreshTarget =
  | { kind: 'custom' }
  | { kind: 'preset'; value: string; hours: number }

export function resolveHostMonitorRefreshTarget(
  selectedOption: string,
  customRange: { start: string; end: string },
  presets: HostMonitorTimePreset[],
): HostMonitorRefreshTarget {
  if (selectedOption === 'custom' && customRange.start && customRange.end) {
    const start = new Date(customRange.start)
    const end = new Date(customRange.end)
    if (!Number.isNaN(start.getTime()) && !Number.isNaN(end.getTime())) {
      return { kind: 'custom' }
    }
  }

  const selectedPreset = presets.find((preset) => preset.value === selectedOption)
  const fallbackPreset = presets.find((preset) => preset.value === '24h')
  return {
    kind: 'preset',
    value: selectedPreset?.value ?? fallbackPreset?.value ?? '24h',
    hours: selectedPreset?.hours ?? fallbackPreset?.hours ?? 24,
  }
}
