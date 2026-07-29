// @vitest-environment jsdom

import { beforeEach, describe, expect, it, vi } from 'vitest'
import { defineComponent, h } from 'vue'
import { mount } from '@vue/test-utils'
import { previewNodeOperationsBatch, startNodeOperationsBatch } from '../lib/nodeApi'
import type { ApiNode } from '../types/node'
import { useNodeLifecycleOps } from './useNodeLifecycleOps'

vi.mock('../lib/nodeApi', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../lib/nodeApi')>()
  return {
    ...actual,
    previewNodeOperationsBatch: vi.fn(),
    startNodeOperationsBatch: vi.fn(),
  }
})

describe('useNodeLifecycleOps batch start', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    window.sessionStorage.clear()
  })

  it('does not report success when HTTP 202 contains per-node errors', async () => {
    const node = {
      id: 21,
      name: 'offline-proxy',
      role: 'proxy',
      status: 'offline',
    } as ApiNode
    vi.mocked(previewNodeOperationsBatch).mockResolvedValue({
      kind: 'remove',
      requested: 1,
      eligible: [{ node_id: node.id, name: node.name }],
      skipped_offline: [],
      skipped_workload: [],
      skipped_in_progress: [],
      skipped_not_upgradeable: [],
      skipped_proxy_bound: [],
      missing_node_ids: [],
      max_concurrent: 5,
    })
    vi.mocked(startNodeOperationsBatch).mockResolvedValue({
      kind: 'remove',
      requested: 1,
      eligible: [{ node_id: node.id, name: node.name }],
      skipped_offline: [],
      skipped_workload: [],
      skipped_in_progress: [],
      skipped_not_upgradeable: [],
      skipped_proxy_bound: [],
      missing_node_ids: [],
      max_concurrent: 5,
      started: [],
      queued: [],
      errors: [{
        node_id: node.id,
        code: 'node_offline',
        error: 'Node is offline. Strict Cleanup requires the Agent to be reachable.',
      }],
    })
    let lifecycle!: ReturnType<typeof useNodeLifecycleOps>
    const wrapper = mount(defineComponent({
      setup() {
        lifecycle = useNodeLifecycleOps({
          role: 'proxy',
          t: ((key: string) => key) as never,
        })
        return () => h('div')
      },
    }))

    try {
      const started = await lifecycle.runBatch('remove', [node], { skipConfirm: true })

      expect(started).toBe(false)
      expect(lifecycle.lastStartErrors.value).toEqual([
        expect.objectContaining({ code: 'node_offline', node_id: node.id }),
      ])
    } finally {
      wrapper.unmount()
    }
  })

  it('keeps preview-blocked nodes as batch errors when eligible nodes start', async () => {
    const startedNode = {
      id: 31,
      name: 'ready-proxy',
      role: 'proxy',
      status: 'online',
    } as ApiNode
    const blockedNode = {
      id: 32,
      name: 'busy-proxy',
      role: 'proxy',
      status: 'online',
    } as ApiNode
    vi.mocked(previewNodeOperationsBatch).mockResolvedValue({
      kind: 'remove',
      requested: 2,
      eligible: [{ node_id: startedNode.id, name: startedNode.name }],
      skipped_offline: [],
      skipped_workload: [{
        node_id: blockedNode.id,
        name: blockedNode.name,
        reason: 'node_workload_active',
      }],
      skipped_in_progress: [],
      skipped_not_upgradeable: [],
      skipped_proxy_bound: [],
      missing_node_ids: [],
      max_concurrent: 5,
    })
    vi.mocked(startNodeOperationsBatch).mockResolvedValue({
      kind: 'remove',
      requested: 1,
      eligible: [{ node_id: startedNode.id, name: startedNode.name }],
      skipped_offline: [],
      skipped_workload: [],
      skipped_in_progress: [],
      skipped_not_upgradeable: [],
      skipped_proxy_bound: [],
      missing_node_ids: [],
      max_concurrent: 5,
      started: [{
        operation_id: 'offline-remove:31',
        task_id: null,
        node_id: startedNode.id,
        kind: 'remove',
        state: 'completed',
        purged: true,
      }],
      queued: [],
      errors: [],
    })
    let lifecycle!: ReturnType<typeof useNodeLifecycleOps>
    const wrapper = mount(defineComponent({
      setup() {
        lifecycle = useNodeLifecycleOps({
          role: 'proxy',
          t: ((key: string) => key) as never,
        })
        return () => h('div')
      },
    }))

    try {
      const succeeded = await lifecycle.runBatch(
        'remove',
        [startedNode, blockedNode],
        { skipConfirm: true, force: true },
      )

      expect(succeeded).toBe(false)
      expect(lifecycle.lastStartErrors.value).toEqual([
        expect.objectContaining({
          code: 'node_workload_active',
          node_id: blockedNode.id,
        }),
      ])
      expect(lifecycle.completed.value).toEqual([
        expect.objectContaining({ nodeId: startedNode.id }),
      ])
    } finally {
      wrapper.unmount()
    }
  })
})
