// @vitest-environment jsdom

import { defineComponent, nextTick } from 'vue'
import { flushPromises, mount } from '@vue/test-utils'
import { describe, expect, it, vi } from 'vitest'
import type { ComposerTranslation } from 'vue-i18n'
import type { SystemMonitorPayload } from '../../lib/monitorApi'
import type { DeploymentHostItem } from '../lib/platformOpsApi'
import { useDeploymentHostMonitor } from './useDeploymentHostMonitor'

const host: DeploymentHostItem = {
  id: 'host-1',
  hostname: 'host-1',
  name: 'host-1',
  ip_address: '127.0.0.1',
  platform: 'linux',
  python_version: '3.13',
  app_version: '1.0.0',
  status: 'online',
  last_seen_at: null,
}

const payload: SystemMonitorPayload = {
  host: {},
  range: {},
  current: {},
  series: [],
}

function deferred<T>() {
  let resolve!: (value: T) => void
  const promise = new Promise<T>((done) => {
    resolve = done
  })
  return { promise, resolve }
}

function mountMonitor(
  fetchMonitor: () => Promise<SystemMonitorPayload>,
  fetchHosts: () => Promise<DeploymentHostItem[]>,
) {
  return mount(defineComponent({
    setup() {
      const monitor = useDeploymentHostMonitor(
        ((key: string) => key) as ComposerTranslation,
        fetchMonitor,
        fetchHosts,
      )
      return {
        loading: monitor.loading,
        onManualRefresh: monitor.onManualRefresh,
      }
    },
    template: `
      <div>
        <span data-test="loading">{{ loading ? 'loading' : 'idle' }}</span>
        <button data-test="refresh" @click="onManualRefresh">refresh</button>
      </div>
    `,
  }))
}

describe('useDeploymentHostMonitor loading', () => {
  it('covers both host discovery and the initial metrics request', async () => {
    const hostsRequest = deferred<DeploymentHostItem[]>()
    const monitorRequest = deferred<SystemMonitorPayload>()
    const fetchHosts = vi.fn(() => hostsRequest.promise)
    const fetchMonitor = vi.fn(() => monitorRequest.promise)
    const wrapper = mountMonitor(fetchMonitor, fetchHosts)
    await nextTick()

    expect(wrapper.get('[data-test="loading"]').text()).toBe('loading')
    hostsRequest.resolve([host])
    await flushPromises()
    expect(fetchMonitor).toHaveBeenCalledOnce()
    expect(wrapper.get('[data-test="loading"]').text()).toBe('loading')

    monitorRequest.resolve(payload)
    await flushPromises()
    expect(wrapper.get('[data-test="loading"]').text()).toBe('idle')
    wrapper.unmount()
  })

  it('reloads hosts and keeps loading active during a manual refresh', async () => {
    const fetchHosts = vi.fn().mockResolvedValue([host])
    const fetchMonitor = vi.fn().mockResolvedValue(payload)
    const wrapper = mountMonitor(fetchMonitor, fetchHosts)
    await flushPromises()
    fetchHosts.mockClear()
    fetchMonitor.mockClear()

    const hostsRequest = deferred<DeploymentHostItem[]>()
    const monitorRequest = deferred<SystemMonitorPayload>()
    fetchHosts.mockReturnValueOnce(hostsRequest.promise)
    fetchMonitor.mockReturnValueOnce(monitorRequest.promise)
    await wrapper.get('[data-test="refresh"]').trigger('click')

    expect(fetchHosts).toHaveBeenCalledOnce()
    expect(wrapper.get('[data-test="loading"]').text()).toBe('loading')
    hostsRequest.resolve([host])
    await flushPromises()
    expect(fetchMonitor).toHaveBeenCalledOnce()
    expect(wrapper.get('[data-test="loading"]').text()).toBe('loading')

    monitorRequest.resolve(payload)
    await flushPromises()
    expect(wrapper.get('[data-test="loading"]').text()).toBe('idle')
    wrapper.unmount()
  })
})
