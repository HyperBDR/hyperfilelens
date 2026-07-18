import type { Component } from 'vue'
import { AtSign, Globe, Mail, MessageSquare, MessagesSquare } from 'lucide-vue-next'
import type { ChannelType } from '../pages/ops/notificationTypes'

export const notificationTypeIcons: Record<ChannelType, Component> = {
  email: Mail,
  webhook: Globe,
  dingtalk: MessageSquare,
  wecom: MessagesSquare,
  sms: AtSign,
}

export function getNotificationTypeIcon(type: ChannelType | string | undefined | null): Component | null {
  if (type && type in notificationTypeIcons) {
    return notificationTypeIcons[type as ChannelType]
  }
  return null
}
