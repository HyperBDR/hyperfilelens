<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { I18nT, useI18n } from 'vue-i18n'
import { Copy, Check, TriangleAlert, RefreshCw, ChevronDown, Info, Cpu, MemoryStick, HardDrive } from 'lucide-vue-next'
import AgentPlatformBrandIcon from './agent-deploy/AgentPlatformBrandIcon.vue'
import UbuntuBrandIcon from './agent-deploy/UbuntuBrandIcon.vue'
import {
  buildLocalServiceCommand,
  buildLocalUninstallCommand,
  buildLocalUpgradeCommand,
  defaultPackagePath,
  installPathsSummary,
  isLinuxOnlyRole,
  roleDeployNotes,
  roleSupportedOnOs,
  type NodeLifecycleTab,
} from '../lib/nodeInstallCommands'
import {
  fetchAgentRelease,
  issueEnrollmentInstall,
  issueGatewayEnrollmentInstall,
  issuePlatformGatewayEnrollmentInstall,
  type EnrollmentOs,
} from '../lib/nodeApi'
import { apiErrorMessage } from '../lib/api'
import type { NodeRole } from '../types/node'

const props = withDefaults(
  defineProps<{
    orgKey: string
    role: NodeRole
    os: EnrollmentOs
    roleLocked?: boolean
    showRolePicker?: boolean
    gatewayScope?: 'user' | 'platform'
    initialTab?: NodeLifecycleTab
    /** Hide upgrade/uninstall/service tabs (install-only embed). */
    installOnly?: boolean
  }>(),
  {
    roleLocked: false,
    showRolePicker: false,
    gatewayScope: 'user',
    initialTab: 'install',
    installOnly: false,
  },
)

const emit = defineEmits<{
  'update:os': [EnrollmentOs]
  'update:role': [NodeRole]
  copy: [string]
}>()

const { t } = useI18n()

const activeTab = ref<NodeLifecycleTab>(props.initialTab)
const installCommand = ref('')
const upgradeCommand = ref('')
const uninstallCommand = ref('')
const serviceCommand = ref('')
const loading = ref(false)
const releaseVersion = ref('')
const copied = ref(false)
const purgeAll = ref(true)
const serviceAction = ref<'status' | 'start' | 'stop' | 'restart'>('status')
const supportOpen = ref(false)

const LINUX_DISTROS = {
  deb: ['Ubuntu', 'Debian'],
  rpm: ['RHEL', 'CentOS Stream', 'Rocky Linux', 'AlmaLinux', 'Fedora', 'openSUSE Leap'],
  cloud: ['Amazon Linux', 'Oracle Linux', 'Arch Linux'],
} as const

const visibleTabs = computed((): NodeLifecycleTab[] =>
  props.installOnly ? ['install'] : ['install', 'upgrade', 'uninstall', 'service'],
)

const isUbuntuHostDeploy = computed(
  () => props.installOnly && (props.role === 'proxy' || props.role === 'gateway'),
)

const proxyReqCards = computed(() => [
  {
    key: 'os',
    kind: 'ubuntu' as const,
    title: t('nodesDeploy.proxyDeployUbuntuTitle'),
    sub: t('nodesDeploy.proxyDeployUbuntuMeta'),
  },
  {
    key: 'cpu',
    kind: 'icon' as const,
    icon: Cpu,
    title: t('nodesDeploy.proxyReqCpu'),
    sub: t('nodesDeploy.proxyReqCpuSub'),
  },
  {
    key: 'mem',
    kind: 'icon' as const,
    icon: MemoryStick,
    title: t('nodesDeploy.proxyReqMem'),
    sub: t('nodesDeploy.proxyReqMemSub'),
  },
  {
    key: 'disk',
    kind: 'icon' as const,
    icon: HardDrive,
    title: t('nodesDeploy.proxyReqDisk'),
    sub: t('nodesDeploy.proxyReqDiskSub'),
  },
])

const osDisabled = computed(() => ({
  windows: isLinuxOnlyRole(props.role),
  macos: isLinuxOnlyRole(props.role),
}))

const roleDisabled = computed(() => ({
  proxy: props.os !== 'linux',
  gateway: props.os !== 'linux',
}))

const linuxOnlyRoleHint = computed(() =>
  isLinuxOnlyRole(props.role) ? t('nodeLifecycle.linuxOnlyRoleHint') : '',
)

let generation = 0
let copiedTimer: ReturnType<typeof setTimeout> | undefined

const roleOptions = computed(() => [
  { value: 'agent' as NodeRole, title: t('nodesDeploy.roleAgentTitle'), desc: t('nodesDeploy.roleAgentDesc') },
  { value: 'proxy' as NodeRole, title: t('nodesDeploy.roleProxyTitle'), desc: t('nodesDeploy.roleProxyDesc') },
  { value: 'gateway' as NodeRole, title: t('nodesDeploy.roleGatewayTitle'), desc: t('nodesDeploy.roleGatewayDesc') },
])

const roleLabel = computed(() => {
  if (props.role === 'proxy') return t('nodesPage.roleProxy')
  if (props.role === 'gateway') return t('nodesPage.roleGateway')
  return t('nodesPage.roleAgent')
})

const paths = computed(() => installPathsSummary(props.os))

const displayCommand = computed(() => {
  switch (activeTab.value) {
    case 'upgrade':
      return upgradeCommand.value || t('nodeLifecycle.upgradeLoading')
    case 'uninstall':
      return uninstallCommand.value
    case 'service':
      return serviceCommand.value
    default:
      return installCommand.value || t('nodesDeploy.scriptLoading')
  }
})

const tabHint = computed(() => t(`nodeLifecycle.tabHint.${activeTab.value}`))

const osPickerOptions = computed(() => [
  { value: 'linux' as EnrollmentOs, label: t('nodesDeploy.osLinux'), meta: t('nodeLifecycle.osMetaLinux') },
  { value: 'windows' as EnrollmentOs, label: t('nodesDeploy.osWindows'), meta: t('nodeLifecycle.osMetaWindows') },
  { value: 'macos' as EnrollmentOs, label: t('nodesDeploy.osMacos'), meta: t('nodeLifecycle.osMetaMacos') },
])

const installLeadKey = computed(() => {
  if (props.os === 'windows') return 'nodeLifecycle.installLeadWindows'
  if (props.os === 'macos') return 'nodeLifecycle.installLeadMacos'
  return 'nodeLifecycle.installLeadLinux'
})

const installFlowRegisterText = computed(() => {
  if (props.role === 'proxy') return t('nodeLifecycle.installFlowRegisterProxy')
  if (props.role === 'gateway') return t('nodeLifecycle.installFlowRegisterGateway')
  return t('nodeLifecycle.installFlowRegister')
})

const consoleBarTitle = computed(() => {
  if (props.installOnly) {
    if (props.os === 'windows') return t('nodeLifecycle.consolePowerShell')
    if (props.os === 'macos') return t('nodeLifecycle.consoleZsh')
    return t('nodeLifecycle.consoleBash')
  }
  return t('nodeLifecycle.consoleTitle', { role: roleLabel.value })
})

const viewSupportedLabel = computed(() => {
  if (props.os === 'windows') return t('nodeLifecycle.viewSupportedWindows')
  if (props.os === 'macos') return t('nodeLifecycle.viewSupportedMacos')
  return t('nodeLifecycle.viewSupportedLinux')
})

const roleNote = computed(() => {
  const keys = roleDeployNotes(props.role)
  if (!keys.length) return ''
  return keys.map((k) => t(`nodesDeploy.${k}`)).join(' ')
})

function selectOs(next: EnrollmentOs) {
  if (isLinuxOnlyRole(props.role) && next !== 'linux') return
  emit('update:os', next)
}

function selectRole(next: NodeRole) {
  if (props.roleLocked) return
  emit('update:role', next)
  if (isLinuxOnlyRole(next) && props.os !== 'linux') {
    emit('update:os', 'linux')
  }
}

async function refreshInstallCommand(gen: number) {
  if (!props.orgKey || !roleSupportedOnOs(props.role, props.os)) {
    installCommand.value = roleSupportedOnOs(props.role, props.os)
      ? ''
      : t('nodeLifecycle.linuxOnlyRoleBlocked')
    return
  }
  loading.value = true
  installCommand.value = ''
  try {
    const { command } =
      props.role === 'gateway' && props.os === 'linux'
        ? props.gatewayScope === 'platform'
          ? await issuePlatformGatewayEnrollmentInstall({ note: 'deploy:platform-gateway' })
          : await issueGatewayEnrollmentInstall({ note: `deploy:${props.role}`, orgKey: props.orgKey })
        : await issueEnrollmentInstall({
            role: props.role,
            os: props.os,
            note: `deploy:${props.role}`,
          })
    if (gen !== generation) return
    installCommand.value = command
  } catch (e) {
    if (gen === generation) {
      installCommand.value = apiErrorMessage(e, t('nodesDeploy.scriptLoadFailed'))
    }
  } finally {
    if (gen === generation) loading.value = false
  }
}

async function refreshUpgradeCommand(gen: number) {
  if (!props.orgKey) {
    upgradeCommand.value = ''
    return
  }
  loading.value = true
  upgradeCommand.value = ''
  try {
    const { token } = await issueEnrollmentInstall({
      role: props.role,
      os: props.os,
      note: `upgrade:${props.role}`,
    })
    const release = await fetchAgentRelease({ role: props.role, token, os: props.os })
    if (gen !== generation) return
    releaseVersion.value = release.version
    const pkg = defaultPackagePath(props.os, release.version)
    upgradeCommand.value = buildLocalUpgradeCommand(
      props.os,
      pkg,
      true,
      release.download_url,
      props.role,
    )
  } catch {
    if (gen === generation) {
      releaseVersion.value = ''
      upgradeCommand.value = buildLocalUpgradeCommand(
        props.os,
        defaultPackagePath(props.os),
        false,
        '',
        props.role,
      )
    }
  } finally {
    if (gen === generation) loading.value = false
  }
}

function refreshStaticCommands() {
  uninstallCommand.value = buildLocalUninstallCommand(props.os, purgeAll.value, props.role)
  serviceCommand.value = buildLocalServiceCommand(props.os, serviceAction.value)
}

function refreshAll() {
  const gen = ++generation
  refreshStaticCommands()
  if (activeTab.value === 'install') {
    void refreshInstallCommand(gen)
  } else if (activeTab.value === 'upgrade') {
    void refreshUpgradeCommand(gen)
  }
}

watch(
  () => [props.orgKey, props.role, props.os] as const,
  () => {
    if (isLinuxOnlyRole(props.role) && props.os !== 'linux') {
      emit('update:os', 'linux')
    }
    refreshAll()
  },
  { immediate: true },
)

watch(
  () => props.initialTab,
  (tab) => {
    if (tab) activeTab.value = tab
  },
)

watch(activeTab, (tab) => {
  const gen = ++generation
  if (tab === 'install') void refreshInstallCommand(gen)
  else if (tab === 'upgrade') void refreshUpgradeCommand(gen)
})

watch([purgeAll, serviceAction, () => props.os], () => refreshStaticCommands())

watch(
  () => props.os,
  () => {
    supportOpen.value = false
  },
)

function onOsCardKeydown(event: KeyboardEvent, next: EnrollmentOs) {
  if (event.key === 'Enter' || event.key === ' ') {
    event.preventDefault()
    selectOs(next)
  }
}

function onCopy() {
  const text = displayCommand.value
  if (!text || loading.value) return
  emit('copy', text)
  copied.value = true
  if (copiedTimer) clearTimeout(copiedTimer)
  copiedTimer = setTimeout(() => {
    copied.value = false
  }, 2000)
}
</script>

<template>
  <div
    class="node-lifecycle-wizard agent-install-wizard"
    :class="{
      'agent-install-wizard--source-host': installOnly,
      'agent-install-wizard--ubuntu-host': isUbuntuHostDeploy,
    }"
  >
    <ElAlert
      v-if="!orgKey"
      type="warning"
      :closable="false"
      show-icon
      class="source-deploy-fullscreen__alert"
    >
      {{ t('nodesDeploy.missingOrgBanner') }}
    </ElAlert>

    <div class="fullscreen-form-step-stack">
      <div v-if="showRolePicker && !roleLocked" class="fullscreen-form-card">
        <section class="fullscreen-form-section">
          <h3 class="fullscreen-form-section__title">
            <span class="fullscreen-form-section__indicator" />
            {{ t('nodesDeploy.step2') }}
          </h3>
          <ElRadioGroup :model-value="role" class="deploy-role-grid" @update:model-value="selectRole">
            <ElRadio
              v-for="opt in roleOptions"
              :key="opt.value"
              :value="opt.value"
              :disabled="roleDisabled[opt.value as 'proxy' | 'gateway']"
              border
              class="deploy-role-option !mr-0"
            >
              <div>
                <div class="deploy-role-option__title">{{ opt.title }}</div>
                <div class="deploy-role-option__desc">{{ opt.desc }}</div>
              </div>
            </ElRadio>
          </ElRadioGroup>
        </section>
      </div>

      <div
        class="fullscreen-form-card"
        :class="{ 'agent-install-wizard__platform-card': installOnly }"
      >
        <section
          class="fullscreen-form-section"
          :class="{ 'agent-install-wizard__platform-section': installOnly }"
        >
          <div v-if="installOnly" class="agent-install-wizard__platform-head">
            <h3 class="fullscreen-form-section__title">
              <span class="fullscreen-form-section__indicator" />
              {{ isUbuntuHostDeploy ? t('nodesDeploy.proxyReqTitle') : t('nodeLifecycle.osStep') }}
            </h3>
          </div>
          <h3 v-else class="fullscreen-form-section__title">
            <span class="fullscreen-form-section__indicator" />
            {{ isUbuntuHostDeploy ? t('nodesDeploy.proxyReqTitle') : t('nodeLifecycle.osStep') }}
          </h3>

          <template v-if="isUbuntuHostDeploy">
            <div class="proxy-req-grid" role="list" :aria-label="t('nodesDeploy.proxyReqTitle')">
              <div
                v-for="card in proxyReqCards"
                :key="card.key"
                class="proxy-req-card"
                role="listitem"
              >
                <div class="proxy-req-card__icon-wrap" aria-hidden="true">
                  <UbuntuBrandIcon
                    v-if="card.kind === 'ubuntu'"
                    class="proxy-req-card__brand proxy-req-card__brand--ubuntu"
                  />
                  <component
                    v-else
                    :is="card.icon"
                    class="proxy-req-card__brand proxy-req-card__brand--hardware"
                    :size="32"
                  />
                </div>
                <span class="proxy-req-card__title">{{ card.title }}</span>
                <span class="proxy-req-card__meta">{{ card.sub }}</span>
              </div>
            </div>
          </template>

          <div
            v-else-if="installOnly"
            class="os-icon-grid"
            role="radiogroup"
            :aria-label="t('nodeLifecycle.osStep')"
          >
            <button
              v-for="opt in osPickerOptions"
              :key="opt.value"
              type="button"
              class="os-icon-card"
              :class="{ 'is-checked': os === opt.value }"
              role="radio"
              :aria-checked="os === opt.value"
              :disabled="osDisabled[opt.value as 'windows' | 'macos']"
              @click="selectOs(opt.value)"
              @keydown="onOsCardKeydown($event, opt.value)"
            >
              <span class="os-icon-card__top">
                <span
                  class="os-icon-card__icon-wrap"
                  :class="`os-icon-card__icon-wrap--${opt.value}`"
                >
                  <AgentPlatformBrandIcon :os="opt.value" class="os-icon-card__brand" />
                </span>
                <span class="os-icon-card__check" aria-hidden="true">
                  <span />
                </span>
              </span>
              <span class="os-icon-card__name">{{ opt.label }}</span>
              <span class="os-icon-card__meta">{{ opt.meta }}</span>
            </button>
          </div>

          <ElRadioGroup v-else :model-value="os" class="source-radio-row" @update:model-value="selectOs">
            <ElRadio value="linux" border class="source-radio-card !mr-0">{{ t('nodesDeploy.osLinux') }}</ElRadio>
            <ElRadio value="windows" border class="source-radio-card !mr-0" :disabled="osDisabled.windows">{{ t('nodesDeploy.osWindows') }}</ElRadio>
            <ElRadio value="macos" border class="source-radio-card !mr-0" :disabled="osDisabled.macos">{{ t('nodesDeploy.osMacos') }}</ElRadio>
          </ElRadioGroup>

          <div v-if="installOnly && !isUbuntuHostDeploy" class="agent-os-support" :class="{ 'is-open': supportOpen }">
            <button
              type="button"
              class="agent-os-support__toggle"
              :aria-expanded="supportOpen"
              @click="supportOpen = !supportOpen"
            >
              <span class="agent-os-support__toggle-main">
                <span class="agent-os-support__toggle-icon">
                  <Info :size="14" aria-hidden="true" />
                </span>
                <span>{{ viewSupportedLabel }}</span>
              </span>
              <ChevronDown class="agent-os-support__chevron" :size="16" aria-hidden="true" />
            </button>
            <div v-show="supportOpen" class="agent-os-support__body">
              <template v-if="os === 'linux'">
                <p class="agent-os-support__group">{{ t('nodeLifecycle.supportedGroupDeb') }}</p>
                <div class="agent-os-support__grid">
                  <div v-for="name in LINUX_DISTROS.deb" :key="name" class="agent-os-support__chip">{{ name }}</div>
                </div>
                <p class="agent-os-support__group">{{ t('nodeLifecycle.supportedGroupRpm') }}</p>
                <div class="agent-os-support__grid">
                  <div v-for="name in LINUX_DISTROS.rpm" :key="name" class="agent-os-support__chip">{{ name }}</div>
                </div>
                <p class="agent-os-support__group">{{ t('nodeLifecycle.supportedGroupCloud') }}</p>
                <div class="agent-os-support__grid">
                  <div v-for="name in LINUX_DISTROS.cloud" :key="name" class="agent-os-support__chip">{{ name }}</div>
                </div>
                <div class="agent-os-support__notes">
                  <p class="agent-os-support__note">
                    <strong>{{ t('nodeLifecycle.supportedLinuxAgentLabel') }}</strong>
                    <span>{{ t('nodeLifecycle.supportedLinuxAgentArch') }}</span>
                  </p>
                  <p class="agent-os-support__note">
                    <strong>{{ t('nodeLifecycle.supportedProxyGatewayLabel') }}</strong>
                    <span>{{ t('nodeLifecycle.supportedProxyGatewayUbuntu') }}</span>
                  </p>
                </div>
              </template>
              <template v-else-if="os === 'windows'">
                <p class="agent-os-support__group">{{ t('nodeLifecycle.supportedGroupDesktopServer') }}</p>
                <div class="agent-os-support__grid">
                  <div class="agent-os-support__chip">
                    <span class="agent-os-support__chip-name">Windows 10 / 11</span>
                    <span class="agent-os-support__chip-ver">{{ t('nodeLifecycle.supportedVer64Bit') }}</span>
                  </div>
                  <div class="agent-os-support__chip">
                    <span class="agent-os-support__chip-name">Windows Server</span>
                    <span class="agent-os-support__chip-ver">{{ t('nodeLifecycle.supportedVerServer64') }}</span>
                  </div>
                </div>
              </template>
              <template v-else>
                <p class="agent-os-support__group">{{ t('nodeLifecycle.supportedGroupHardware') }}</p>
                <div class="agent-os-support__grid">
                  <div class="agent-os-support__chip">
                    <span class="agent-os-support__chip-name">Apple Silicon</span>
                    <span class="agent-os-support__chip-ver">{{ t('nodeLifecycle.supportedVerAppleSilicon') }}</span>
                  </div>
                  <div class="agent-os-support__chip">
                    <span class="agent-os-support__chip-name">Intel Mac</span>
                    <span class="agent-os-support__chip-ver">{{ t('nodeLifecycle.supportedVerIntel64') }}</span>
                  </div>
                </div>
              </template>
            </div>
          </div>

          <p v-if="linuxOnlyRoleHint && !isUbuntuHostDeploy" class="fullscreen-form-field__hint">{{ linuxOnlyRoleHint }}</p>
        </section>
      </div>

      <div class="fullscreen-form-card">
        <section class="fullscreen-form-section">
          <template v-if="installOnly">
            <h3 class="fullscreen-form-section__title">
              <span class="fullscreen-form-section__indicator" />
              {{ t('nodeLifecycle.installCommandStep') }}
            </h3>
            <I18nT
              :keypath="installLeadKey"
              scope="global"
              tag="p"
              class="fullscreen-form-field__hint agent-install-wizard__command-lead"
            >
              <template #root><strong>root</strong></template>
              <template #sudo><strong>sudo</strong></template>
              <template #cmd><strong>CMD</strong></template>
              <template #powershell><strong>PowerShell</strong></template>
              <template #administrator><strong>{{ t('nodeLifecycle.installLeadAdministrator') }}</strong></template>
              <template #terminal><strong>{{ t('nodeLifecycle.installLeadTerminal') }}</strong></template>
            </I18nT>

            <div class="source-script-shell agent-install-wizard__console">
              <div class="agent-install-wizard__console-bar">
                <span>{{ consoleBarTitle }}</span>
              </div>
              <div
                v-loading="loading"
                class="agent-install-wizard__console-body"
                element-loading-background="rgba(43, 45, 54, 0.88)"
              >
                <pre class="agent-install-wizard__console-pre">{{ displayCommand }}</pre>
              </div>
              <div class="agent-install-wizard__console-foot agent-install-wizard__console-foot--copy-only">
                <button
                  type="button"
                  class="btn btn-primary agent-install-wizard__copy-btn"
                  :class="{ 'agent-install-wizard__copy-btn--done': copied }"
                  :disabled="!displayCommand || loading"
                  @click="onCopy"
                >
                  <Check v-if="copied" :size="12" aria-hidden="true" />
                  <Copy v-else :size="12" aria-hidden="true" />
                  <span>{{ copied ? t('nodesDeploy.copied') : t('nodesDeploy.clickCopyCmd') }}</span>
                </button>
              </div>
            </div>

            <div class="install-flow-note" :aria-label="t('nodeLifecycle.installFlowLabel')">
              <p class="install-flow-note__label">{{ t('nodeLifecycle.installFlowLabel') }}</p>
              <div class="install-flow-note__steps">
                <p class="install-flow-note__step">
                  <strong>{{ t('nodeLifecycle.installFlowStepDownload') }}</strong>{{ t('nodeLifecycle.installFlowDownload') }}
                </p>
                <p class="install-flow-note__step">
                  <strong>{{ t('nodeLifecycle.installFlowStepInstall') }}</strong>{{ t('nodeLifecycle.installFlowInstall') }}
                </p>
                <p class="install-flow-note__step">
                  <strong>{{ t('nodeLifecycle.installFlowStepRegister') }}</strong>{{ installFlowRegisterText }}
                </p>
              </div>
            </div>

          </template>

          <template v-else>
          <div class="node-lifecycle-wizard__tabs">
            <button
              v-for="tab in visibleTabs"
              :key="tab"
              type="button"
              class="node-lifecycle-wizard__tab"
              :class="{ 'node-lifecycle-wizard__tab--active': activeTab === tab }"
              @click="activeTab = tab"
            >
              {{ t(`nodeLifecycle.tab.${tab}`) }}
            </button>
          </div>

          <div class="agent-install-wizard__body-grid">
            <div class="agent-install-wizard__platform">
              <AgentPlatformBrandIcon :os="os" />
              <p class="agent-install-wizard__platform-name">{{ roleLabel }}</p>
              <div v-if="activeTab !== 'install'" class="agent-install-wizard__platform-hints">
                <p class="agent-install-wizard__platform-hint-line">{{ paths.installDir }}</p>
                <p class="agent-install-wizard__platform-hint-line">{{ paths.dataDir }}</p>
                <p class="agent-install-wizard__platform-hint-line">{{ paths.service }}</p>
              </div>
            </div>

            <div class="agent-install-wizard__command-col">
              <p class="fullscreen-form-field__hint agent-install-wizard__command-lead">{{ tabHint }}</p>

              <div v-if="activeTab === 'uninstall'" class="node-lifecycle-wizard__options">
                <ElCheckbox v-model="purgeAll">{{ t('nodeLifecycle.purgeAll') }}</ElCheckbox>
              </div>
              <div v-if="activeTab === 'service'" class="node-lifecycle-wizard__options">
                <ElRadioGroup v-model="serviceAction" size="small">
                  <ElRadio value="status">{{ t('nodeLifecycle.serviceStatus') }}</ElRadio>
                  <ElRadio value="start">{{ t('nodeLifecycle.serviceStart') }}</ElRadio>
                  <ElRadio value="stop">{{ t('nodeLifecycle.serviceStop') }}</ElRadio>
                  <ElRadio value="restart">{{ t('nodeLifecycle.serviceRestart') }}</ElRadio>
                </ElRadioGroup>
              </div>

              <div class="source-script-shell agent-install-wizard__console">
                <div class="agent-install-wizard__console-bar">
                  <span>{{ consoleBarTitle }}</span>
                  <span v-if="activeTab === 'upgrade' && releaseVersion">v{{ releaseVersion }}</span>
                </div>
                <div
                  v-loading="loading && (activeTab === 'install' || activeTab === 'upgrade')"
                  class="agent-install-wizard__console-body"
                  element-loading-background="rgba(43, 45, 54, 0.88)"
                >
                  <div v-if="loading && activeTab === 'upgrade'" class="proxy-install-wizard__generating">
                    <RefreshCw class="proxy-install-wizard__generating-icon" :size="14" aria-hidden="true" />
                    <span>{{ t('nodeLifecycle.upgradeLoading') }}</span>
                  </div>
                  <pre v-else class="agent-install-wizard__console-pre">{{ displayCommand }}</pre>
                </div>
                <div class="agent-install-wizard__console-foot">
                  <span class="agent-install-wizard__console-hint">{{ t(`nodeLifecycle.footnote.${activeTab}`) }}</span>
                  <button
                    type="button"
                    class="btn btn-primary agent-install-wizard__copy-btn"
                    :class="{ 'agent-install-wizard__copy-btn--done': copied }"
                    :disabled="!displayCommand || loading"
                    @click="onCopy"
                  >
                    <Check v-if="copied" :size="12" aria-hidden="true" />
                    <Copy v-else :size="12" aria-hidden="true" />
                    <span>{{ copied ? t('nodesDeploy.copied') : t('nodesDeploy.clickCopyCmd') }}</span>
                  </button>
                </div>
              </div>

              <div v-if="roleNote" class="add-s3-warning agent-install-wizard__warn" role="note">
                <TriangleAlert class="add-s3-warning__icon" :size="16" stroke-width="2" />
                <div class="agent-install-wizard__warn-body">
                  <p class="agent-install-wizard__warn-title">{{ t('nodesDeploy.notesTitle') }}</p>
                  <p class="agent-install-wizard__warn-desc">{{ roleNote }}</p>
                </div>
              </div>

              <div v-if="activeTab === 'upgrade'" class="add-s3-warning agent-install-wizard__warn" role="note">
                <TriangleAlert class="add-s3-warning__icon" :size="16" stroke-width="2" />
                <div class="agent-install-wizard__warn-body">
                  <p class="agent-install-wizard__warn-desc">{{ t('nodeLifecycle.upgradeOnlineHint') }}</p>
                  <p class="agent-install-wizard__warn-desc">{{ t('nodeLifecycle.upgradeInterruptHint') }}</p>
                </div>
              </div>
            </div>
          </div>
          </template>
        </section>
      </div>
    </div>
  </div>
</template>

<style scoped>
.node-lifecycle-wizard__tabs {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 16px;
}

.node-lifecycle-wizard__tab {
  border: 1px solid rgb(226 232 240);
  background: rgb(248 250 252);
  color: rgb(51 65 85);
  border-radius: 999px;
  padding: 6px 14px;
  font-size: 13px;
  cursor: pointer;
}

.node-lifecycle-wizard__tab--active {
  background: var(--color-info-light);
  border-color: var(--color-info-border);
  color: var(--color-info);
  font-weight: 600;
}

.node-lifecycle-wizard__options {
  margin-bottom: 12px;
}
</style>
