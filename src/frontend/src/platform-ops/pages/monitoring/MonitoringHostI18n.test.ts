import { createI18n } from 'vue-i18n'
import { describe, expect, it } from 'vitest'
import { en } from '../../../locales/en'

describe('MonitoringHost service health translations', () => {
  it('resolves the unavailable state from the monitoring namespace', () => {
    const i18n = createI18n({
      legacy: false,
      locale: 'en',
      messages: { en },
      missingWarn: false,
      fallbackWarn: false,
    })

    expect(i18n.global.t('platformOps.monitoring.serviceHealthUnavailable')).toBe(
      'Service Health Unavailable',
    )
    expect(i18n.global.t('platformOps.monitoring.serviceHealthUnavailableHint')).toBe(
      'Refresh to retry the platform service health check.',
    )
  })
})
