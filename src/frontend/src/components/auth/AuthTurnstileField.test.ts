// @vitest-environment jsdom

import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { shallowMount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'

import AuthTurnstileField from './AuthTurnstileField.vue'

const baseProps = {
  pending: false,
  ready: false,
  blocked: false,
  siteKey: 'test-site-key',
  action: 'login',
  loadingMessage: 'Loading Cloudflare human verification...',
  blockedMessage: 'Cloudflare verification unavailable.',
  retryLabel: 'Retry',
}

function mountField(overrides: Partial<typeof baseProps> & { errorMessage?: string } = {}) {
  return shallowMount(AuthTurnstileField, {
    props: { ...baseProps, ...overrides },
    global: {
      stubs: {
        KeyRound: true,
        TurnstileWidget: true,
      },
    },
  })
}

describe('AuthTurnstileField display states', () => {
  it('renders the configuration loading state without mounting the widget', () => {
    const wrapper = mountField({ pending: true })

    expect(wrapper.find('.auth-turnstile-field__loading').exists()).toBe(true)
    expect(wrapper.find('.auth-turnstile-field__widget').exists()).toBe(false)
    expect(wrapper.text()).toContain(baseProps.loadingMessage)
  })

  it('keeps verification errors visible below a ready Cloudflare widget', () => {
    const wrapper = mountField({ ready: true, errorMessage: 'Human verification failed or expired' })

    expect(wrapper.find('.auth-turnstile-field__widget').exists()).toBe(true)
    expect(wrapper.find('.auth-turnstile-field__viewport').exists()).toBe(true)
    expect(wrapper.get('.auth-turnstile-field__error').text()).toBe('Human verification failed or expired')
  })

  it('shows an unavailable message only once and exposes retry', async () => {
    const wrapper = mountField({
      blocked: true,
      errorMessage: baseProps.blockedMessage,
    })

    expect(wrapper.find('.auth-turnstile-field__blocked').exists()).toBe(true)
    expect(wrapper.find('.auth-turnstile-field__error').exists()).toBe(false)
    expect(wrapper.text().match(/Cloudflare verification unavailable\./g)).toHaveLength(1)

    await wrapper.get('.auth-turnstile-field__retry').trigger('click')
    expect(wrapper.emitted('retry')).toHaveLength(1)
  })

  it('assigns exactly one frame owner to every visual state', () => {
    const fieldSource = readFileSync(
      resolve(process.cwd(), 'src/components/auth/AuthTurnstileField.vue'),
      'utf8',
    )
    const widgetSource = readFileSync(
      resolve(process.cwd(), 'src/components/TurnstileWidget.vue'),
      'utf8',
    )

    expect(fieldSource).toMatch(
      /\.auth-turnstile-field__loading,\s*\.auth-turnstile-field__blocked\s*{[^}]*background:\s*#313131;[^}]*border:\s*1px solid #3a3b40;[^}]*border-radius:[^}]*overflow:\s*hidden;/s,
    )
    expect(fieldSource).toMatch(
      /\.auth-turnstile-field__widget\s*{[^}]*background:\s*transparent;[^}]*border:\s*0;[^}]*border-radius:\s*0;[^}]*overflow:\s*visible;/s,
    )
    expect(fieldSource).toMatch(
      /\.auth-turnstile-field__viewport\s*{[^}]*border:\s*1px solid #3a3b40;[^}]*border-radius:[^}]*overflow:\s*hidden;/s,
    )
    expect(fieldSource).toMatch(
      /\.auth-turnstile-field__viewport :deep\(\.turnstile-widget\)\s*{[^}]*width:\s*calc\(100% \+ 2px\);[^}]*margin:\s*-1px;/s,
    )
    expect(fieldSource).toMatch(
      /\.auth-turnstile-field__viewport :deep\(\.turnstile-widget__loading\)\s*{[^}]*border:\s*0;[^}]*border-radius:\s*0;/s,
    )
    expect(fieldSource).toMatch(
      /\.auth-turnstile-field__control\s*{[^}]*min-height:\s*65px;/s,
    )
    expect(fieldSource).toMatch(
      /\.auth-turnstile-field__spinner\s*{[^}]*width:\s*16px;[^}]*height:\s*16px;/s,
    )
    expect(widgetSource).toMatch(
      /\.turnstile-widget__loading\s*{[^}]*gap:\s*10px;[^}]*background:\s*#313131;[^}]*border:\s*1px solid #3A3B40;[^}]*border-radius:/s,
    )
  })
})
