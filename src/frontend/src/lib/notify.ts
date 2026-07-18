import { ElMessage } from 'element-plus'
import type {
  MessageHandler,
  MessageOptionsWithType,
  MessageParamsWithType,
  MessageType,
} from 'element-plus'

type NotifyType = Extract<MessageType, 'success' | 'warning' | 'error' | 'info'>
type NotifyDefaults = Pick<MessageOptionsWithType, 'duration' | 'showClose' | 'offset' | 'grouping'>

const DEFAULTS: Record<NotifyType, NotifyDefaults> = {
  success: { duration: 2200, showClose: false, offset: 72, grouping: true },
  info: { duration: 2600, showClose: false, offset: 72, grouping: true },
  warning: { duration: 3600, showClose: true, offset: 72, grouping: true },
  error: { duration: 5000, showClose: true, offset: 72, grouping: true },
}

const MESSAGE_OPTION_KEYS = [
  'appendTo',
  'customClass',
  'dangerouslyUseHTMLString',
  'duration',
  'grouping',
  'icon',
  'message',
  'offset',
  'onClose',
  'placement',
  'plain',
  'repeatNum',
  'showClose',
  'zIndex',
]

function isMessageOptions(value: MessageParamsWithType): value is MessageOptionsWithType {
  return Boolean(
    value
      && typeof value === 'object'
      && !Array.isArray(value)
      && MESSAGE_OPTION_KEYS.some((key) => key in value),
  )
}

function notify(type: NotifyType, options?: MessageParamsWithType): MessageHandler {
  const defaults = DEFAULTS[type]
  if (isMessageOptions(options)) {
    return ElMessage[type]({ ...defaults, ...options, grouping: true })
  }

  return ElMessage[type]({ ...defaults, message: options ?? '', grouping: true })
}

export function notifySuccess(options?: MessageParamsWithType): MessageHandler {
  return notify('success', options)
}

export function notifyWarning(options?: MessageParamsWithType): MessageHandler {
  return notify('warning', options)
}

export function notifyError(options?: MessageParamsWithType): MessageHandler {
  return notify('error', options)
}

export function notifyInfo(options?: MessageParamsWithType): MessageHandler {
  return notify('info', options)
}

export { notify }
