import type { App } from 'vue'
import HflPagination from '../components/HflPagination.vue'
import HflPopover from '../components/HflPopover.vue'
import { setupTableColumnResizeDirective } from '../directives/tableColumnResize'
import { setupTableHeaderScrollSyncDirective } from '../directives/tableHeaderScrollSync'
import { setupTableOverflowTitleDirective } from '../directives/tableOverflowTitle'
import {
  ElTable,
  ElTableColumn,
  ElButton,
  ElDialog,
  ElForm,
  ElFormItem,
  ElInput,
  ElSelect,
  ElOption,
  ElDatePicker,
  ElPagination,
  ElTag,
  ElDropdown,
  ElDropdownMenu,
  ElDropdownItem,
  ElMessage,
  ElMessageBox,
  ElTooltip,
  ElIcon,
  ElEmpty,
  ElBadge,
  ElSwitch,
  ElCheckbox,
  ElRadio,
  ElRadioGroup,
  ElRadioButton,
  ElInputNumber,
  ElSlider,
  ElUpload,
  ElProgress,
  ElSkeleton,
  ElAlert,
  ElLoading,
  ElTabs,
  ElTabPane,
  ElSteps,
  ElStep,
  ElDescriptions,
  ElDescriptionsItem,
  ElCheckboxGroup,
  ElResult,
  ElDrawer,
  ElDivider,
  ElCollapse,
  ElCollapseItem,
  ElTree,
  ElTimeline,
  ElTimelineItem,
  ElSegmented,
} from 'element-plus'
import type { MessageHandler, MessageParamsWithType } from 'element-plus'

function isEmptyMessage(options?: MessageParamsWithType): boolean {
  if (options == null) return true
  if (typeof options === 'string') return options.trim() === ''
  if (typeof options === 'object' && 'message' in options) {
    const message = options.message
    return message == null || String(message).trim() === ''
  }
  return false
}

function noopMessageHandler(): MessageHandler {
  return { close: () => undefined } as MessageHandler
}

function installEmptyErrorMessageGuard() {
  const originalError = ElMessage.error.bind(ElMessage)
  ;(ElMessage as typeof ElMessage & { error: typeof ElMessage.error }).error = ((options?: MessageParamsWithType) => {
    if (isEmptyMessage(options)) return noopMessageHandler()
    return originalError(options)
  }) as typeof ElMessage.error
}

export function setupElementPlus(app: App) {
  installEmptyErrorMessageGuard()

  // Register all Element Plus components
  const components = [
    ElTable,
    ElTableColumn,
    ElButton,
    ElDialog,
    ElForm,
    ElFormItem,
    ElInput,
    ElSelect,
    ElOption,
    ElDatePicker,
    ElPagination,
    ElTag,
    ElDropdown,
    ElDropdownMenu,
    ElDropdownItem,
    ElTooltip,
    ElIcon,
    ElEmpty,
    ElBadge,
    ElSwitch,
    ElCheckbox,
    ElRadio,
    ElRadioGroup,
    ElRadioButton,
    ElInputNumber,
    ElSlider,
    ElUpload,
    ElProgress,
    ElSkeleton,
    ElAlert,
    ElTabs,
    ElTabPane,
    ElSteps,
    ElStep,
    ElDescriptions,
    ElDescriptionsItem,
    ElCheckboxGroup,
    ElResult,
    ElDrawer,
    ElDivider,
    ElCollapse,
    ElCollapseItem,
    ElTree,
    ElTimeline,
    ElTimelineItem,
    ElSegmented,
  ]

  components.forEach((component) => {
    app.component(component.name!, component)
  })

  app.component('HflPagination', HflPagination)
  app.component('HflPopover', HflPopover)
  setupTableColumnResizeDirective(app)
  setupTableHeaderScrollSyncDirective(app)
  setupTableOverflowTitleDirective(app)

  // Configure global properties
  app.config.globalProperties.$message = ElMessage
  app.config.globalProperties.$msgbox = ElMessageBox
  app.config.globalProperties.$messageBox = ElMessageBox
  app.config.globalProperties.$loading = ElLoading.directive

  // Provide loading directive
  app.directive('loading', ElLoading.directive)
}

export default setupElementPlus
