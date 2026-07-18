<script setup lang="ts">
import { ref } from 'vue'
import { ElMessage } from 'element-plus'
import HostSourceDetailDrawer from '../../../components/HostSourceDetailDrawer.vue'
import { apiErrorMessage } from '../../../lib/api'
import { listAllNodes } from '../../../lib/nodeApi'
import { getSourceResource, type SourceResource } from '../../../lib/sourceApi'
import type { ApiNode } from '../../../types/node'
import type { FlowSourceRow } from '../composables/useFlowSourceAggregate'
import NasSourceDetailDrawer from './NasSourceDetailDrawer.vue'

const hostOpen = ref(false)
const hostNodeId = ref<number | null>(null)
const nasOpen = ref(false)
const nasResource = ref<SourceResource | null>(null)
const proxyNodes = ref<ApiNode[]>([])
const loading = ref(false)

async function open(source: FlowSourceRow) {
  const refId = Number(source.refId || source.id.split(':')[1])
  if (!Number.isInteger(refId) || refId <= 0) return
  if (source.type === 'host') {
    hostNodeId.value = refId
    hostOpen.value = true
    return
  }
  if (loading.value) return
  loading.value = true
  try {
    const [resource, nodes] = await Promise.all([getSourceResource(refId), listAllNodes()])
    nasResource.value = resource
    proxyNodes.value = nodes.filter((node) => node.role === 'proxy')
    nasOpen.value = true
  } catch (err) {
    ElMessage.error({ message: apiErrorMessage(err), grouping: true })
  } finally {
    loading.value = false
  }
}

function setHostOpen(value: boolean) {
  hostOpen.value = value
  if (!value) hostNodeId.value = null
}

defineExpose({ open })
</script>

<template>
  <HostSourceDetailDrawer
    :model-value="hostOpen"
    :node-id="hostNodeId"
    :source="null"
    @update:model-value="setHostOpen"
  />
  <NasSourceDetailDrawer
    v-if="nasOpen"
    v-model="nasOpen"
    :resource="nasResource"
    :proxy-nodes="proxyNodes"
  />
</template>
