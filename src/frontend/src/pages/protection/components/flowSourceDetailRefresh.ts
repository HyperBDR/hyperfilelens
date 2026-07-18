export type RefreshableFlowSourceDetailTab = 'overview' | 'snapshots' | 'restoreRecords' | 'tasks'

export type FlowSourceDetailTabLoaders = Record<RefreshableFlowSourceDetailTab, () => void | Promise<void>>

/** Run the active tab loader every time the tab is activated; callers own request cancellation. */
export function refreshFlowSourceDetailTab(
  tab: RefreshableFlowSourceDetailTab,
  loaders: FlowSourceDetailTabLoaders,
) {
  return loaders[tab]()
}
