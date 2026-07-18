import type { Component } from 'vue'
import { Activity, BellRing, ClipboardList, Monitor, ShieldCheck } from 'lucide-vue-next'

const alertPolicyTypeIcons = {
  metric: Activity,
  task: ClipboardList,
  event: BellRing,
  system: Monitor,
  availability: ShieldCheck,
} as const

export function getAlertPolicyTypeIcon(type?: string | null): Component | null {
  if (type && type in alertPolicyTypeIcons) {
    return alertPolicyTypeIcons[type as keyof typeof alertPolicyTypeIcons]
  }
  return null
}
