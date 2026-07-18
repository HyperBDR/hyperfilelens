import { computed, type Ref } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { ElMessage } from 'element-plus'

type OrgLinkedRow = {
  organization_id?: number | null
}

export function usePlatformOpsReadonlyListActions<T extends OrgLinkedRow>(
  selected: Ref<T[]>,
  options?: { orgLinked?: boolean },
) {
  const router = useRouter()
  const { t } = useI18n()
  const orgLinked = options?.orgLinked ?? true

  const editDisabled = computed(() => {
    if (selected.value.length !== 1) return true
    if (!orgLinked) return true
    return !Number(selected.value[0]?.organization_id)
  })

  const deleteDisabled = computed(() => selected.value.length === 0)

  function onAdd() {
    ElMessage.info({ message: t('platformOps.list.addNotSupported'), grouping: true })
  }

  function onEdit() {
    if (selected.value.length !== 1) {
      ElMessage.warning({ message: t('platformOps.list.msgSelectOne'), grouping: true })
      return
    }
    const orgId = Number(selected.value[0]?.organization_id)
    if (!orgId) {
      ElMessage.warning({ message: t('platformOps.list.editNotSupported'), grouping: true })
      return
    }
    router.push(`/platform-ops/orgs/${orgId}`)
  }

  function onDelete() {
    ElMessage.info({ message: t('platformOps.list.deleteNotSupported'), grouping: true })
  }

  return {
    editDisabled,
    deleteDisabled,
    onAdd,
    onEdit,
    onDelete,
  }
}
