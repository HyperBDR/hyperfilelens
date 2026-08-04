import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { describe, expect, it } from 'vitest'

function source(path: string) {
  return readFileSync(resolve(process.cwd(), path), 'utf8')
}

describe('Admin Console finalization contracts', () => {
  it('does not issue a gateway enrollment token until the operator clicks Generate', () => {
    const wizard = source('src/components/NodeLifecycleWizard.vue')
    const addPage = source('src/platform-ops/pages/engine/PlatformGatewayAdd.vue')

    expect(addPage).toContain('generate-on-demand')
    expect(addPage).toContain("<h1>{{ t('platformOps.engineGateway.addTitle') }}</h1>")
    expect(addPage).not.toContain("<h2>{{ t('platformOps.engineGateway.addTitle') }}</h2>")
    expect(addPage).not.toContain('enrollment-ttl-seconds')
    expect(addPage).not.toContain('gateway-token-ttl')
    expect(addPage).toContain('@enrollment-issued="onEnrollmentIssued"')
    expect(wizard).toContain("activeTab.value === 'install' && !props.generateOnDemand")
    expect(wizard).toContain('v-if="generateOnDemand && !installGenerated"')
    expect(wizard).toContain('@click="generateInstallCommand"')
  })

  it('keeps the Admin gateway table compact and uses Admin pagination', () => {
    const gateways = source('src/pages/insight/InsightDataGateways.vue')

    expect(gateways).toContain("'/platform-ops/engine/gateways/add'")
    expect(gateways).toContain('<PlatformOpsPagination')
    expect(gateways).toContain('v-if="!isPlatformEngine" label="OS"')
    expect(gateways).toContain('v-if="!isPlatformEngine" :label="t(\'protection.sourceResources.colCapacity\')"')
    expect(gateways).toContain('fixed="right"')
  })

  it('hides the outer Admin title on every AI Engine editor route', () => {
    const layout = source('src/platform-ops/layout/PlatformEngineLayout.vue')
    expect(layout).toContain("/\\/(?:add|edit)$/")
    expect(layout).toContain(':hide-page-title="hidePageTitle"')
  })

  it('keeps tenant list labels while using resource-specific Admin actions', () => {
    const models = source('src/pages/insight/InsightAiSettings.vue')
    expect(models).toContain("isPlatformEngine ? t('platformOps.engineActions.addModel') : t('insight.aiSettings.btnAdd')")
    expect(models).toContain("isPlatformEngine ? t('platformOps.engineActions.modelActions') : t('insight.aiSettings.btnMoreActions')")
  })

  it('presents deployment environment source aliases consistently', () => {
    const environment = source('src/platform-ops/pages/platform/settings/EnvironmentSettings.vue')

    expect(environment).toContain("source === 'deployment' || source === 'environment' || source === 'env'")
    expect(environment).toContain("return 'Deployment environment'")
  })

  it('requires the DISABLE keyword before saving an Admin Console lockout', () => {
    const identity = source('src/platform-ops/pages/platform/settings/IdentitySettings.vue')

    expect(identity).toContain('if (disablesPlatformOps.value)')
    expect(identity).toContain('disableConfirmOpen.value = true')
    expect(identity).toContain('confirm-keyword="DISABLE"')
    expect(identity).toContain("body.confirm_disable = 'DISABLE'")
  })
})
