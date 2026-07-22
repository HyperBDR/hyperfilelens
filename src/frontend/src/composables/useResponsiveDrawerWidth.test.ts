import { describe, expect, it } from 'vitest'
import { computeResponsiveDrawerWidth } from './useResponsiveDrawerWidth'

describe('computeResponsiveDrawerWidth', () => {
  it('keeps phone drawers inside the visible viewport', () => {
    expect(computeResponsiveDrawerWidth(1, 375)).toBe(359)
    expect(computeResponsiveDrawerWidth(2, 390)).toBe(374)
  })

  it('uses a comfortable tablet gutter for nested drawers', () => {
    expect(computeResponsiveDrawerWidth(1, 768)).toBe(736)
    expect(computeResponsiveDrawerWidth(2, 1023)).toBe(991)
  })

  it('preserves the desktop drawer hierarchy', () => {
    expect(computeResponsiveDrawerWidth(1, 1280)).toBe(922)
    expect(computeResponsiveDrawerWidth(2, 1280)).toBe(717)
    expect(computeResponsiveDrawerWidth(3, 1280)).toBe(589)
  })
})
