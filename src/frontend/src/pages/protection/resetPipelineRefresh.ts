/** Source ids whose Reset Backup Config finished successfully (no active/failed reset state). */
export function selectFinishedResetSourceIds(
  trackedIds: string[],
  resetStateOf: (id: string) => string,
): string[] {
  // Use global reset state only — never infer completion from the current step-3
  // page/filter membership (a still-resetting source can be off the current page).
  return trackedIds.filter((id) => !resetStateOf(id))
}

/** Terminal failed resets should stop pipeline tracking without a step-2 refresh. */
export function selectTerminalFailedResetSourceIds(
  trackedIds: string[],
  resetStateOf: (id: string) => string,
): string[] {
  return trackedIds.filter((id) => resetStateOf(id) === 'reset_failed')
}
