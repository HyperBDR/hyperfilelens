import { Layers, Monitor, Share2 } from 'lucide-vue-next'
import type { Component } from 'vue'

export type BackupSourceType = 'host' | 'nas'

export const sourceHostIcon = Monitor

export const sourceNasIcon = Share2

export const backupFlowSourceStepIcon = Layers

export function backupSourceTypeIcon(sourceType: BackupSourceType): Component {
  return sourceType === 'host' ? sourceHostIcon : sourceNasIcon
}

export function backupSourceTypeIconClass(sourceType: BackupSourceType): string {
  return sourceType === 'host' ? 'text-slate-500' : 'text-emerald-500'
}
