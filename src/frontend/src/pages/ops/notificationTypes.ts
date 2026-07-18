export type ChannelType = 'email' | 'sms' | 'webhook' | 'dingtalk' | 'wecom'

export interface NotificationChannelRow {
  id: number
  name: string
  type: ChannelType
  enabled: boolean
  config?: Record<string, unknown>
  createdAt?: string
  created_at?: string
  updatedAt?: string
  updated_at?: string
}
