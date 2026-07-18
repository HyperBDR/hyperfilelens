<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { RouterLink, useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { Globe, Shield } from 'lucide-vue-next'
import NavNotificationPopover from '../../components/NavNotificationPopover.vue'
import NavUserMenu from '../../components/NavUserMenu.vue'
import OrgSwitcher from '../../components/OrgSwitcher.vue'
import AppLogoMark from '../../components/AppLogoMark.vue'
import { useLocaleSwitch } from '../../composables/useLocaleSwitch'
import { fetchDeployProfile } from '../../composables/useDeployProfile'
import { currentUser } from '../../composables/useAuth'
import { beginRouteRequestScope } from '../../lib/routeRequestAbort'
import { beginRouteTransition } from '../../lib/routeTransition'

const { t } = useI18n()
const { canSwitchLocale, nextLocaleLabel, toggleLocale } = useLocaleSwitch()

const adminConsoleUrl = ref('')

async function refreshAdminConsoleEntry() {
  const profile = await fetchDeployProfile(true)
  adminConsoleUrl.value = profile?.admin_console_entry_visible
    ? profile.admin_console_url
    : ''
}

onMounted(() => {
  void refreshAdminConsoleEntry()
})

watch(
  () => currentUser.value?.id,
  () => {
    void refreshAdminConsoleEntry()
  },
)

const navItems = computed(() => [
  { to: '/', label: t('nav.overview') },
  { to: '/protection', label: t('nav.protection') },
  { to: '/insight', label: t('nav.insight') },
  { to: '/node', label: t('nav.node') },
  { to: '/ops', label: t('nav.ops') },
])

const route = useRoute()
const router = useRouter()

const timezoneDisplay = computed(() => {
  const offset = new Date().getTimezoneOffset()
  const sign = offset <= 0 ? '+' : '-'
  const absOffset = Math.abs(offset)
  const hours = String(Math.floor(absOffset / 60)).padStart(2, '0')
  const minutes = String(absOffset % 60).padStart(2, '0')
  return `${t('nav.timezone')}GMT${sign}${hours}:${minutes}`
})

function pathMatchesPrefix(path: string, prefix: string) {
  return path === prefix || path.startsWith(`${prefix}/`)
}

/** Route prefixes moved from infrastructure into protection or insights. */
const protectionRoutePrefixes = [
  '/protection/backup-sources',
  '/node/agents',
  '/node/repositories',
  '/node/snapshots',
  '/node/deployment',
]
const insightRoutePrefixes = ['/node/ai-settings', '/node/knowledge-base', '/node/gateways']

function navActive(to: string) {
  const path = route.path
  if (to === '/') return path === '/'

  if (to === '/protection') {
    if (pathMatchesPrefix(path, to)) return true
    return protectionRoutePrefixes.some((p) => pathMatchesPrefix(path, p))
  }

  if (to === '/insight') {
    if (pathMatchesPrefix(path, to)) return true
    return insightRoutePrefixes.some((p) => pathMatchesPrefix(path, p))
  }

  if (to === '/node') {
    if (protectionRoutePrefixes.some((p) => pathMatchesPrefix(path, p))) return false
    if (insightRoutePrefixes.some((p) => pathMatchesPrefix(path, p))) return false
    return pathMatchesPrefix(path, to)
  }

  return pathMatchesPrefix(path, to)
}

function navigateImmediately(to: string) {
  if (to === route.fullPath) return
  beginRouteTransition()
  beginRouteRequestScope()
  void router.push(to)
}

function handleNavClick(event: MouseEvent, to: string) {
  if (event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return
  event.preventDefault()
  navigateImmediately(to)
}
</script>

<template>
  <header class="top-nav">
    <div class="logo" @click="navigateImmediately('/')">
      <AppLogoMark :size="18" />
      <span class="logo-text"><span>Hyper</span><strong>FileLens</strong></span>
    </div>

    <nav class="nav-menu">
      <RouterLink
        v-for="item in navItems"
        :key="item.to"
        :to="item.to"
        :class="{ active: navActive(item.to) }"
        class="nav-item"
        @click="handleNavClick($event, item.to)"
      >
        {{ item.label }}
      </RouterLink>
    </nav>

    <div class="right-menu">
      <span class="timezone-display">
        {{ timezoneDisplay }}
      </span>

      <ElButton
        v-if="canSwitchLocale"
        class="icon-btn"
        :title="`Switch to ${nextLocaleLabel}`"
        @click="toggleLocale"
        text
      >
        <Globe :size="16" />
      </ElButton>

      <OrgSwitcher />

      <a
        v-if="adminConsoleUrl"
        class="platform-ops-entry"
        :href="`${adminConsoleUrl}/platform-ops/monitoring/host`"
        target="_blank"
        rel="noopener noreferrer"
      >
        <Shield :size="15" aria-hidden="true" />
        <span>{{ t('nav.platformOps') }}</span>
      </a>

      <div class="icon-btn alerts-btn">
        <NavNotificationPopover />
      </div>

      <NavUserMenu />
    </div>
  </header>
</template>

<style scoped>
.top-nav {
  --topnav-height: 52px;
  --brand-color: var(--color-primary, #6D5EF6);
  --brand-glow: rgba(109, 94, 246, 0.5);
  --nav-item-active-color: var(--color-primary, #6D5EF6);

  height: var(--topnav-height);
  background:
    var(--tnav-overlay, linear-gradient(180deg, rgba(255, 255, 255, 0.045), rgba(255, 255, 255, 0))),
    var(--tnav-bg, #0F0F17);
  border-bottom: 1px solid var(--tnav-border, rgba(109, 94, 246, 0.24));
  position: sticky;
  top: 0;
  z-index: 40;
  display: flex;
  align-items: center;
  padding: 0 16px 0 12px;
  box-shadow: var(--tnav-shadow, 0 12px 26px rgba(9, 8, 15, 0.22));
  font-family: var(--font-sans);
}

.logo {
  display: flex;
  align-items: center;
  gap: 9px;
  width: 150px;
  height: 100%;
  cursor: pointer;
  padding-left: 0;
}

.logo-text {
  display: inline-flex;
  align-items: baseline;
  gap: 2px;
  font-size: 14px;
  font-weight: 850;
  color: var(--tnav-text, #fff);
  letter-spacing: 0;
  line-height: 1;
}

.logo-text > span {
  color: var(--nav-active-accent, #F5A623);
  font-weight: 850;
}

.logo-text strong {
  color: #f8fafc;
  font-weight: 850;
}

.nav-menu {
  display: flex;
  align-items: center;
  height: 52px;
}

.nav-item {
  position: relative;
  height: 52px;
  min-width: 90px;
  padding: 0 16px;
  font-size: 13px;
  font-weight: 650;
  color: #a1a1aa;
  text-decoration: none;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 8px 8px 0 0;
  transition: color 150ms ease, background-color 150ms ease;
}

.nav-item:hover {
  color: var(--nav-item-hover-color, #E2E2E2);
  background-color: var(--nav-item-hover-bg, rgba(255, 255, 255, 0.05));
}

.nav-item.active {
  color: #f8fafc;
  background: rgba(109, 94, 246, 0.1);
}

.nav-item.active::before {
  content: '';
  position: absolute;
  left: 18px;
  right: 18px;
  bottom: -1px;
  height: 18px;
  background: radial-gradient(ellipse at center, rgba(109, 94, 246, 0.42), transparent 68%);
  pointer-events: none;
}

.nav-item.active::after {
  content: '';
  position: absolute;
  left: 32px;
  right: 32px;
  bottom: 6px;
  width: auto;
  height: 2px;
  transform: none;
  --tw-gradient-from: var(--nav-active-accent, #F5A623);
  --tw-gradient-to: var(--nav-active-accent, #F5A623);
  --tw-gradient-position: to right in oklab;
  background-image: linear-gradient(var(--tw-gradient-position), var(--tw-gradient-from), var(--tw-gradient-to));
  box-shadow: var(--nav-active-line-shadow, 0 -2px 12px rgba(245, 166, 35, 0.35));
}

.right-menu {
  margin-left: auto;
  display: flex;
  align-items: center;
  gap: 4px;
}

.icon-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 4px;
  height: 32px;
  width: 32px;
  padding: 0;
  color: var(--icon-btn-color, #aeb2c5);
  border-radius: 6px;
  cursor: pointer;
  text-decoration: none;
  border: none;
  background: transparent;
  font-size: 13px;
  transition: all 150ms ease;
  margin: 0;
}

.timezone-display {
  height: 32px;
  padding: 0 10px;
  margin-right: 12px;
  font-size: 13px;
  font-weight: 500;
  line-height: 1.5;
  color: var(--tz-color, #c9cdd4);
  display: flex;
  align-items: center;
  border-radius: 10px;
  background: var(--tz-bg, rgba(255, 255, 255, 0.06));
  border: 1px solid var(--tz-border, rgba(255, 255, 255, 0.12));
}

.icon-btn:hover {
  background: var(--icon-btn-hover-bg, rgba(255, 255, 255, 0.08)) !important;
  color: var(--icon-btn-hover-color, #E2E2E2) !important;
}

.alerts-btn {
  position: relative;
}

.theme-options {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.theme-options-title {
  font-size: 12px;
  color: var(--el-text-color-secondary);
  padding: 0 4px 4px;
  border-bottom: 1px solid var(--el-border-color-lighter);
  margin-bottom: 4px;
}

.theme-option {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 8px;
  border-radius: 6px;
  cursor: pointer;
  transition: background-color 150ms ease;
  position: relative;
}

.theme-option:hover {
  background-color: var(--el-fill-color-light);
}

.theme-option.active {
  background-color: var(--el-fill-color);
}

.theme-preview {
  width: 80px;
  height: 48px;
  border-radius: 4px;
  overflow: hidden;
  display: flex;
  border: 1px solid var(--el-border-color);
}

.preview-sidebar {
  width: 16px;
}

.preview-content {
  flex: 1;
  padding: 4px;
  display: flex;
  flex-direction: column;
  gap: 3px;
}

.preview-header {
  height: 8px;
  border-radius: 2px;
}

.preview-body {
  flex: 1;
  border-radius: 2px;
}

.theme-option-info {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  color: var(--el-text-color-primary);
}

.theme-check {
  position: absolute;
  right: 8px;
  color: var(--el-color-primary);
}

.preview-light {
  background: #F5F5F5;
}
.preview-light .preview-sidebar {
  background: #E8E8E8;
}
.preview-light .preview-header {
  background: #DDD;
}
.preview-light .preview-body {
  background: #EEE;
}

.preview-hybrid {
  background: #F5F5F5;
  position: relative;
  padding-top: 10px;
}
.preview-hybrid .preview-sidebar {
  position: absolute;
  left: 0;
  top: 10px;
  bottom: 0;
  width: 16px;
  background: #2C2C2E;
}
.preview-hybrid .preview-header {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  height: 10px;
  background: #2C2C2E;
}
.preview-hybrid .preview-content {
  margin-left: 16px;
  padding: 4px;
  flex: 1;
  background: #F5F5F5;
}

.preview-dark {
  background: #1C1C1E;
}
.preview-dark .preview-sidebar {
  background: #2C2C2E;
}
.preview-dark .preview-header {
  background: #3A3A3C;
}
.preview-dark .preview-body {
  background: #2C2C2E;
}

.platform-ops-entry {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 6px 10px;
  border: 1px solid rgba(148, 163, 184, 0.35);
  border-radius: 8px;
  color: var(--nav-item-color, #bec2d4);
  font-size: 13px;
  font-weight: 500;
  line-height: 1.5;
  text-decoration: none;
  white-space: nowrap;
}

.platform-ops-entry:hover {
  border-color: var(--color-primary, #6D5EF6);
  color: var(--nav-item-hover-color, #fff);
}

</style>
