export type TaskStepExpansionItem = {
  id: number | string
  events?: readonly unknown[]
}

function isExpandableStep(step: TaskStepExpansionItem) {
  return (step.events?.length || 0) > 0
}

export function hasExpandableTaskStep(steps: readonly TaskStepExpansionItem[]) {
  return steps.some(isExpandableStep)
}

export function hasExpandedTaskStep(
  steps: readonly TaskStepExpansionItem[],
  isExpanded: (stepId: number | string) => boolean,
) {
  return steps.some((step) => isExpandableStep(step) && isExpanded(step.id))
}
