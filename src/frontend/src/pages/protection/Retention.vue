<script setup lang="ts">
import {  onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { Plus } from 'lucide-vue-next'
import { api } from '../../lib/api'
import { formatLocalDateTime } from '../../lib/dateTime'
import { asList } from '../../lib/parse'
import Modal from '../../components/Modal.vue'
import ModulePage from '../../components/ModulePage.vue'
import { useProtectionSideNav } from '../../composables/useProtectionSideNav'
import { booleanStatusTag } from '../../lib/statusTag'

type RetentionRule = { id: number; organization: number; name: string; spec: unknown; is_active: boolean; updated_at?: string }

const rows = ref<RetentionRule[]>([])
const open = ref(false)
const busy = ref(false)
const form = ref({ organization: '', name: '' })

const { t } = useI18n()

const protectionMenus = useProtectionSideNav()

function formatDate(value?: string | null) {
  return formatLocalDateTime(value, '--')
}

async function load() {
  const data = await api<unknown>(`/api/v1/protection/retention-rules/`)
  rows.value = asList<RetentionRule>(data)
}

onMounted(() => {
  load().catch(() => {
    rows.value = []
  })
})

async function save() {
  busy.value = true
  try {
    await api(`/api/v1/protection/retention-rules/`, {
      method: 'POST',
      body: JSON.stringify({
        organization: Number(form.value.organization),
        name: form.value.name,
        spec: {
          latest: 10,
          hourly: 24,
          daily: 7,
          weekly: 4,
          monthly: 12,
          yearly: 3,
        },
        is_active: true,
      }),
    })
    open.value = false
    form.value = { organization: '', name: '' }
    await load()
  } finally {
    busy.value = false
  }
}
</script>

<template>
  <ModulePage :title="t('protection.side.retention')" :menus="protectionMenus">
    <template #actions>
      <ElButton type="primary" @click="open = true">
        <Plus :size="16" /> {{ t('protection.retentionPage.btnNewRule') }}
      </ElButton>
    </template>

    <div class="hfl-list-panel">
      <el-table
          v-table-overflow-title :data="rows" stripe :loading="busy">
        <el-table-column prop="name" :label="t('protection.retentionPage.colRule')" min-width="150" />
        <el-table-column :label="t('protection.retentionPage.colStatus')" width="100">
          <template #default="{ row }">
            <el-tag
              :type="booleanStatusTag(row.is_active).type"
              :class="booleanStatusTag(row.is_active).class"
              size="small"
            >
              {{ row.is_active ? t('protection.retentionPage.statusOn') : t('protection.retentionPage.statusPaused') }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column :label="t('protection.retentionPage.colSpec')" min-width="200">
          <template #default="{ row }">{{ JSON.stringify(row.spec || {}) }}</template>
        </el-table-column>
        <el-table-column prop="updated_at" :label="t('protection.retentionPage.colUpdated')" min-width="180">
          <template #default="{ row }">
            <span class="hfl-table-cell-time">{{ formatDate(row.updated_at) }}</span>
          </template>
        </el-table-column>
        <template #empty>
          <el-empty :description="t('protection.retentionPage.empty')" :image-size="80" />
        </template>
      </el-table>
    </div>

    <Modal :open="open" :title="t('protection.retentionPage.modalTitle')" @close="open = false">
      <ElForm label-position="right" label-width="auto">
        <ElFormItem :label="t('protection.retentionPage.labelOrgId')">
          <ElInput v-model="form.organization" :placeholder="t('protection.retentionPage.phOrgId')" />
        </ElFormItem>
        <ElFormItem :label="t('protection.retentionPage.labelRuleName')">
          <ElInput v-model="form.name" :placeholder="t('protection.retentionPage.phRuleName')" />
        </ElFormItem>
      </ElForm>
      <div class="mt-4 flex justify-end gap-2">
        <ElButton @click="open = false">{{ t('common.cancel') }}</ElButton>
        <ElButton type="primary" :disabled="busy" @click="save">{{ t('protection.retentionPage.btnSave') }}</ElButton>
      </div>
    </Modal>
  </ModulePage>
</template>
