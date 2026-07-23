// @vitest-environment jsdom

import { flushPromises, mount } from '@vue/test-utils'
import { createI18n } from 'vue-i18n'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import {
  preloadTurnstileScript,
  resetTurnstileScriptLoad,
} from '../lib/turnstileLoader'
import TurnstileWidget from './TurnstileWidget.vue'

vi.mock('../lib/turnstileLoader', () => ({
  preloadTurnstileScript: vi.fn(),
  resetTurnstileScriptLoad: vi.fn(),
  TURNSTILE_LOAD_TIMEOUT_MS: 1_000,
}))

const i18n = createI18n({
  legacy: false,
  locale: 'en',
  messages: {
    en: {
      login: { captchaLoading: 'Loading Cloudflare human verification...' },
    },
  },
})

type RenderOptions = Parameters<NonNullable<typeof window.turnstile>['render']>[1]

function mountWidget() {
  return mount(TurnstileWidget, {
    props: { siteKey: 'test-site-key', action: 'login' },
    global: { plugins: [i18n] },
  })
}

describe('TurnstileWidget lifecycle', () => {
  beforeEach(() => {
    vi.useFakeTimers()
    vi.mocked(preloadTurnstileScript).mockReset().mockResolvedValue(undefined)
    vi.mocked(resetTurnstileScriptLoad).mockReset()
    delete window.turnstile
  })

  afterEach(() => {
    vi.useRealTimers()
    delete window.turnstile
  })

  it('moves from loading to challenge, success, expiration, and reset', async () => {
    let renderOptions: RenderOptions | undefined
    const reset = vi.fn()
    const remove = vi.fn()
    window.turnstile = {
      ready: callback => callback(),
      render: (container, options) => {
        renderOptions = options
        container.append(document.createElement('iframe'))
        return 'widget-1'
      },
      reset,
      remove,
    }

    const wrapper = mountWidget()
    await flushPromises()
    expect(wrapper.find('.turnstile-widget__loading').exists()).toBe(true)

    await vi.advanceTimersByTimeAsync(100)
    expect(wrapper.find('.turnstile-widget__loading').exists()).toBe(false)
    expect(wrapper.find('iframe').exists()).toBe(true)

    renderOptions!.callback('verified-token')
    renderOptions!.callback('duplicate-token')
    expect(wrapper.emitted('success')).toEqual([['verified-token']])

    renderOptions!['expired-callback']?.()
    expect(wrapper.emitted('expire')).toHaveLength(1)

    wrapper.vm.reset()
    expect(reset).toHaveBeenCalledWith('widget-1')
    wrapper.unmount()
    expect(remove).toHaveBeenCalledWith('widget-1')
  })

  it('emits an error when Cloudflare fails before rendering a challenge', async () => {
    let renderOptions: RenderOptions | undefined
    window.turnstile = {
      ready: callback => callback(),
      render: (_container, options) => {
        renderOptions = options
        return 'widget-2'
      },
      reset: vi.fn(),
      remove: vi.fn(),
    }

    const wrapper = mountWidget()
    await flushPromises()
    renderOptions!['error-callback']?.()
    await wrapper.vm.$nextTick()

    expect(wrapper.emitted('error')).toHaveLength(1)
    expect(wrapper.find('.turnstile-widget__loading').exists()).toBe(false)
    wrapper.unmount()
  })

  it('retries a failed script load once before reporting load failure', async () => {
    vi.mocked(preloadTurnstileScript).mockRejectedValue(new Error('network unavailable'))

    const wrapper = mountWidget()
    await flushPromises()
    await vi.advanceTimersByTimeAsync(300)
    await flushPromises()

    expect(preloadTurnstileScript).toHaveBeenCalledTimes(2)
    expect(resetTurnstileScriptLoad).toHaveBeenCalledTimes(1)
    expect(wrapper.emitted('load-failed')).toHaveLength(1)
    expect(wrapper.find('.turnstile-widget__loading').exists()).toBe(false)
    wrapper.unmount()
  })
})
