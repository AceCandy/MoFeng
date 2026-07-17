// 版本号归一化纯函数：供 UI 层比较版本复用，避免直连 @/api
export const normalizeVersion = (rawVersion: string): string =>
  rawVersion.trim().replace(/^v(?=\d)/i, '')

export const normalizeComparableVersion = (rawVersion: string): string =>
  normalizeVersion(rawVersion)
