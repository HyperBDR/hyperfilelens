import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { Building2, Users, CreditCard, Settings } from 'lucide-vue-next'
import type { MenuItem } from '../components/ModulePage.vue'

/**
 * Config management sidebar: organization management + system settings
 */
export function useNodeSideNav() {
  const { t } = useI18n()
  return computed<MenuItem[]>(() => [
    {
      label: t('assetsPage.side.groupGovernance'),
      children: [
        { label: t('settings.nav.organizationHub'), to: '/node/organization', icon: Building2 },
        { label: t('settings.nav.members'), to: '/node/members', icon: Users },
        { label: t('settings.nav.subscription'), to: '/node/subscription', icon: CreditCard },
      ],
    },
    {
      label: t('assetsPage.side.groupSystem'),
      children: [{ label: t('settings.nav.systemHub'), to: '/node/system', icon: Settings }],
    },
  ])
}
