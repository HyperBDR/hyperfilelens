import type { LensGatewayInsight } from './lensApi'
import type { GatewayAiPhase } from './gatewayDisplayStatus'

export function gatewaySelectLine(gateway: Pick<LensGatewayInsight, 'name' | 'ip_address'>): string {
  const name = gateway.name?.trim() || '—'
  const ip = gateway.ip_address?.trim() || '—'
  return `${name} (${ip})`
}

export function gatewayAiPhase(gateway: LensGatewayInsight): GatewayAiPhase {
  if (!gateway.ai_enabled) return 'not_provisioned'
  const status = gateway.sidecar_status
  if (status === 'online') return 'online'
  if (status === 'offline') return 'offline'
  if (status === 'error') return 'error'
  if (status === 'not_deployed') return 'error'
  return 'pending_install'
}

export function gatewayAiPhaseLabelKey(phase: GatewayAiPhase): string {
  if (phase === 'pending_install') return 'insight.dataGateway.gatewayPhase.installing'
  return `insight.dataGateway.gatewayPhase.${phase}`
}

export function gatewayAiPhaseTagType(phase: GatewayAiPhase): 'success' | 'warning' | 'danger' | 'info' {
  switch (phase) {
    case 'online':
      return 'success'
    case 'not_provisioned':
      return 'info'
    case 'pending_install':
      return 'info'
    case 'offline':
      return 'danger'
    case 'error':
      return 'danger'
    default:
      return 'info'
  }
}
