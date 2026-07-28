<script setup lang="ts">
import { computed, ref } from 'vue'
import { RouterLink } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { ArrowLeft, Clock3, ShieldCheck } from 'lucide-vue-next'
import { ElMessage } from 'element-plus'
import NodeLifecycleWizard from '../../../components/NodeLifecycleWizard.vue'
import DangerConfirmDialog from '../../../components/DangerConfirmDialog.vue'
import { copyTextToClipboard } from '../../../lib/clipboard'
import {
  auditPlatformGatewayEnrollmentCopy,
  revokePlatformGatewayEnrollment,
} from '../../../lib/nodeApi'
import { apiErrorMessage } from '../../../lib/api'

const { t } = useI18n()
const wizardRef = ref<{ clearInstallCommand: () => void } | null>(null)
const ttlSeconds = ref<900 | 3600 | 14400 | 86400>(900)
const tokenId = ref<number | null>(null)
const expiresAt = ref<string | null>(null)
const revokeOpen = ref(false)
const revoking = ref(false)

const expiresLabel = computed(() => {
  if (!expiresAt.value) return '—'
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: 'medium',
    timeStyle: 'short',
  }).format(new Date(expiresAt.value))
})

function onEnrollmentIssued(payload: { tokenId: number; expiresAt: string | null }) {
  tokenId.value = payload.tokenId
  expiresAt.value = payload.expiresAt
}

async function copyCommand(command: string) {
  try {
    await copyTextToClipboard(command)
    if (tokenId.value != null) {
      await auditPlatformGatewayEnrollmentCopy(tokenId.value).catch(() => undefined)
    }
    ElMessage.success({ message: t('nodesDeploy.copied'), grouping: true })
  } catch {
    ElMessage.error({ message: t('nodesDeploy.copyFailed'), grouping: true })
  }
}

async function confirmRevoke() {
  if (tokenId.value == null) return
  revoking.value = true
  try {
    await revokePlatformGatewayEnrollment(tokenId.value)
    tokenId.value = null
    expiresAt.value = null
    wizardRef.value?.clearInstallCommand()
    revokeOpen.value = false
    ElMessage.success({ message: t('platformOps.engineGateway.revokeSuccess'), grouping: true })
  } catch (error) {
    ElMessage.error({
      message: apiErrorMessage(error, t('platformOps.engineGateway.revokeFailed')),
      grouping: true,
    })
  } finally {
    revoking.value = false
  }
}
</script>

<template>
  <div class="platform-gateway-add">
    <RouterLink to="/platform-ops/engine/gateways" class="platform-gateway-add__back">
      <ArrowLeft :size="16" aria-hidden="true" />
      {{ t('platformOps.engineGateway.backToGateways') }}
    </RouterLink>

    <header class="platform-gateway-add__header">
      <div>
        <h1>{{ t('platformOps.engineGateway.addTitle') }}</h1>
        <p>{{ t('platformOps.engineGateway.addSubtitle') }}</p>
      </div>
      <div class="platform-gateway-add__lifetime">
        <label for="gateway-token-ttl">{{ t('platformOps.engineGateway.tokenLifetime') }}</label>
        <ElSelect id="gateway-token-ttl" v-model="ttlSeconds" :disabled="tokenId != null">
          <ElOption :value="900" :label="t('platformOps.engineGateway.lifetime15m')" />
          <ElOption :value="3600" :label="t('platformOps.engineGateway.lifetime1h')" />
          <ElOption :value="14400" :label="t('platformOps.engineGateway.lifetime4h')" />
          <ElOption :value="86400" :label="t('platformOps.engineGateway.lifetime24h')" />
        </ElSelect>
      </div>
    </header>

    <ElAlert type="warning" :closable="false" show-icon class="platform-gateway-add__security">
      {{ t('platformOps.engineGateway.securityNote') }}
    </ElAlert>

    <section v-if="tokenId != null" class="platform-gateway-add__token-status" aria-live="polite">
      <span class="platform-gateway-add__token-icon"><ShieldCheck :size="18" aria-hidden="true" /></span>
      <span class="platform-gateway-add__token-copy">
        <strong>{{ t('platformOps.engineGateway.tokenActive') }}</strong>
        <span><Clock3 :size="14" aria-hidden="true" />{{ t('platformOps.engineGateway.tokenExpires', { time: expiresLabel }) }}</span>
      </span>
      <ElButton type="danger" plain @click="revokeOpen = true">
        {{ t('platformOps.engineGateway.revoke') }}
      </ElButton>
    </section>

    <NodeLifecycleWizard
      ref="wizardRef"
      install-only
      generate-on-demand
      org-key="__platform_lens__"
      role="gateway"
      os="linux"
      role-locked
      gateway-scope="platform"
      :enrollment-ttl-seconds="ttlSeconds"
      @copy="copyCommand"
      @enrollment-issued="onEnrollmentIssued"
    />

    <DangerConfirmDialog
      v-model="revokeOpen"
      :title="t('platformOps.engineGateway.revokeTitle')"
      :message="t('platformOps.engineGateway.revokeMessage')"
      confirm-mode="keyword"
      :confirm-keyword="t('platformOps.engineGateway.revokeKeyword')"
      :confirm-text="t('platformOps.engineGateway.revoke')"
      :cancel-text="t('common.cancel')"
      :loading="revoking"
      @confirm="confirmRevoke"
    />
  </div>
</template>

<style scoped>
.platform-gateway-add {
  display: flex;
  flex-direction: column;
  gap: 16px;
  width: min(100%, 1120px);
  margin: 0 auto;
}

.platform-gateway-add__back {
  display: inline-flex;
  width: fit-content;
  min-height: 36px;
  align-items: center;
  gap: 6px;
  color: #4338ca;
  font-size: 13px;
  font-weight: 600;
}

.platform-gateway-add__header {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 24px;
}

.platform-gateway-add__header h1 {
  margin: 0;
  color: var(--color-text-title, #1d2129);
  font-size: 20px;
  font-weight: 600;
}

.platform-gateway-add__header p {
  margin: 6px 0 0;
  color: #475569;
  font-size: 13px;
}

.platform-gateway-add__lifetime {
  display: grid;
  width: 200px;
  flex-shrink: 0;
  gap: 6px;
}

.platform-gateway-add__lifetime label {
  color: #475569;
  font-size: 12px;
  font-weight: 600;
}

.platform-gateway-add__token-status {
  display: flex;
  min-height: 64px;
  align-items: center;
  gap: 12px;
  padding: 12px 16px;
  border: 1px solid #bbf7d0;
  border-radius: 10px;
  background: #f0fdf4;
}

.platform-gateway-add__token-icon {
  display: grid;
  width: 34px;
  height: 34px;
  place-items: center;
  border-radius: 50%;
  background: #dcfce7;
  color: #166534;
}

.platform-gateway-add__token-copy {
  display: grid;
  min-width: 0;
  flex: 1;
  gap: 3px;
  color: #14532d;
  font-size: 13px;
}

.platform-gateway-add__token-copy > span {
  display: inline-flex;
  align-items: center;
  gap: 5px;
}

@media (max-width: 640px) {
  .platform-gateway-add__header {
    align-items: stretch;
    flex-direction: column;
    gap: 12px;
  }

  .platform-gateway-add__lifetime {
    width: 100%;
  }

  .platform-gateway-add__token-status {
    align-items: flex-start;
    flex-wrap: wrap;
  }

  .platform-gateway-add__token-copy {
    flex-basis: calc(100% - 46px);
  }

  .platform-gateway-add__token-status :deep(.el-button) {
    width: 100%;
    min-height: 44px;
  }
}
</style>

<style src="../../../styles/resource-add.css"></style>
<style src="../../../styles/source-deploy-ui.css"></style>
<style src="../../../styles/agent-install-wizard.css"></style>
