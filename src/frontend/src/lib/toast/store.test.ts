// @vitest-environment jsdom

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import {
  closeToast,
  pauseToast,
  pushToast,
  resetToastStoreForTests,
  resumeToast,
  toastState,
} from './store'

describe('toast store', () => {
  beforeEach(() => {
    vi.useFakeTimers()
    vi.setSystemTime(new Date('2026-07-20T00:00:00Z'))
    resetToastStoreForTests()
  })

  afterEach(() => {
    resetToastStoreForTests()
    vi.useRealTimers()
  })

  it('closes a toast when its remaining time reaches zero', () => {
    pushToast({ type: 'success', message: 'Saved', duration: 1000 })
    expect(toastState.items).toHaveLength(1)

    vi.advanceTimersByTime(950)
    expect(toastState.items).toHaveLength(1)
    vi.advanceTimersByTime(50)
    expect(toastState.items).toHaveLength(0)
  })

  it('pauses and resumes from the actual remaining time', () => {
    const handler = pushToast({ type: 'error', message: 'Failed', duration: 1000 })
    const id = toastState.items[0]?.id
    expect(id).toBeTruthy()

    vi.advanceTimersByTime(400)
    pauseToast(id!)
    const remaining = toastState.items[0]?.remainingMs
    expect(remaining).toBe(600)

    vi.advanceTimersByTime(2000)
    expect(toastState.items[0]?.remainingMs).toBe(600)
    resumeToast(id!)
    vi.advanceTimersByTime(550)
    expect(toastState.items).toHaveLength(1)
    vi.advanceTimersByTime(50)
    expect(toastState.items).toHaveLength(0)

    handler.close()
  })

  it('merges the same dedupe key, counts it, and resets its duration', () => {
    pushToast({ type: 'warning', message: 'Still running', dedupeKey: 'task:1', duration: 1000 })
    vi.advanceTimersByTime(700)
    pushToast({ type: 'warning', message: 'Still running', dedupeKey: 'task:1', duration: 1000 })

    expect(toastState.items).toHaveLength(1)
    expect(toastState.items[0]?.repeatCount).toBe(2)
    expect(toastState.items[0]?.remainingMs).toBe(1000)
    vi.advanceTimersByTime(950)
    expect(toastState.items).toHaveLength(1)
  })

  it('does not merge different resources', () => {
    pushToast({ type: 'success', message: 'Copied', dedupeKey: 'copy:task-1' })
    pushToast({ type: 'success', message: 'Copied', dedupeKey: 'copy:task-2' })
    expect(toastState.items).toHaveLength(2)
  })

  it('limits the visible stack and prefers removing low-priority messages', () => {
    pushToast({ type: 'error', message: 'Error 1', dedupeKey: 'e1' })
    pushToast({ type: 'success', message: 'Success', dedupeKey: 's1' })
    pushToast({ type: 'warning', message: 'Warning', dedupeKey: 'w1' })
    pushToast({ type: 'error', message: 'Error 2', dedupeKey: 'e2' })
    pushToast({ type: 'info', message: 'Newest', dedupeKey: 'i1' })

    expect(toastState.items).toHaveLength(4)
    expect(toastState.items.some((item) => item.dedupeKey === 's1')).toBe(false)
    expect(toastState.items.some((item) => item.dedupeKey === 'e1')).toBe(true)
  })

  it('runs the close callback only when the toast closes', () => {
    const onClose = vi.fn()
    pushToast({ type: 'info', message: 'Info', onClose })
    const id = toastState.items[0]!.id
    expect(onClose).not.toHaveBeenCalled()
    closeToast(id)
    expect(onClose).toHaveBeenCalledTimes(1)
  })
})
