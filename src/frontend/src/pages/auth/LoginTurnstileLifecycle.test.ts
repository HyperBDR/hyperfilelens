// @vitest-environment jsdom

import { defineComponent, h, ref } from 'vue'
import { flushPromises, mount } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import { createI18n } from 'vue-i18n'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { en } from '../../locales/en'
import { storeSessionNotice } from '../../lib/sessionNotice'
import Login from './Login.vue'

const mocks = vi.hoisted(() => ({
  api: vi.fn(),
  blockTurnstile: vi.fn(),
  buildTurnstilePayload: vi.fn(),
  fetchCurrentUser: vi.fn(),
  fetchDeployProfile: vi.fn(),
  loadTurnstileConfig: vi.fn(),
  resetWidget: vi.fn(),
  routeQuery: {} as Record<string, string>,
  routerPush: vi.fn(),
  setStoredOrgKey: vi.fn(),
  setUser: vi.fn(),
}))

vi.mock('../../lib/api', () => ({ api: mocks.api }))

vi.mock('../../composables/useAuth', () => ({
  fetchCurrentUser: mocks.fetchCurrentUser,
  setStoredOrgKey: mocks.setStoredOrgKey,
  useAuth: () => ({ setUser: mocks.setUser }),
}))

vi.mock('../../composables/useLocaleSwitch', () => ({
  useLocaleSwitch: () => ({
    canSwitchLocale: ref(false),
    nextLocaleCode: ref('en'),
    nextLocaleLabel: ref('English'),
    toggleLocale: vi.fn(),
  }),
}))

vi.mock('../../composables/useTurnstileConfig', () => ({
  useTurnstileConfig: () => ({
    turnstileSiteKey: ref('test-site-key'),
    isTurnstilePending: ref(false),
    isTurnstileReady: ref(true),
    isTurnstileBlocked: ref(false),
    authTurnstileMountGeneration: ref(0),
    loadTurnstileConfig: mocks.loadTurnstileConfig,
    buildTurnstilePayload: mocks.buildTurnstilePayload,
    blockTurnstile: mocks.blockTurnstile,
  }),
}))

vi.mock('../../composables/useDeployProfile', () => ({
  fetchDeployProfile: mocks.fetchDeployProfile,
  resolvePostLoginPath: vi.fn().mockResolvedValue('/'),
}))

vi.mock('../../lib/appConfig', () => ({
  appConfig: { showEula: false },
}))

vi.mock('vue-router', () => ({
  useRoute: () => ({ query: mocks.routeQuery }),
  useRouter: () => ({ push: mocks.routerPush }),
}))

const AuthTurnstileFieldStub = defineComponent({
  name: 'AuthTurnstileField',
  props: {
    errorMessage: { type: String, default: '' },
  },
  emits: ['retry', 'success', 'expire', 'invalidate', 'error', 'load-failed'],
  setup(props, { expose }) {
    expose({ reset: mocks.resetWidget })
    return () => h('div', {
      class: 'turnstile-field-stub',
      role: props.errorMessage ? 'alert' : undefined,
    }, props.errorMessage)
  },
})

const successfulLoginResponse = {
  code: '0000',
  data: {
    user: { id: 1, email: 'person@example.com', username: 'person' },
    available_orgs: [],
  },
}

function installDefaultApiMock() {
  mocks.api.mockImplementation(async (path: string) => {
    if (path === '/api/v1/auth/google/config') {
      return { code: '0000', data: { enabled: false } }
    }
    if (path === '/api/v1/auth/email-login') {
      return successfulLoginResponse
    }
    throw new Error(`Unexpected API path: ${path}`)
  })
}

async function mountLogin(viewportWidth: number) {
  Object.defineProperty(window, 'innerWidth', {
    configurable: true,
    value: viewportWidth,
  })
  window.dispatchEvent(new Event('resize'))

  const i18n = createI18n({
    legacy: false,
    locale: 'en',
    messages: { en },
    missingWarn: false,
    fallbackWarn: false,
  })
  const wrapper = mount(Login, {
    global: {
      plugins: [i18n, ElementPlus],
      stubs: {
        AuthTurnstileField: AuthTurnstileFieldStub,
        ResetPasswordCard: true,
        Globe: true,
        Mail: true,
        Lock: true,
        Eye: true,
        EyeOff: true,
      },
    },
  })
  await flushPromises()
  return wrapper
}

async function fillCredentials(wrapper: Awaited<ReturnType<typeof mountLogin>>) {
  const inputs = wrapper.findAll('input')
  await inputs[0].setValue('person@example.com')
  await inputs[1].setValue('ValidPass123')
  return {
    email: inputs[0].element as HTMLInputElement,
    password: inputs[1].element as HTMLInputElement,
  }
}

function emailLoginCalls() {
  return mocks.api.mock.calls.filter(([path]) => path === '/api/v1/auth/email-login')
}

function submittedBody(call: unknown[]) {
  const init = call[1] as RequestInit
  return JSON.parse(String(init.body)) as Record<string, string>
}

describe('Login Turnstile lifecycle', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    window.sessionStorage.clear()
    for (const key of Object.keys(mocks.routeQuery)) {
      delete mocks.routeQuery[key]
    }
    mocks.fetchDeployProfile.mockResolvedValue({
      email_signup_enabled: false,
      password_reset_available: false,
    })
    mocks.loadTurnstileConfig.mockResolvedValue(undefined)
    mocks.buildTurnstilePayload.mockImplementation((token: string) => (
      token ? { turnstile_token: token } : {}
    ))
    installDefaultApiMock()
  })

  it('ignores a forged session reason from the public URL', async () => {
    mocks.routeQuery.reason = 'TOKEN_REUSED'
    mocks.routeQuery.redirect = '/ops/alerts/incidents'

    const wrapper = await mountLogin(1440)

    expect(wrapper.find('.session-alert').exists()).toBe(false)
    wrapper.unmount()
  })

  it('shows a backend-produced session notice only once', async () => {
    expect(storeSessionNotice('TOKEN_REUSED')).toBe(true)

    const firstMount = await mountLogin(1440)
    expect(firstMount.get('.session-alert').text()).toContain(
      'Unusual sign-in activity. Sign in again.',
    )
    firstMount.unmount()

    const replayMount = await mountLogin(1440)
    expect(replayMount.find('.session-alert').exists()).toBe(false)
    replayMount.unmount()
  })

  it.each([
    ['mobile', 390],
    ['tablet', 820],
    ['desktop', 1440],
  ])('recovers from invalidation and repeated expiration on %s', async (_name, width) => {
    const wrapper = await mountLogin(width)
    const credentials = await fillCredentials(wrapper)
    const turnstile = wrapper.getComponent(AuthTurnstileFieldStub)
    const submit = wrapper.get('button.submit-btn')

    expect(submit.attributes('disabled')).toBeDefined()

    turnstile.vm.$emit('success', 'initial-token')
    await wrapper.vm.$nextTick()
    expect(submit.attributes('disabled')).toBeUndefined()

    turnstile.vm.$emit('invalidate')
    await wrapper.vm.$nextTick()
    expect(submit.attributes('disabled')).toBeDefined()
    expect(turnstile.props('errorMessage')).toBe('')
    expect(credentials.email.value).toBe('person@example.com')
    expect(credentials.password.value).toBe('ValidPass123')

    turnstile.vm.$emit('success', 'language-refresh-token')
    await wrapper.vm.$nextTick()
    turnstile.vm.$emit('expire')
    await wrapper.vm.$nextTick()
    expect(submit.attributes('disabled')).toBeDefined()
    expect(turnstile.props('errorMessage')).toBe(
      'Human verification expired. Please complete the new challenge.',
    )

    turnstile.vm.$emit('success', 'replacement-token')
    await wrapper.vm.$nextTick()
    turnstile.vm.$emit('expire')
    await wrapper.vm.$nextTick()
    turnstile.vm.$emit('success', 'final-token')
    await wrapper.vm.$nextTick()
    expect(submit.attributes('disabled')).toBeUndefined()

    await submit.trigger('click')
    await flushPromises()

    expect(emailLoginCalls()).toHaveLength(1)
    expect(submittedBody(emailLoginCalls()[0])).toMatchObject({
      email: 'person@example.com',
      password: 'ValidPass123',
      turnstile_token: 'final-token',
    })
    expect(credentials.email.value).toBe('person@example.com')
    expect(credentials.password.value).toBe('ValidPass123')
    wrapper.unmount()
  })

  it('accepts a new token after the backend rejects an expired token', async () => {
    let loginAttempt = 0
    mocks.api.mockImplementation(async (path: string) => {
      if (path === '/api/v1/auth/google/config') {
        return { code: '0000', data: { enabled: false } }
      }
      if (path === '/api/v1/auth/email-login') {
        loginAttempt += 1
        if (loginAttempt === 1) {
          throw {
            status: 400,
            message: 'Invalid or expired human verification',
            fields: {
              turnstile_token: ['Invalid or expired human verification'],
            },
          }
        }
        return successfulLoginResponse
      }
      throw new Error(`Unexpected API path: ${path}`)
    })

    const wrapper = await mountLogin(1440)
    await fillCredentials(wrapper)
    const turnstile = wrapper.getComponent(AuthTurnstileFieldStub)
    const submit = wrapper.get('button.submit-btn')

    turnstile.vm.$emit('success', 'rejected-token')
    await wrapper.vm.$nextTick()
    await submit.trigger('click')
    await flushPromises()

    expect(mocks.resetWidget).toHaveBeenCalledTimes(1)
    expect(submit.attributes('disabled')).toBeDefined()
    expect(turnstile.props('errorMessage')).toBe('Human verification failed or expired')

    turnstile.vm.$emit('success', 'accepted-token')
    await wrapper.vm.$nextTick()
    expect(submit.attributes('disabled')).toBeUndefined()

    await submit.trigger('click')
    await flushPromises()

    expect(emailLoginCalls()).toHaveLength(2)
    expect(submittedBody(emailLoginCalls()[1]).turnstile_token).toBe('accepted-token')
    wrapper.unmount()
  })

  it('accepts corrected credentials after a password error resets Turnstile', async () => {
    let loginAttempt = 0
    mocks.api.mockImplementation(async (path: string) => {
      if (path === '/api/v1/auth/google/config') {
        return { code: '0000', data: { enabled: false } }
      }
      if (path === '/api/v1/auth/email-login') {
        loginAttempt += 1
        if (loginAttempt === 1) {
          return {
            code: '1001',
            data: {},
            error: {
              fields: {
                password: ['Incorrect password'],
              },
            },
          }
        }
        return successfulLoginResponse
      }
      throw new Error(`Unexpected API path: ${path}`)
    })

    const wrapper = await mountLogin(1440)
    const credentials = await fillCredentials(wrapper)
    const turnstile = wrapper.getComponent(AuthTurnstileFieldStub)
    const submit = wrapper.get('button.submit-btn')

    turnstile.vm.$emit('success', 'initial-token')
    await wrapper.vm.$nextTick()
    await submit.trigger('click')
    await flushPromises()

    expect(mocks.resetWidget).toHaveBeenCalledTimes(1)
    expect(submit.attributes('disabled')).toBeDefined()
    expect(wrapper.get('.input-wrapper.has-error .error-msg').text()).toBe('Incorrect password')

    await wrapper.findAll('input')[1].setValue('CorrectPass123')
    turnstile.vm.$emit('success', 'replacement-token')
    await wrapper.vm.$nextTick()

    expect(submit.attributes('disabled')).toBeUndefined()
    await submit.trigger('click')
    await flushPromises()

    expect(emailLoginCalls()).toHaveLength(2)
    expect(submittedBody(emailLoginCalls()[0])).toMatchObject({
      password: 'ValidPass123',
      turnstile_token: 'initial-token',
    })
    expect(submittedBody(emailLoginCalls()[1])).toMatchObject({
      password: 'CorrectPass123',
      turnstile_token: 'replacement-token',
    })
    expect(credentials.password.value).toBe('CorrectPass123')
    wrapper.unmount()
  })
})
