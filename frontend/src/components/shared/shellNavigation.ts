export type ShellNavKey = 'workspace' | 'inspiration' | 'settings' | 'admin'

export type ShellNavIcon = 'desk' | 'spark' | 'settings' | 'admin'

export interface ShellNavItem {
  key: ShellNavKey
  label: string
  mobileLabel?: string
  path: string
  icon: ShellNavIcon
  mobileTab: boolean
  adminOnly?: boolean
  match: (path: string) => boolean
}

const baseItems: ShellNavItem[] = [
  {
    key: 'workspace',
    label: '工作台',
    mobileLabel: '工作台',
    path: '/workspace',
    icon: 'desk',
    mobileTab: true,
    match: (path) =>
      path === '/workspace' ||
      path.startsWith('/projects/') ||
      path.startsWith('/detail/') ||
      path.startsWith('/novel/'),
  },
  {
    key: 'inspiration',
    label: '灵感',
    mobileLabel: '灵感',
    path: '/inspiration',
    icon: 'spark',
    mobileTab: true,
    match: (path) => path.startsWith('/inspiration'),
  },
  {
    key: 'settings',
    label: '模型设置',
    mobileLabel: '设置',
    path: '/settings',
    icon: 'settings',
    mobileTab: true,
    match: (path) => path.startsWith('/settings'),
  },
  {
    key: 'admin',
    label: '管理',
    mobileLabel: '管理',
    path: '/admin',
    icon: 'admin',
    mobileTab: true,
    adminOnly: true,
    match: (path) => path.startsWith('/admin'),
  },
]

export const buildShellNavigation = (isAdmin: boolean) => {
  const availableItems = baseItems.filter((item) => !item.adminOnly || isAdmin)

  return {
    sidebarItems: availableItems,
    mobileTabs: availableItems.filter((item) => item.mobileTab),
    drawerItems: availableItems,
  }
}
