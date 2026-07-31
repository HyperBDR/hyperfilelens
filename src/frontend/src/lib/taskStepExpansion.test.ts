import { describe, expect, it } from 'vitest'
import { hasExpandableTaskStep, hasExpandedTaskStep, type TaskStepExpansionItem } from './taskStepExpansion'

const steps: TaskStepExpansionItem[] = [
  { id: 1, events: [{ id: 1 }] },
  { id: 2, events: [{ id: 2 }] },
  { id: 3, events: [] },
]

describe('task step expansion state', () => {
  it('shows Collapse All when every expandable step is expanded', () => {
    expect(hasExpandedTaskStep(steps, () => true)).toBe(true)
  })

  it('shows Collapse All when only one expandable step is expanded', () => {
    expect(hasExpandedTaskStep(steps, (stepId) => stepId === 2)).toBe(true)
  })

  it('shows Expand All only when every expandable step is collapsed', () => {
    expect(hasExpandedTaskStep(steps, () => false)).toBe(false)
  })

  it('ignores steps without collapsible event content', () => {
    const emptySteps = [{ id: 1, events: [] }]
    expect(hasExpandableTaskStep(emptySteps)).toBe(false)
    expect(hasExpandedTaskStep(emptySteps, () => true)).toBe(false)
  })
})
