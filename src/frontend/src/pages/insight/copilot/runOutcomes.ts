import type { LensCopilotRunOutcome } from '../../../lib/lensApi'
import type { CopilotDisplayMessage } from './types'

export function appendRunOutcomeMessages(
  messages: CopilotDisplayMessage[],
  outcomes: LensCopilotRunOutcome[],
): CopilotDisplayMessage[] {
  const assistantRuns = new Set(
    messages
      .filter((message) => message.role === 'assistant' && message.runId)
      .map((message) => message.runId as string),
  )
  const outcomesByRun = new Map(outcomes.map((outcome) => [outcome.run_uuid, outcome]))
  const merged: CopilotDisplayMessage[] = []
  for (const message of messages) {
    merged.push(message)
    if (message.role !== 'user' || !message.runId || assistantRuns.has(message.runId)) {
      continue
    }
    const outcome = outcomesByRun.get(message.runId)
    if (!outcome) continue
    merged.push({
      id: `run-outcome-${outcome.run_uuid}`,
      role: 'assistant',
      text: outcome.message,
      isError: true,
      createdAt: outcome.finished_at || message.createdAt,
      runId: outcome.run_uuid,
    })
  }
  return merged
}
