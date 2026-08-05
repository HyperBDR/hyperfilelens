/** Connection presentation is sourced exclusively from Availability. */

import type { Availability, ApiNode } from '../types/node'

export function debouncedNodeStatus(node: Pick<ApiNode, 'availability'>): Availability {
  return node.availability === 'online' ? 'online' : 'offline'
}

export function resetNodeConnectionDisplay(nodeId?: number) {
  void nodeId
}

/**
 * While another node is in a lifecycle batch, ignore transient reconnecting flicker
 * from full list refreshes on unrelated agents that stayed online.
 */
export function mergeNodeListDuringLifecycleBatch<T extends Pick<ApiNode, 'id' | 'availability' | 'routable'>>(
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
    return old?.availability === 'online' && node.availability === 'offline'
      ? { ...node, availability: old.availability, routable: old.routable ?? node.routable }
      : node
  })
}

export function connectionStatusForLifecycle(node: Pick<ApiNode, 'availability'>): Availability {
  return debouncedNodeStatus(node)
}
