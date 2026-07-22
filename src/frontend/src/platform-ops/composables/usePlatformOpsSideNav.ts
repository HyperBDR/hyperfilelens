import { computed, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import {
  Activity,
  AlertTriangle,
  BellRing,
  Bot,
  BookOpen,
  Building2,
  Cpu,
  FileText,
  History,
  KeyRound,
  LayoutDashboard,
  ListTodo,
  Mail,
  Package,
  Puzzle,
  Radio,
  ScrollText,
  Server,
  Settings,
  Users,
} from 'lucide-vue-next'
import type { MenuItem } from '../../components/ModulePage.vue'

export function usePlatformOpsSideNav() {
  const { t } = useI18n()

  return computed<MenuItem[]>(() => [
    {
      label: t('platformOps.nav.overview'),
      to: '/platform-ops/overview',
      icon: LayoutDashboard,
      pageTitle: t('platformOps.overview.title'),
    },
    {
      label: t('platformOps.nav.groupMonitoringDiagnostics'),
      children: [
        {
          label: t('platformOps.nav.monitoringMonitor'),
          to: '/platform-ops/monitoring/monitor',
          icon: Activity,
          pageTitle: t('platformOps.monitoring.monitorTitle'),
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
        {
          label: t('platformOps.nav.monitoringLogs'),
          to: '/platform-ops/monitoring/logs',
          icon: ScrollText,
          pageTitle: t('platformOps.monitoring.logsTitle'),
        },
      ],
    },
    {
      label: t('platformOps.nav.groupAlertCenter'),
      children: [
        {
          label: t('platformOps.nav.alertIncidents'),
          to: '/platform-ops/alert-center/incidents',
          icon: AlertTriangle,
          pageTitle: t('platformOps.monitoring.incidentsTitle'),
        },
        {
          label: t('platformOps.nav.alertPolicies'),
          to: '/platform-ops/alert-center/policies',
          icon: BellRing,
          pageTitle: t('platformOps.alertCenter.policiesTitle'),
        },
        {
          label: t('platformOps.nav.notificationChannels'),
          to: '/platform-ops/alert-center/notification-channels',
          icon: Radio,
          pageTitle: t('platformOps.alertCenter.channelsTitle'),
        },
        {
          label: t('platformOps.nav.notificationHistory'),
          to: '/platform-ops/alert-center/notification-history',
          icon: History,
          pageTitle: t('platformOps.monitoring.notificationHistoryTitle'),
        },
      ],
    },
    {
      label: t('platformOps.nav.groupIdentityAccess'),
      children: [
        {
          label: t('platformOps.nav.users'),
          to: '/platform-ops/users',
          icon: Users,
          pageTitle: t('platformOps.users.pageTitle'),
        },
        {
          label: t('platformOps.nav.orgs'),
          to: '/platform-ops/orgs',
          icon: Building2,
          pageTitle: t('platformOps.orgs.pageTitle'),
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
          label: t('platformOps.nav.engineUsage'),
          to: '/platform-ops/engine/usage',
          icon: Activity,
        },
        {
          label: t('platformOps.nav.engineGateways'),
          to: '/platform-ops/engine/gateways',
          icon: Server,
        },
        {
          label: t('platformOps.nav.engineConnections'),
          to: '/platform-ops/engine/data-connections',
          icon: Radio,
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
      label: t('platformOps.nav.groupPlatform'),
      children: [
        {
          label: t('platformOps.nav.platformIntegrations'),
          to: '/platform-ops/platform/integrations',
          icon: Radio,
          pageTitle: t('platformOps.integrations.title'),
        },
        {
          label: t('platformOps.nav.platformAuthentication'),
          to: '/platform-ops/platform/authentication',
          icon: KeyRound,
          pageTitle: t('platformOps.settings.identityTitle'),
        },
        {
          label: t('platformOps.nav.platformEmail'),
          to: '/platform-ops/platform/email',
          icon: Mail,
          pageTitle: t('platformOps.settings.emailTitle'),
        },
        {
          label: t('platformOps.nav.platformRuntime'),
          to: '/platform-ops/platform/runtime-environment',
          icon: Settings,
          pageTitle: t('platformOps.settings.environmentTitle'),
        },
        {
          label: t('platformOps.nav.platformAgentReleases'),
          to: '/platform-ops/platform/agent-releases',
          icon: Package,
          pageTitle: t('platformOps.platform.agentsTitle'),
        },
      ],
    },
    {
      label: t('platformOps.nav.groupAuditCenter'),
      children: [
        {
          label: t('platformOps.nav.auditLogs'),
          to: '/platform-ops/audit-center/audit-logs',
          icon: FileText,
          pageTitle: t('platformOps.audit.title'),
        },
      ],
    },
  ])
}

export function usePlatformOpsAccess() {
  const ready = ref(false)
  const emailSignupEnabled = ref(false)
  const tenantPublicUrl = ref('')

  async function load() {
    const { fetchDeployProfile } = await import('../../composables/useDeployProfile')
    const profile = await fetchDeployProfile()
    emailSignupEnabled.value = !!profile?.email_signup_enabled
    tenantPublicUrl.value = profile?.tenant_public_url || ''
    ready.value = true
    return profile
  }

  onMounted(() => {
    void load()
  })

  return {
    ready,
    emailSignupEnabled,
    tenantPublicUrl,
    load,
  }
}
