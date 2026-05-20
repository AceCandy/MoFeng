import { describe, expect, it } from 'vitest'

import {
  desktopMin,
  isResponsiveTier,
  mobileMax,
  resolveResponsiveTier,
  tabletMin,
} from '@/constants/responsive'

describe('responsive constants', () => {
  it('exposes the expected breakpoint values', () => {
    expect(desktopMin).toBe(1200)
    expect(tabletMin).toBe(834)
    expect(mobileMax).toBe(833)
  })
})

describe('responsive helpers', () => {
  it('maps widths into ordered tiers', () => {
    expect(resolveResponsiveTier(320)).toBe('mobile')
    expect(resolveResponsiveTier(833)).toBe('mobile')
    expect(resolveResponsiveTier(834)).toBe('tablet')
    expect(resolveResponsiveTier(1199)).toBe('tablet')
    expect(resolveResponsiveTier(1200)).toBe('desktop')
  })

  it('guards valid responsive tiers', () => {
    expect(isResponsiveTier('mobile')).toBe(true)
    expect(isResponsiveTier('tablet')).toBe(true)
    expect(isResponsiveTier('desktop')).toBe(true)
    expect(isResponsiveTier('laptop')).toBe(false)
  })
})
