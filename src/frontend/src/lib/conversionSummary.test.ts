import { describe, expect, it } from 'vitest'
import {
  conversionAllOk,
  conversionCountsLabel,
  conversionEmptyResult,
  conversionPhase,
  conversionProblemItems,
  conversionWarningsForDisplay,
  type DocumentConversion,
} from './conversionSummary'

const sample: DocumentConversion = {
  status: 'SUCCESS',
  phase: 'succeeded',
  all_ok: false,
  counts: {
    total: 4,
    candidates: 3,
    success: 1,
    failed: 1,
    skipped: 0,
    unsupported: 1,
    unchanged: 1,
  },
  items: [
    { name: 'ok.pdf', reason: 'UNCHANGED', reason_label: 'Already converted (unchanged)', is_problem: false },
    {
      name: 'scan.pdf',
      reason: 'NO_EXTRACTABLE_TEXT',
      reason_label: 'No extractable text (may be scanned or empty)',
      is_problem: true,
    },
    { name: 'notes.doc', reason: 'UNSUPPORTED_TYPE', reason_label: 'Unsupported file type', is_problem: true },
  ],
  problem_items: [
    {
      name: 'scan.pdf',
      reason: 'NO_EXTRACTABLE_TEXT',
      reason_label: 'No extractable text (may be scanned or empty)',
      is_problem: true,
    },
    { name: 'notes.doc', reason: 'UNSUPPORTED_TYPE', reason_label: 'Unsupported file type', is_problem: true },
  ],
  warnings: [],
  usable: true,
}

describe('conversionSummary', () => {
  it('formats counts label', () => {
    expect(conversionCountsLabel(sample)).toBe('2 ready · 1 failed · 1 unsupported')
  })

  it('lists problem items from API field', () => {
    expect(conversionProblemItems(sample).map((row) => row.name)).toEqual([
      'scan.pdf',
      'notes.doc',
    ])
  })

  it('does not treat in-progress conversion as all ok', () => {
    const running: DocumentConversion = {
      status: 'STARTING',
      phase: 'running',
      all_ok: false,
      counts: {
        total: 0,
        candidates: 0,
        success: 0,
        failed: 0,
        skipped: 0,
        unsupported: 0,
        unchanged: 0,
      },
      items: [],
      problem_items: [],
      warnings: [],
      usable: false,
    }
    expect(conversionPhase(running)).toBe('running')
    expect(conversionAllOk(running)).toBe(false)
    expect(conversionCountsLabel(running)).toBe('')
  })

  it('marks clean success as all ok', () => {
    const ok: DocumentConversion = {
      status: 'SUCCESS',
      phase: 'succeeded',
      all_ok: true,
      empty_result: false,
      counts: {
        total: 2,
        candidates: 2,
        success: 2,
        failed: 0,
        skipped: 0,
        unsupported: 0,
        unchanged: 0,
      },
      items: [],
      problem_items: [],
      warnings: [],
      usable: true,
    }
    expect(conversionAllOk(ok)).toBe(true)
    expect(conversionEmptyResult(ok)).toBe(false)
  })

  it('marks zero-candidate success as empty not all ok', () => {
    const empty: DocumentConversion = {
      status: 'SUCCESS',
      phase: 'succeeded',
      all_ok: false,
      empty_result: true,
      counts: {
        total: 0,
        candidates: 0,
        success: 0,
        failed: 0,
        skipped: 0,
        unsupported: 0,
        unchanged: 0,
      },
      items: [],
      problem_items: [],
      warnings: [],
      usable: false,
    }
    expect(conversionAllOk(empty)).toBe(false)
    expect(conversionEmptyResult(empty)).toBe(true)
  })

  it('does not mark failed counts without items as all ok', () => {
    const failed: DocumentConversion = {
      status: 'SUCCESS',
      phase: 'succeeded',
      all_ok: false,
      counts: {
        total: 3,
        candidates: 3,
        success: 0,
        failed: 3,
        skipped: 0,
        unsupported: 0,
        unchanged: 0,
      },
      items: [],
      problem_items: [],
      warnings: [],
      usable: false,
    }
    expect(conversionAllOk(failed)).toBe(false)
  })

  it('hides partial-failed warning when problem items are listed', () => {
    const withDup: DocumentConversion = {
      ...sample,
      warnings: [
        { code: 'CONVERSION_PARTIAL_FAILED', label: 'Some documents could not be converted' },
        { code: 'VISUAL_MODEL_NOT_CONFIGURED', label: 'Visual understanding is not configured' },
      ],
    }
    expect(conversionWarningsForDisplay(withDup).map((row) => row.code)).toEqual([
      'VISUAL_MODEL_NOT_CONFIGURED',
    ])
  })
})
