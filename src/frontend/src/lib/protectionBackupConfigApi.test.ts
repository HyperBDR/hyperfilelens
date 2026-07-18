// @vitest-environment jsdom

import { describe, expect, it } from 'vitest'
import {
  InvalidCompressionLevelError,
  parseCompressionLevel,
} from './protectionBackupConfigApi'

describe('parseCompressionLevel', () => {
  it.each(['none', 'balanced', 'high'] as const)('accepts %s', (value) => {
    expect(parseCompressionLevel(value)).toBe(value)
  })

  it.each(['', 'best', 'zstd', null, undefined])('rejects unexpected value %s', (value) => {
    expect(() => parseCompressionLevel(value)).toThrow(InvalidCompressionLevelError)
  })
})
