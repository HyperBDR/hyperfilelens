import { notifyError } from '../notify'
import { isAbortError } from './normalizer'
import { resolveErrorMessage, type TranslateFn } from './resolver'
import type { ErrorContext } from './types'

export function presentError(
  err: unknown,
  ctx: ErrorContext,
  t?: TranslateFn,
  fallback = 'Request failed',
): string {
  if (isAbortError(err)) return ''
  if (ctx.kind === 'background') return ''

  const message = resolveErrorMessage(err, t, fallback)
  if (!message) return ''

  if (ctx.kind === 'mutation') {
    notifyError(message)
    return message
  }

  // page-load / drawer-load / form / offline: caller renders inline UI
  return message
}
