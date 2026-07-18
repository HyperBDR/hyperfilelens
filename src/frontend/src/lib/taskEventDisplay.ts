const taskEventMessageKeys: Record<string, string> = {
  'task created': 'ops.task.eventMessage.taskCreated',
  'task started': 'ops.task.eventMessage.taskStarted',
  'task cancelled': 'ops.task.eventMessage.taskCancelled',
  'task queued for retry': 'ops.task.eventMessage.taskQueuedForRetry',
  'logical snapshot created': 'ops.task.eventMessage.logicalSnapshotCreated',
  'starting directory snapshot': 'ops.task.eventMessage.startingDirectorySnapshot',
  'dispatching directory backup to agent': 'ops.task.eventMessage.dispatchingDirectoryBackup',
  'directory backup agent task finished': 'ops.task.eventMessage.directoryBackupFinished',
  'directory snapshot created': 'ops.task.eventMessage.directorySnapshotCreated',
  'backup progress stalled': 'ops.task.eventMessage.backupProgressStalled',
  'late backup result ignored due to newer backup task': 'ops.task.eventMessage.lateBackupResultIgnored',
  'late backup result adopted': 'ops.task.eventMessage.lateBackupResultAdopted',
  'directory backup failed': 'ops.task.eventMessage.directoryBackupFailed',
  'directory backup cancelled': 'ops.task.eventMessage.directoryBackupCancelled',
  'resuming directory backup agent task': 'ops.task.eventMessage.resumingDirectoryBackup',
  'proxy repository server started': 'ops.task.eventMessage.proxyRepositoryServerStarted',
  'source repository connectivity probe started': 'ops.task.eventMessage.sourceRepositoryConnectivityProbeStarted',
  'repository usage refresh queued': 'ops.task.eventMessage.repositoryUsageRefreshQueued',
  'repository usage refresh queue failed': 'ops.task.eventMessage.repositoryUsageRefreshQueueFailed',
  'backup finished with failed directories': 'ops.task.eventMessage.backupFinishedWithFailedDirectories',
  'backup configuration reset failed': 'ops.task.eventMessage.backupConfigurationResetFailed',
  'deleting kopia snapshots for reset': 'ops.task.eventMessage.deletingKopiaSnapshotsForReset',
  'kopia snapshot already absent; continuing reset cleanup': 'ops.task.eventMessage.kopiaSnapshotAlreadyAbsent',
  'deleting physical kopia snapshot': 'ops.task.eventMessage.deletingPhysicalKopiaSnapshot',
  'physical snapshot delete failed': 'ops.task.eventMessage.physicalSnapshotDeleteFailed',
  'starting snapshot download': 'ops.task.eventMessage.startingSnapshotDownload',
  'snapshot download artifact is ready': 'ops.task.eventMessage.snapshotDownloadArtifactReady',
  'snapshot download exceeds the size limit': 'ops.task.eventMessage.snapshotDownloadSizeExceeded',
  'restore item dispatched to agent': 'ops.task.eventMessage.restoreItemDispatchedToAgent',
  'restore dispatch failed': 'ops.task.eventMessage.restoreDispatchFailed',
  'restore repository server started': 'ops.task.eventMessage.restoreRepositoryServerStarted',
  'restore repository server failed': 'ops.task.eventMessage.restoreRepositoryServerFailed',
  'restore stopped by user': 'ops.task.eventMessage.restoreStoppedByUser',
  'restore finished with failed items': 'ops.task.eventMessage.restoreFinishedWithFailedItems',
  'restore finished successfully': 'ops.task.eventMessage.restoreFinishedSuccessfully',
  'source unregister prepared': 'ops.task.eventMessage.sourceUnregisterPrepared',
  'cleaning direct nas physical repositories': 'ops.task.eventMessage.cleaningDirectNasPhysicalRepositories',
  'direct nas repository cleanup completed': 'ops.task.eventMessage.directNasRepositoryCleanupCompleted',
  'resetting backup configuration data': 'ops.task.eventMessage.resettingBackupConfigurationData',
  'backup configuration data reset': 'ops.task.eventMessage.backupConfigurationDataReset',
  'cleaning up source endpoints': 'ops.task.eventMessage.cleaningUpSourceEndpoints',
  'source endpoint cleanup dispatched': 'ops.task.eventMessage.sourceEndpointCleanupDispatched',
  'source unregister finalized': 'ops.task.eventMessage.sourceUnregisterFinalized',
  'task finished with status success': 'ops.task.eventMessage.taskFinishedSuccess',
  'task finished with status failed': 'ops.task.eventMessage.taskFinishedFailed',
  'task finished with status cancelled': 'ops.task.eventMessage.taskFinishedCancelled',
  'task finished with status timeout': 'ops.task.eventMessage.taskFinishedTimeout',
}

export function taskEventMessageKey(message?: unknown): string | null {
  const normalized = String(message || '').trim().toLowerCase()
  if (!normalized) return null
  return taskEventMessageKeys[normalized]
    || (normalized.includes('task finished') ? 'ops.task.eventMessage.taskFinished' : null)
}

export function parseTaskStepStatusEvent(message?: unknown): { step: string; status: string } | null {
  const match = /^step ([a-z0-9_]+) ([a-z_]+)$/i.exec(String(message || '').trim())
  if (!match) return null
  return { step: match[1], status: match[2].toLowerCase() }
}
