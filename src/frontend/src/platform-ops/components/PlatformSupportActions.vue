<script setup lang="ts">
import { ref } from 'vue'
import { RouterLink } from 'vue-router'
import { ExternalLink, LifeBuoy } from 'lucide-vue-next'
import { ElMessage } from 'element-plus'
import { startSupportSession } from '../lib/platformOpsApi'
import { apiErrorMessage } from '../../lib/api'

const props = defineProps<{
  orgId: number
  orgKey: string
  tenantPath: string
  relatedLinks?: Array<{ label: string; to: string }>
}>()

const opening = ref(false)

async function openInCustomerAccount() {
  if (opening.value) return
  opening.value = true
  try {
    const session = await startSupportSession(props.orgId)
    const target = new URL(props.tenantPath, `${session.tenant_url.replace(/\/$/, '')}/`)
    target.searchParams.set('org', session.org_key)
    window.open(target.toString(), '_blank', 'noopener,noreferrer')
  } catch (error) {
    ElMessage.error({
      message: apiErrorMessage(error, 'Failed to open customer account support mode'),
      grouping: true,
    })
  } finally {
    opening.value = false
  }
}
</script>

<template>
  <div class="platform-support-actions">
    <p class="platform-support-actions__note">
      This configuration is managed inside the customer account. Admin Console access is read-only.
    </p>
    <div class="platform-support-actions__buttons">
      <RouterLink :to="`/platform-ops/orgs/${orgId}`">
        <ElButton><LifeBuoy :size="15" aria-hidden="true" />Open Customer Account</ElButton>
      </RouterLink>
      <ElButton type="primary" :loading="opening" @click="openInCustomerAccount">
        <ExternalLink :size="15" aria-hidden="true" />View in Customer Account
      </ElButton>
    </div>
    <div v-if="relatedLinks?.length" class="platform-support-actions__related">
      <span>Related:</span>
      <RouterLink v-for="link in relatedLinks" :key="link.to" :to="link.to">{{ link.label }}</RouterLink>
    </div>
  </div>
</template>

<style scoped>
.platform-support-actions {
  display: grid;
  gap: 12px;
  padding: 14px;
  border: 1px solid #c7d2fe;
  border-radius: 9px;
  background: #eef2ff;
}

.platform-support-actions__note {
  margin: 0;
  color: #3730a3;
  font-size: 13px;
  line-height: 1.5;
}

.platform-support-actions__buttons,
.platform-support-actions__related {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
}

.platform-support-actions__related {
  color: #475569;
  font-size: 12px;
}

.platform-support-actions__related a {
  color: #4338ca;
  font-weight: 600;
}

@media (max-width: 480px) {
  .platform-support-actions__buttons,
  .platform-support-actions__buttons a,
  .platform-support-actions__buttons :deep(.el-button) {
    width: 100%;
  }

  .platform-support-actions__buttons :deep(.el-button) {
    min-height: 44px;
  }
}
</style>
