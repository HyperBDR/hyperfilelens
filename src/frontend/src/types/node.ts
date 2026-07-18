import type { NodeLifecycleInfo, NodeWorkloadInfo } from './nodeLifecycle'

export type NodeRole = 'agent' | 'proxy' | 'gateway'
export type NodeStatus = 'online' | 'reconnecting' | 'offline'

export type ApiNode = {
  id: number
  organization: number
  name: string
  role: NodeRole
  version?: string
  os_name?: string
  ip_address?: string | null
  status: NodeStatus
  routable?: boolean
  last_seen_at?: string | null
  metadata?: Record<string, unknown>
  created_at?: string
  updated_at?: string
  agent_control_ws_path?: string
  lifecycle?: NodeLifecycleInfo | null
  workload?: NodeWorkloadInfo | null
}

export type ApiNodeToken = {
  id: number
  organization: number
  token: string
  role: NodeRole
  note?: string
  is_active: boolean
  created_at?: string
  expires_at?: string | null
  used_at?: string | null
}

export type CreateNodeTokenBody = {
  role: NodeRole
  note?: string
  expires_at?: string | null
  is_active?: boolean
}

export type UpdateNodeBody = {
  name?: string
  ip_address?: string | null
  version?: string
  os_name?: string
  metadata?: Record<string, unknown>
}
