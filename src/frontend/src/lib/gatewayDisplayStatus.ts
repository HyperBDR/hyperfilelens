import type { ApiNode } from '../types/node'

export type GatewayAiPhase = 'not_provisioned' | 'pending_install' | 'online' | 'offline' | 'error'

export type GatewayDisplayStatus = {
  labelKey: string
  tagType: 'success' | 'warning' | 'danger' | 'info'
  tagClass?: string
  spinning?: boolean
}

const AGENT_ONLINE_KEY = 'protection.sourceResources.nodeStatusOnline'

export function resolveGatewayDisplayStatus(
  node: ApiNode,
  aiPhase: GatewayAiPhase,
  resolveDisplayStatus: (node: ApiNode) => GatewayDisplayStatus,
): GatewayDisplayStatus {
  const agentDisplay = resolveDisplayStatus(node)
  if (agentDisplay.labelKey !== AGENT_ONLINE_KEY) {
    return agentDisplay
  }

  switch (aiPhase) {
    case 'online':
      return { labelKey: 'insight.dataGateway.gatewayPhase.online', tagType: 'success' }
    case 'not_provisioned':
      return { labelKey: 'insight.dataGateway.gatewayPhase.setup_incomplete', tagType: 'info' }
    case 'pending_install':
      return {
        labelKey: 'insight.dataGateway.gatewayPhase.installing',
        tagType: 'info',
        spinning: true,
      }
    case 'offline':
      return { labelKey: 'insight.dataGateway.gatewayPhase.degraded', tagType: 'danger' }
    case 'error':
      return { labelKey: 'insight.dataGateway.gatewayPhase.error', tagType: 'danger' }
    default:
      return agentDisplay
  }
}
