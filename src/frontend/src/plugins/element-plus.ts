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
import { notifyError, notifyInfo, notifySuccess, notifyWarning, type NotifyHandler } from '../lib/notify'

function noopMessageHandler(): MessageHandler {
  return { close: () => undefined } as MessageHandler
}

function bridgeMessageOptions(options?: MessageParamsWithType) {
  if (options == null) return null
  if (typeof options === 'string') return { message: options }
  if (typeof options === 'object' && 'message' in options && typeof options.message === 'string') {
    return {
      message: options.message,
      duration: options.duration,
      onClose: options.onClose,
    }
  }
  return null
}

function asMessageHandler(handler: NotifyHandler): MessageHandler {
  return handler as MessageHandler
}

let toastMessageBridgeInstalled = false

function installToastMessageBridge() {
  if (toastMessageBridgeInstalled) return
  toastMessageBridgeInstalled = true
  const originals = {
    success: ElMessage.success.bind(ElMessage),
    info: ElMessage.info.bind(ElMessage),
    warning: ElMessage.warning.bind(ElMessage),
    error: ElMessage.error.bind(ElMessage),
  }
  const bridges = {
    success: notifySuccess,
    info: notifyInfo,
    warning: notifyWarning,
    error: notifyError,
  }

  for (const type of ['success', 'info', 'warning', 'error'] as const) {
    ElMessage[type] = ((options?: MessageParamsWithType) => {
      const normalized = bridgeMessageOptions(options)
      if (!normalized) {
        if (type === 'error' && options != null && String(options).trim() === '') return noopMessageHandler()
        return originals[type](options)
      }
      if (!normalized.message.trim()) return noopMessageHandler()
      return asMessageHandler(bridges[type](normalized))
    }) as typeof ElMessage[typeof type]
  }
}

export function setupElementPlus(app: App) {
  installToastMessageBridge()

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
