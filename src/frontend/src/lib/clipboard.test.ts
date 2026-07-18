// @vitest-environment jsdom

import { afterEach, describe, expect, it, vi } from 'vitest'
import { copyTextToClipboard } from './clipboard'

describe('copyTextToClipboard', () => {
  afterEach(() => {
    vi.restoreAllMocks()
    vi.unstubAllGlobals()
  })

  it('uses the Clipboard API when it is available', async () => {
    const writeText = vi.fn().mockResolvedValue(undefined)
    vi.stubGlobal('navigator', { clipboard: { writeText } })

    await copyTextToClipboard('install command')

    expect(writeText).toHaveBeenCalledWith('install command')
  })

  it('falls back to execCommand when the Clipboard API is unavailable', async () => {
    vi.stubGlobal('navigator', {})
    const execCommand = vi.fn().mockReturnValue(true)
    Object.defineProperty(document, 'execCommand', { configurable: true, value: execCommand })

    await copyTextToClipboard('fallback command')

    expect(execCommand).toHaveBeenCalledWith('copy')
    expect(document.querySelector('textarea')).toBeNull()
  })

  it('falls back when the Clipboard API rejects the request', async () => {
    const writeText = vi.fn().mockRejectedValue(new Error('permission denied'))
    vi.stubGlobal('navigator', { clipboard: { writeText } })
    const execCommand = vi.fn().mockReturnValue(true)
    Object.defineProperty(document, 'execCommand', { configurable: true, value: execCommand })

    await copyTextToClipboard('restricted command')

    expect(writeText).toHaveBeenCalledWith('restricted command')
    expect(execCommand).toHaveBeenCalledWith('copy')
  })

  it('rejects when both copy mechanisms fail', async () => {
    vi.stubGlobal('navigator', {})
    Object.defineProperty(document, 'execCommand', {
      configurable: true,
      value: vi.fn().mockReturnValue(false),
    })

    await expect(copyTextToClipboard('command')).rejects.toThrow('Copy command failed')
    expect(document.querySelector('textarea')).toBeNull()
  })
})
