export const desktopMin = 1200
export const tabletMin = 834
export const mobileMax = 833

export type ResponsiveTier = 'mobile' | 'tablet' | 'desktop'

export const isResponsiveTier = (value: unknown): value is ResponsiveTier =>
  value === 'mobile' || value === 'tablet' || value === 'desktop'

export const resolveResponsiveTier = (width: number): ResponsiveTier => {
  if (width >= desktopMin) {
    return 'desktop'
  }

  if (width >= tabletMin) {
    return 'tablet'
  }

  return 'mobile'
}
