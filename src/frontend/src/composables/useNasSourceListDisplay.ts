import { type Ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { debouncedNodeStatus } from './useNodeConnectionDisplay'
import { formatAppDateTime } from '../lib/dateTime'
import {
  proxyNodeStackIpLine,
  proxyNodeStackPrimaryLine,
} from '../lib/nodeInventoryDisplay'
import {
  nasMountProtocol,
  nasProxyMountPoint,
  nasServerAddress,
  nasShareOrExport,
} from '../lib/sourceNasDisplay'
import type { SourceResource } from '../lib/sourceApi'
import type { ApiNode } from '../types/node'

export type NasListProtocol = 'smb' | 'nfs' | 'nas'

export const NAS_SOURCE_TABLE_HEADER_STYLE: Record<string, string> = {
  background: 'rgba(248, 250, 252, 0.96)',
  color: 'rgb(71 85 105)',
  fontWeight: '600',
  whiteSpace: 'nowrap',
}

function sourceConfigValue(row: SourceResource, key: string) {
  const value = row.config?.[key]
  return typeof value === 'string' ? value : ''
}

export function useNasSourceListDisplay(proxyNodes: Ref<ApiNode[]>) {
  const { t } = useI18n()

  function boundNodeForRow(row: SourceResource) {
    return proxyNodes.value.find((node) =>
      node.id === row.bound_node || (!!row.bound_node_name && node.name === row.bound_node_name),
    )
  }

  function formatBytes(n?: number) {
    const v = Number(n || 0)
    if (!v) return '—'
    const units = ['B', 'KB', 'MB', 'GB', 'TB']
    let u = 0
    let x = v
    while (x >= 1024 && u < units.length - 1) {
      x /= 1024
      u += 1
    }
    return `${x.toFixed(1)} ${units[u]}`
  }

  function formatDate(iso?: string | null) {
    return formatAppDateTime(iso, '—')
  }

  function sourceNodeName(row: SourceResource) {
    return row.bound_node_name || boundNodeForRow(row)?.name || '—'
  }

  function sourceNodeIp(row: SourceResource) {
    return sourceConfigValue(row, 'host_ip') || boundNodeForRow(row)?.ip_address?.trim() || '—'
  }

  function sourceNodeOnlineStatus(row: SourceResource): 'online' | 'reconnecting' | 'offline' {
    const explicit = (row.bound_node_status || '').trim().toLowerCase()
    if (explicit === 'online' || explicit === 'reconnecting' || explicit === 'offline') {
      return explicit
    }
    const node = boundNodeForRow(row)
    if (node) return debouncedNodeStatus(node)
    return 'offline'
  }

  function sourceNodeOnlineLabel(row: SourceResource) {
    const status = sourceNodeOnlineStatus(row)
    if (status === 'online') return t('protection.sourceResources.nodeStatusOnline')
    if (status === 'reconnecting') return t('protection.sourceResources.nodeStatusReconnecting')
    return t('protection.sourceResources.nodeStatusOffline')
  }

  function sourceNodeOnlineTagType(row: SourceResource): 'success' | 'info' | 'danger' {
    const status = sourceNodeOnlineStatus(row)
    if (status === 'online') return 'success'
    if (status === 'reconnecting') return 'info'
    return 'danger'
  }

  function sourceRegisteredAt(row: SourceResource) {
    const node = boundNodeForRow(row)
    return node?.created_at || row.created_at || row.updated_at || null
  }

  function nasProtocolType(row: SourceResource): NasListProtocol {
    const explicit = sourceConfigValue(row, 'protocol').toLowerCase()
    if (explicit === 'smb' || explicit === 'nfs') return explicit
    const detected = nasMountProtocol(row)
    if (detected) return detected
    return 'nas'
  }

  function nasProtocolLabel(row: SourceResource) {
    const protocol = nasProtocolType(row)
    if (protocol === 'smb') return t('repositoriesPage.protocolSmb')
    if (protocol === 'nfs') return t('repositoriesPage.protocolNfs')
    return 'NAS'
  }

  function nasProtocolPillClass(row: SourceResource) {
    const protocol = nasProtocolType(row)
    if (protocol === 'smb') return 'repo-protocol-pill repo-protocol-pill--smb'
    if (protocol === 'nfs') return 'repo-protocol-pill repo-protocol-pill--nfs'
    return 'repo-protocol-pill'
  }

  function nasSourceProxyName(row: SourceResource) {
    const node = boundNodeForRow(row)
    const name = node?.name?.trim() || row.bound_node_name?.trim() || sourceNodeName(row)
    if (!name || name === '—') return ''
    return proxyNodeStackPrimaryLine(name, node, row.bound_node)
  }

  function nasSourceProxyIp(row: SourceResource) {
    const node = boundNodeForRow(row)
    return proxyNodeStackIpLine(node, sourceNodeIp(row) !== '—' ? sourceNodeIp(row) : '')
  }

  return {
    formatBytes,
    formatDate,
    nasMountProtocol,
    nasProtocolType,
    nasProtocolLabel,
    nasProtocolPillClass,
    nasServerAddress,
    nasShareOrExport,
    nasProxyMountPoint,
    nasSourceProxyName,
    nasSourceProxyIp,
    sourceNodeOnlineStatus,
    sourceNodeOnlineLabel,
    sourceNodeOnlineTagType,
    sourceRegisteredAt,
  }
}
