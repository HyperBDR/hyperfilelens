/** Debounce transient reconnecting for node connection status display. */

import type { NodeStatus, ApiNode } from '../types/node'

const RECONNECT_DEBOUNCE_POLLS = 2

type NodeStreak = {
  lastStable: NodeStatus
  reconnectPolls: number
}

const streakByNodeId = new Map<number, NodeStreak>()

function defaultStableStatus(): NodeStatus {
  return 'online'
}

/**
 * Return UI-facing connection status with reconnecting debounce.
 * ``online`` / ``offline`` apply immediately; ``reconnecting`` requires two polls.
 */
export function debouncedNodeStatus(node: Pick<ApiNode, 'id' | 'status'>): NodeStatus {
  const raw = node.status
  const nodeId = node.id

  if (raw === 'online' || raw === 'offline') {
    streakByNodeId.set(nodeId, { lastStable: raw, reconnectPolls: 0 })
    return raw
  }

  if (raw !== 'reconnecting') {
    return raw
  }

  const prev = streakByNodeId.get(nodeId) ?? {
    lastStable: defaultStableStatus(),
    reconnectPolls: 0,
  }
  const reconnectPolls = prev.reconnectPolls + 1
  if (reconnectPolls >= RECONNECT_DEBOUNCE_POLLS) {
    streakByNodeId.set(nodeId, { lastStable: 'reconnecting', reconnectPolls })
    return 'reconnecting'
  }
  streakByNodeId.set(nodeId, { ...prev, reconnectPolls })
  return prev.lastStable
}

export function resetNodeConnectionDisplay(nodeId?: number) {
  if (nodeId == null) {
    streakByNodeId.clear()
    return
  }
  streakByNodeId.delete(nodeId)
}

/**
 * While another node is in a lifecycle batch, ignore transient reconnecting flicker
 * from full list refreshes on unrelated agents that stayed online.
 */
export function mergeNodeListDuringLifecycleBatch<T extends Pick<ApiNode, 'id' | 'status' | 'routable'>>(
  next: T[],
  prev: T[],
  batchNodeIds: ReadonlySet<number>,
): T[] {
  if (batchNodeIds.size === 0) {
    return next
  }
  const prevById = new Map(prev.map((node) => [node.id, node]))
  return next.map((node) => {
    if (batchNodeIds.has(node.id)) {
      return node
    }
    const old = prevById.get(node.id)
    if (!old || old.status !== 'online' || node.status !== 'reconnecting') {
      return node
    }
    return { ...node, status: 'online' as const, routable: old.routable ?? node.routable }
  })
}

export function connectionStatusForLifecycle(node: Pick<ApiNode, 'id' | 'status'>): NodeStatus {
  return node.status
}
