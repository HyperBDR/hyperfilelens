import { computed, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import {
  Bot,
  BookOpen,
  Building2,
  Cpu,
  KeyRound,
  ListTodo,
  Mail,
  Monitor,
  Package,
  Puzzle,
  Server,
  Shield,
  Users,
} from 'lucide-vue-next'
import type { MenuItem } from '../../components/ModulePage.vue'

export function usePlatformOpsSideNav() {
  const { t } = useI18n()

  return computed<MenuItem[]>(() => [
    {
      label: t('platformOps.nav.groupMonitoringDiagnostics'),
      children: [
        {
          label: t('platformOps.nav.monitoringHost'),
          to: '/platform-ops/monitoring/host',
          icon: Monitor,
          pageTitle: t('platformOps.monitoring.hostTitle'),
        },
        {
          label: t('platformOps.nav.monitoringNodes'),
          to: '/platform-ops/monitoring/nodes',
          icon: Server,
          pageTitle: t('platformOps.monitoring.nodesTitle'),
        },
        {
          label: t('platformOps.nav.monitoringTasks'),
          to: '/platform-ops/monitoring/tasks',
          icon: ListTodo,
          pageTitle: t('platformOps.monitoring.tasksTitle'),
        },
      ],
    },
    {
      label: t('platformOps.nav.groupIdentityAccess'),
      children: [
        {
          label: t('platformOps.nav.orgs'),
          to: '/platform-ops/orgs',
          icon: Building2,
          pageTitle: t('platformOps.orgs.pageTitle'),
        },
        {
          label: t('platformOps.nav.users'),
          to: '/platform-ops/users',
          icon: Users,
          pageTitle: t('platformOps.users.pageTitle'),
        },
      ],
    },
    {
      label: t('platformOps.nav.groupEngine'),
      children: [
        {
          label: t('platformOps.nav.engineModels'),
          to: '/platform-ops/engine/ai-settings',
          icon: Cpu,
        },
        {
          label: t('platformOps.nav.engineGateways'),
          to: '/platform-ops/engine/gateways',
          icon: Server,
        },
        {
          label: t('platformOps.nav.engineKnowledge'),
          to: '/platform-ops/engine/knowledge-base',
          icon: BookOpen,
        },
        {
          label: t('platformOps.nav.engineAssistants'),
          to: '/platform-ops/engine/assistants',
          icon: Bot,
        },
        {
          label: t('platformOps.nav.engineSkills'),
          to: '/platform-ops/engine/skills',
          icon: Puzzle,
        },
        {
          label: t('platformOps.nav.engineMcp'),
          to: '/platform-ops/engine/mcp-servers',
          icon: Server,
        },
      ],
    },
    {
      label: t('platformOps.nav.groupSystemSettings'),
      children: [
        {
          label: t('platformOps.nav.platformEmail'),
          to: '/platform-ops/platform/settings/email',
          icon: Mail,
          pageTitle: t('platformOps.settings.emailTitle'),
        },
        {
          label: t('platformOps.nav.platformTurnstile'),
          to: '/platform-ops/platform/settings/turnstile',
          icon: Shield,
          pageTitle: t('platformOps.settings.turnstileTitle'),
        },
        {
          label: t('platformOps.nav.platformGoogleOAuth'),
          to: '/platform-ops/platform/settings/google-oauth',
          icon: KeyRound,
          pageTitle: t('platformOps.settings.googleOAuthTitle'),
        },
      ],
    },
    {
      label: t('platformOps.nav.groupResourcesReleases'),
      children: [
        {
          label: t('platformOps.nav.platformAgentReleases'),
          to: '/platform-ops/platform/agent-releases',
          icon: Package,
          pageTitle: t('platformOps.platform.agentsTitle'),
        },
      ],
    },
  ])
}

export function usePlatformOpsAccess() {
  const ready = ref(false)
  const registrationEnabled = ref(false)
  const tenantPublicUrl = ref('')

  async function load() {
    const { fetchDeployProfile } = await import('../../composables/useDeployProfile')
    const profile = await fetchDeployProfile()
    registrationEnabled.value = !!profile?.registration_enabled
    tenantPublicUrl.value = profile?.tenant_public_url || ''
    ready.value = true
    return profile
  }

  onMounted(() => {
    void load()
  })

  return {
    ready,
    registrationEnabled,
    tenantPublicUrl,
    load,
  }
}
