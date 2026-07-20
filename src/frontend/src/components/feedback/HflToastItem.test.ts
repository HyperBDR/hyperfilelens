// @vitest-environment jsdom

import { mount } from '@vue/test-utils'
import { createI18n } from 'vue-i18n'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import HflToastItem from './HflToastItem.vue'
import { closeErrorDetails, errorDetailsState } from '../../lib/errors/details'
import { pushToast, resetToastStoreForTests, toastState } from '../../lib/toast/store'

const i18n = createI18n({
  legacy: false,
  locale: 'en',
  messages: {
    en: {
      common: { close: 'Close' },
      feedback: { toast: { copy: 'Copy', copied: 'Copied', viewDetails: 'View details', howToFix: 'How to fix' } },
    },
  },
})

describe('HflToastItem', () => {
  beforeEach(() => {
    vi.useFakeTimers()
    resetToastStoreForTests()
    closeErrorDetails()
  })

  afterEach(() => {
    resetToastStoreForTests()
    closeErrorDetails()
    vi.useRealTimers()
  })

  it('pauses on hover and closes from the close button', async () => {
    pushToast({ type: 'warning', title: 'Warning', message: 'Read this message' })
    const toast = toastState.items[0]!
    const wrapper = mount(HflToastItem, { props: { toast }, global: { plugins: [i18n] } })

    await wrapper.trigger('mouseenter')
    expect(toastState.items[0]?.paused).toBe(true)
    document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Tab', bubbles: true }))
    await wrapper.trigger('focusin')
    await wrapper.trigger('mouseleave')
    expect(toastState.items[0]?.paused).toBe(true)
    await wrapper.trigger('focusout')
    expect(toastState.items[0]?.paused).toBe(false)
    await wrapper.get('[aria-label="Close"]').trigger('click')
    expect(toastState.items).toHaveLength(0)
  })

  it('does not keep a toast paused after pointer focus leaves the toast', async () => {
    pushToast({ type: 'info', message: 'Clickable message' })
    const wrapper = mount(HflToastItem, {
      props: { toast: toastState.items[0]! },
      attachTo: document.body,
      global: { plugins: [i18n] },
    })

    await wrapper.trigger('mouseenter')
    wrapper.element.dispatchEvent(new Event('pointerdown', { bubbles: true }))
    await wrapper.trigger('focusin')
    await wrapper.trigger('mouseleave')
    expect(toastState.items[0]?.paused).toBe(false)
    wrapper.unmount()
  })

  it('uses centered compact styling only for a single message', () => {
    pushToast({ type: 'success', message: 'Policy updated.' })
    const compact = mount(HflToastItem, {
      props: { toast: toastState.items[0]! },
      global: { plugins: [i18n] },
    })
    expect(compact.classes()).toContain('hfl-toast--compact')
    compact.unmount()

    resetToastStoreForTests()
    pushToast({ type: 'error', title: 'Connection failed', message: 'Endpoint timed out' })
    const detailed = mount(HflToastItem, {
      props: { toast: toastState.items[0]! },
      global: { plugins: [i18n] },
    })
    expect(detailed.classes()).not.toContain('hfl-toast--compact')
  })

  it('opens details and removes the summary toast', async () => {
    pushToast({
      type: 'error',
      title: 'Connection failed',
      message: 'Endpoint timed out',
      details: {
        title: 'Connection failed',
        summary: 'Endpoint timed out',
        errorCode: 'NETWORK.TIMEOUT',
      },
    })
    const wrapper = mount(HflToastItem, {
      props: { toast: toastState.items[0]! },
      global: { plugins: [i18n] },
    })

    const detailsButton = wrapper.findAll('button').find((button) => button.text() === 'View details')
    expect(detailsButton).toBeTruthy()
    await detailsButton!.trigger('click')
    expect(toastState.items).toHaveLength(0)
    expect(errorDetailsState.current?.errorCode).toBe('NETWORK.TIMEOUT')
  })

  it('promotes actionable details as how-to-fix guidance', () => {
    pushToast({
      type: 'error',
      title: 'Connection failed',
      message: 'Endpoint timed out',
      details: {
        title: 'Connection failed',
        summary: 'Endpoint timed out',
        resolutions: ['Check the endpoint.'],
      },
    })
    const wrapper = mount(HflToastItem, {
      props: { toast: toastState.items[0]! },
      global: { plugins: [i18n] },
    })
    expect(wrapper.text()).toContain('How to fix')
    expect(wrapper.text()).not.toContain('View details')
  })
})
