import type { LensChatMessage } from '../../../lib/lensApi'

export type CopilotDisplayMessage = {
  id: string
  role: 'user' | 'assistant'
  text?: string
  starterChips?: boolean
  isError?: boolean
  createdAt?: string
  runId?: string
  thinking?: LensChatMessage['thinking']
}
