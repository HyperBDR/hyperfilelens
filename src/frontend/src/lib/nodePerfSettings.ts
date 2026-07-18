import type { ApiNode } from '../types/node'

export type NodePerfLogLevel = 'debug' | 'info' | 'warning' | 'error'

export type NodePerfSettings = {
  bandwidth: number
  cpuCores: number
  memCapMb: number
  log: NodePerfLogLevel
  logRetention: number
  logSpaceMb: number
}

const PERF_SETTINGS_KEY = 'perf_settings'

export function buildDefaultNodePerfSettings(hostCpuCores: number, hostMemMb: number): NodePerfSettings {
  return {
    bandwidth: 20,
    cpuCores: Math.min(2, Math.max(1, hostCpuCores)),
    memCapMb: Math.min(2048, Math.max(128, hostMemMb)),
    log: 'info',
    logRetention: 30,
    logSpaceMb: 512,
  }
}

function asLogLevel(value: unknown): NodePerfLogLevel | null {
  if (value === 'debug' || value === 'info' || value === 'warning' || value === 'error') return value
  return null
}

function asPositiveInt(value: unknown): number | null {
  const n = Number(value)
  if (!Number.isFinite(n) || n < 1) return null
  return Math.round(n)
}

export function readNodePerfSettings(
  node: { metadata?: Record<string, unknown> } | null | undefined,
  defaults: NodePerfSettings,
): NodePerfSettings {
  const raw = node?.metadata?.[PERF_SETTINGS_KEY]
  if (!raw || typeof raw !== 'object') return { ...defaults }
  const obj = raw as Record<string, unknown>
  const log = asLogLevel(obj.log)
  return {
    bandwidth: asPositiveInt(obj.bandwidth) ?? defaults.bandwidth,
    cpuCores: asPositiveInt(obj.cpuCores) ?? defaults.cpuCores,
    memCapMb: asPositiveInt(obj.memCapMb) ?? defaults.memCapMb,
    log: log ?? defaults.log,
    logRetention: asPositiveInt(obj.logRetention) ?? defaults.logRetention,
    logSpaceMb: asPositiveInt(obj.logSpaceMb) ?? defaults.logSpaceMb,
  }
}

export function mergeNodeMetadataWithPerfSettings(
  node: Pick<ApiNode, 'metadata'>,
  settings: NodePerfSettings,
): Record<string, unknown> {
  return {
    ...(node.metadata || {}),
    [PERF_SETTINGS_KEY]: settings,
  }
}
