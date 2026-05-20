import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

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

describe('responsive auth screens', () => {
  it('keeps auth and entry screens on the mobile breakpoint', () => {
    const loginSfc = readFileSync(resolve(process.cwd(), 'src/views/Login.vue'), 'utf-8')
    const registerSfc = readFileSync(resolve(process.cwd(), 'src/views/Register.vue'), 'utf-8')
    const workspaceEntrySfc = readFileSync(
      resolve(process.cwd(), 'src/views/WorkspaceEntry.vue'),
      'utf-8',
    )

    expect(loginSfc.includes('@media (max-width: 833px)')).toBe(true)
    expect(registerSfc.includes('@media (max-width: 833px)')).toBe(true)
    expect(workspaceEntrySfc.includes('@media (max-width: 833px)')).toBe(true)
  })
})

describe('responsive shell layout', () => {
  it('keeps app shell bottom tabs guarded by the mobile breakpoint', () => {
    const shellStyles = readFileSync(resolve(process.cwd(), 'src/assets/main.css'), 'utf-8')

    expect(shellStyles.includes('.app-shell__bottom-tabs')).toBe(true)
    expect(shellStyles.includes('@media (max-width: 833px)')).toBe(true)
  })
})
