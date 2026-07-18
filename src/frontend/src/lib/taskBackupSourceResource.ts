import { getNode } from './nodeApi'
import { getSourceResource } from './sourceApi'
import type { TaskResourceRow } from './taskApi'
import type { FlowSourceRow } from '../pages/protection/composables/useFlowSourceAggregate'

export type TaskBackupSourceResourceDisplay = {
  backupSource: string
  endpointName: string
  endpointIp: string
  registeredAt: string
  status: string
  statusValue: string
  flowSource: FlowSourceRow
}

const EMPTY = '—'

export async function resolveTaskBackupSourceResource(
  resource: TaskResourceRow,
  sourceType: string,
  signal?: AbortSignal,
): Promise<TaskBackupSourceResourceDisplay> {
  if (sourceType === 'agent') {
    const node = await getNode(resource.resource_id, { signal })
    const metadata = node.metadata || {}
    const hostname = String(metadata.hostname || node.name || EMPTY)
    const platformValue = String(node.os_name || metadata.os || '').toLowerCase()
    const platform = platformValue
      ? platformValue.includes('win')
        ? 'windows'
        : platformValue.includes('mac') || platformValue.includes('darwin')
          ? 'macos'
          : 'linux'
      : undefined
    const flowSource: FlowSourceRow = {
      id: `agent:${node.id}`,
      refId: node.id,
      name: node.name || EMPTY,
      hostname,
      nodeName: node.name || EMPTY,
      nodeIp: node.ip_address || '',
      status: node.status === 'online' ? 'online' : 'offline',
      registeredAt: node.created_at || '',
      type: 'host',
      platform,
    }
    return {
      backupSource: node.name || EMPTY,
      endpointName: hostname,
      endpointIp: node.ip_address || EMPTY,
      registeredAt: node.created_at || '',
      status: node.status || '',
      statusValue: node.status || '',
      flowSource,
    }
  }

  const source = await getSourceResource(resource.resource_id, { signal })
  const boundNode = source.bound_node ? await getNode(source.bound_node, { signal }) : null
  const protocolValue = String(source.config?.protocol || '').toLowerCase()
  const protocol = protocolValue === 'smb' ? 'smb' : protocolValue === 'nfs' ? 'nfs' : undefined
  const flowSource: FlowSourceRow = {
    id: `nas:${source.id}`,
    refId: source.id,
    name: source.name || EMPTY,
    hostname: source.name || EMPTY,
    nodeName: boundNode?.name || source.bound_node_name || '',
    nodeIp: boundNode?.ip_address || '',
    status: source.status === 'online' || source.status === 'active' ? 'online' : 'offline',
    registeredAt: source.created_at || '',
    type: 'nas',
    protocol,
    boundNodeId: source.bound_node,
    mountStatus: source.mount_status,
    mountPoint: source.mount_point,
  }
  return {
    backupSource: source.name || EMPTY,
    endpointName: boundNode?.name || source.bound_node_name || EMPTY,
    endpointIp: boundNode?.ip_address || EMPTY,
    registeredAt: source.created_at || '',
    status: source.status_display || source.status || '',
    statusValue: source.status || '',
    flowSource,
  }
}
