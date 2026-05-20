import { describe, expect, it } from 'vitest'

import { buildShellNavigation } from '../shellNavigation'

describe('buildShellNavigation', () => {
  it('returns the author navigation entries in primary order', () => {
    const nav = buildShellNavigation(false)

    expect(nav.sidebarItems.map((item) => item.key)).toEqual([
      'workspace',
      'inspiration',
      'settings',
    ])
    expect(nav.mobileTabs.map((item) => item.key)).toEqual([
      'workspace',
      'inspiration',
      'settings',
    ])
  })

  it('adds admin navigation for admin users', () => {
    const nav = buildShellNavigation(true)

    expect(nav.drawerItems.some((item) => item.key === 'admin')).toBe(true)
    expect(nav.mobileTabs.some((item) => item.key === 'admin')).toBe(true)
  })

  it('keeps workspace active for project detail routes', () => {
    const nav = buildShellNavigation(false)
    const workspace = nav.drawerItems.find((item) => item.key === 'workspace')

    expect(workspace?.match('/projects/123')).toBe(true)
    expect(workspace?.match('/settings')).toBe(false)
  })
})
