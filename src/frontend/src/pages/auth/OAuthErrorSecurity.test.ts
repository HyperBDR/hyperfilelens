// @vitest-environment jsdom

import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { flushPromises, mount } from '@vue/test-utils'
import { createI18n } from 'vue-i18n'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { en } from '../../locales/en'
import OAuthError from './OAuthError.vue'

const mocks = vi.hoisted(() => ({
  api: vi.fn(),
  route: {
    path: '/auth/oauth/error',
    hash: '',
    query: {} as Record<string, string>,
  },
  routerPush: vi.fn(),
  routerReplace: vi.fn().mockResolvedValue(undefined),
}))

vi.mock('../../lib/api', () => ({ api: mocks.api }))

vi.mock('vue-router', () => ({
  useRoute: () => mocks.route,
  useRouter: () => ({
    push: mocks.routerPush,
    replace: mocks.routerReplace,
  }),
}))

async function mountOAuthError() {
  const i18n = createI18n({
    legacy: false,
    locale: 'en',
    messages: { en },
  })
  const wrapper = mount(OAuthError, {
    global: {
      plugins: [i18n],
    },
  })
  await flushPromises()
  return wrapper
}

describe('OAuth error event verification', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mocks.route.path = '/auth/oauth/error'
    mocks.route.hash = ''
    mocks.route.query = {}
    mocks.routerReplace.mockResolvedValue(undefined)
  })

  it('ignores and removes a forged legacy reason', async () => {
    mocks.route.query = { reason: 'account_disabled' }

    const wrapper = await mountOAuthError()

    expect(mocks.api).not.toHaveBeenCalled()
    expect(mocks.routerReplace).toHaveBeenCalledWith({
      path: '/auth/oauth/error',
      query: {},
      hash: '',
    })
    expect(wrapper.get('p').text()).toBe(
      'Google sign-in failed. Try again or select your work Google account.',
    )
  })

  it('shows a verified backend event and removes its ID', async () => {
    mocks.route.query = { event_id: 'verified-event' }
    mocks.api.mockResolvedValue({
      code: '0000',
      data: {
        verified: true,
        reason: 'account_disabled',
      },
    })

    const wrapper = await mountOAuthError()

    expect(mocks.api).toHaveBeenCalledWith(
      '/api/v1/auth/google/error-events/consume',
      {
        method: 'POST',
        body: JSON.stringify({ event_id: 'verified-event' }),
      },
    )
    expect(mocks.routerReplace).toHaveBeenCalledWith({
      path: '/auth/oauth/error',
      query: {},
      hash: '',
    })
    expect(wrapper.get('p').text()).toBe('This account is disabled.')
  })

  it('shows only the generic message for unknown or replayed events', async () => {
    mocks.route.query = { event_id: 'replayed-event' }
    mocks.api.mockResolvedValue({
      code: '0000',
      data: {
        verified: false,
        reason: 'account_disabled',
      },
    })

    const wrapper = await mountOAuthError()

    expect(wrapper.get('p').text()).toBe(
      'Google sign-in failed. Try again or select your work Google account.',
    )
  })

  it('still consumes a verified event when URL cleanup fails', async () => {
    mocks.route.query = { event_id: 'verified-event' }
    mocks.routerReplace.mockRejectedValue(new Error('navigation failed'))
    mocks.api.mockResolvedValue({
      code: '0000',
      data: {
        verified: true,
        reason: 'state_lost',
      },
    })

    const wrapper = await mountOAuthError()

    expect(mocks.api).toHaveBeenCalledOnce()
    expect(wrapper.get('p').text()).toBe(
      'Your sign-in session expired during the Google redirect. Please try again.',
    )
  })

  it('keeps the heading readable on the dark error page', () => {
    const source = readFileSync(
      resolve(process.cwd(), 'src/pages/auth/OAuthError.vue'),
      'utf8',
    )

    expect(source).toMatch(
      /\.oauth-error\s*{[^}]*background:\s*#08090c;[^}]*color:\s*#fff;/s,
    )
    expect(source).toMatch(
      /\.oauth-error-card h1\s*{[^}]*color:\s*inherit;/s,
    )
  })
})
