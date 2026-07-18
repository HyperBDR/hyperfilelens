import type { ComposerTranslation } from 'vue-i18n'
import type { DemoBackup, DemoSnapshot } from '../../../composables/useProtectionDemoStore'

export type BackupHistoryTaskStatus = 'success' | 'running' | 'failed'

export type BackupHistoryTask = {
  id: string
  backupId: string
  backupName: string
  type: string
  status: BackupHistoryTaskStatus
  startTime: string
  endTime: string
  duration: string
  trigger: string
  executor: string
  snapshotId: string | null
  detail: string
}

export type SourceSnapshotRow = {
  backupId: string
  backupName: string
  snapshot: DemoSnapshot
}

export function fmtBackupBytes(n: number) {
  if (!n || n <= 0) return '0 B'
  const u = ['B', 'KB', 'MB', 'GB', 'TB', 'PB']
  let i = 0
  let v = n
  while (v >= 1024 && i < u.length - 1) {
    v /= 1024
    i += 1
  }
  return `${v.toFixed(i >= 2 ? 1 : 0)} ${u[i]}`
}

function taskDurationText(
  t: ComposerTranslation,
  startTime: string,
  endTime: string,
) {
  const dash = t('protection.backupDetail.durationDash')
  const s = new Date(startTime).getTime()
  const e = new Date(endTime).getTime()
  if (!Number.isFinite(s) || !Number.isFinite(e) || e <= s) return dash
  const sec = Math.floor((e - s) / 1000)
  const min = Math.floor(sec / 60)
  const remSec = sec % 60
  if (min <= 0) return t('protection.backupDetail.durationSec', { n: remSec })
  return t('protection.backupDetail.durationMinSec', { m: min, s: remSec })
}

export function buildHistoryTasksForBackup(
  t: ComposerTranslation,
  backup: DemoBackup,
  hostNames: string,
): BackupHistoryTask[] {
  const dash = t('protection.backupDetail.durationDash')
  const rows: BackupHistoryTask[] = backup.snapshots.map((s, idx) => ({
    id: `task-${backup.id}-${s.id}`,
    backupId: backup.id,
    backupName: backup.name,
    type: idx === 0 ? t('protection.backupDetail.taskTypeFull') : t('protection.backupDetail.taskTypeInc'),
    status: 'success' as const,
    startTime: s.startTime,
    endTime: s.endTime,
    duration: taskDurationText(t, s.startTime, s.endTime),
    trigger: t('protection.backupDetail.triggerPolicy'),
    executor: `${t('protection.backupDetail.executorPrefix')} / ${hostNames}`,
    snapshotId: s.id,
    detail: t('protection.backupDetail.taskDetailOk', {
      id: s.id,
      size: fmtBackupBytes(s.sizeBytes),
      files: s.fileCount,
      dirs: s.dirCount,
    }),
  }))
  if (backup.status === 'failed') {
    rows.unshift({
      id: `task-${backup.id}-failed-retry`,
      backupId: backup.id,
      backupName: backup.name,
      type: t('protection.backupDetail.taskTypeRetry'),
      status: 'failed',
      startTime: backup.latestSnapshotAt ?? dash,
      endTime: dash,
      duration: t('protection.backupDetail.durationFailedMid'),
      trigger: t('protection.backupDetail.triggerManual'),
      executor: `${t('protection.backupDetail.executorOperator')} / ${hostNames}`,
      snapshotId: null,
      detail: t('protection.backupDetail.taskDetailFail'),
    })
  }
  return rows
}

export function buildSnapshotRowsForBackups(backups: DemoBackup[]): SourceSnapshotRow[] {
  const rows: SourceSnapshotRow[] = []
  for (const backup of backups) {
    for (const snapshot of backup.snapshots) {
      rows.push({ backupId: backup.id, backupName: backup.name, snapshot })
    }
  }
  return rows.sort(
    (a, b) => new Date(b.snapshot.endTime).getTime() - new Date(a.snapshot.endTime).getTime(),
  )
}

export function buildHistoryTasksForBackups(
  t: ComposerTranslation,
  backups: DemoBackup[],
  getHostNames: (backup: DemoBackup) => string,
): BackupHistoryTask[] {
  const all: BackupHistoryTask[] = []
  for (const backup of backups) {
    all.push(...buildHistoryTasksForBackup(t, backup, getHostNames(backup)))
  }
  return all.sort((a, b) => new Date(b.startTime).getTime() - new Date(a.startTime).getTime())
}
