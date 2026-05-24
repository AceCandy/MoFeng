import { readdir, readFile } from 'node:fs/promises'
import { resolve } from 'node:path'
import process from 'node:process'
import { gzipSync } from 'node:zlib'

const distDir = resolve(process.cwd(), 'dist')
const distAssetsDir = resolve(process.cwd(), 'dist/assets')
const manifestPath = resolve(distDir, '.vite/manifest.json')

const parseNumber = (rawValue, fallbackValue) => {
  const parsed = Number(rawValue)
  return Number.isFinite(parsed) && parsed > 0 ? parsed : fallbackValue
}

const maxBudgets = {
  maxJsAssetGzipKB: parseNumber(process.env.BUNDLE_BUDGET_MAX_JS_GZIP_KB, 60),
  maxCssAssetGzipKB: parseNumber(process.env.BUNDLE_BUDGET_MAX_CSS_GZIP_KB, 20),
  maxJsTotalGzipKB: parseNumber(process.env.BUNDLE_BUDGET_MAX_JS_TOTAL_GZIP_KB, 480),
  maxCssTotalGzipKB: parseNumber(process.env.BUNDLE_BUDGET_MAX_CSS_TOTAL_GZIP_KB, 90),
}

const warnBudgets = {
  warnJsAssetGzipKB: parseNumber(
    process.env.BUNDLE_BUDGET_WARN_JS_GZIP_KB,
    maxBudgets.maxJsAssetGzipKB,
  ),
  warnCssAssetGzipKB: parseNumber(
    process.env.BUNDLE_BUDGET_WARN_CSS_GZIP_KB,
    maxBudgets.maxCssAssetGzipKB,
  ),
  warnJsTotalGzipKB: parseNumber(
    process.env.BUNDLE_BUDGET_WARN_JS_TOTAL_GZIP_KB,
    maxBudgets.maxJsTotalGzipKB,
  ),
  warnCssTotalGzipKB: parseNumber(
    process.env.BUNDLE_BUDGET_WARN_CSS_TOTAL_GZIP_KB,
    maxBudgets.maxCssTotalGzipKB,
  ),
}

const toKB = (bytes) => bytes / 1024
const formatKB = (bytes) => `${toKB(bytes).toFixed(2)} KB`

const ensureAssetsExist = async () => {
  try {
    return await readdir(distAssetsDir)
  } catch (error) {
    throw new Error(`未找到构建产物目录：${distAssetsDir}。请先执行 npm run build-only。`)
  }
}

const readManifestAssetFiles = async () => {
  try {
    const manifest = JSON.parse(await readFile(manifestPath, 'utf8'))
    const files = new Set()

    for (const entry of Object.values(manifest)) {
      if (!entry || typeof entry !== 'object') continue

      if (typeof entry.file === 'string') {
        files.add(entry.file)
      }

      for (const key of ['css', 'assets']) {
        if (!Array.isArray(entry[key])) continue
        for (const fileName of entry[key]) {
          if (typeof fileName === 'string') {
            files.add(fileName)
          }
        }
      }
    }

    return [...files].filter((fileName) => /\.(js|css)$/u.test(fileName))
  } catch {
    return null
  }
}

// 构建目录可能保留旧 hash 产物；优先使用 Vite manifest 只统计本次构建实际产出的资源。
const manifestFiles = await readManifestAssetFiles()
const files = manifestFiles ?? (await ensureAssetsExist())
  .filter((fileName) => /\.(js|css)$/u.test(fileName))
  .map((fileName) => `assets/${fileName}`)

if (files.length === 0) {
  throw new Error(`在 ${distAssetsDir} 未找到 JS/CSS 构建产物。`)
}

const assets = await Promise.all(
  files.map(async (fileName) => {
    const fullPath = resolve(distDir, fileName)
    const content = await readFile(fullPath)
    return {
      fileName,
      isJs: fileName.endsWith('.js'),
      isCss: fileName.endsWith('.css'),
      gzipSize: gzipSync(content, { level: 9 }).length,
    }
  }),
)

const jsAssets = assets.filter((asset) => asset.isJs)
const cssAssets = assets.filter((asset) => asset.isCss)

const totalJsGzip = jsAssets.reduce((sum, asset) => sum + asset.gzipSize, 0)
const totalCssGzip = cssAssets.reduce((sum, asset) => sum + asset.gzipSize, 0)

const failures = []

for (const asset of jsAssets) {
  if (toKB(asset.gzipSize) > maxBudgets.maxJsAssetGzipKB) {
    failures.push(
      `[JS 单文件超限] ${asset.fileName} = ${formatKB(asset.gzipSize)} > ${maxBudgets.maxJsAssetGzipKB} KB`,
    )
  }
}

for (const asset of cssAssets) {
  if (toKB(asset.gzipSize) > maxBudgets.maxCssAssetGzipKB) {
    failures.push(
      `[CSS 单文件超限] ${asset.fileName} = ${formatKB(asset.gzipSize)} > ${maxBudgets.maxCssAssetGzipKB} KB`,
    )
  }
}

if (toKB(totalJsGzip) > maxBudgets.maxJsTotalGzipKB) {
  failures.push(
    `[JS 总量超限] ${formatKB(totalJsGzip)} > ${maxBudgets.maxJsTotalGzipKB} KB`,
  )
}

if (toKB(totalCssGzip) > maxBudgets.maxCssTotalGzipKB) {
  failures.push(
    `[CSS 总量超限] ${formatKB(totalCssGzip)} > ${maxBudgets.maxCssTotalGzipKB} KB`,
  )
}

const topHeavyAssets = [...assets]
  .sort((left, right) => right.gzipSize - left.gzipSize)
  .slice(0, 8)

console.log('[bundle-budget] gzip 汇总')
console.log(
  `- JS: ${formatKB(totalJsGzip)} / ${maxBudgets.maxJsTotalGzipKB} KB`,
)
console.log(
  `- CSS: ${formatKB(totalCssGzip)} / ${maxBudgets.maxCssTotalGzipKB} KB`,
)
console.log('[bundle-budget] Top 8 体积文件')
for (const asset of topHeavyAssets) {
  console.log(`- ${asset.fileName}: ${formatKB(asset.gzipSize)}`)
}

const warnings = []

for (const asset of jsAssets) {
  if (toKB(asset.gzipSize) > warnBudgets.warnJsAssetGzipKB && toKB(asset.gzipSize) <= maxBudgets.maxJsAssetGzipKB) {
    warnings.push(
      `[JS 单文件预警] ${asset.fileName} = ${formatKB(asset.gzipSize)} > ${warnBudgets.warnJsAssetGzipKB} KB`,
    )
  }
}

for (const asset of cssAssets) {
  if (toKB(asset.gzipSize) > warnBudgets.warnCssAssetGzipKB && toKB(asset.gzipSize) <= maxBudgets.maxCssAssetGzipKB) {
    warnings.push(
      `[CSS 单文件预警] ${asset.fileName} = ${formatKB(asset.gzipSize)} > ${warnBudgets.warnCssAssetGzipKB} KB`,
    )
  }
}

if (toKB(totalJsGzip) > warnBudgets.warnJsTotalGzipKB && toKB(totalJsGzip) <= maxBudgets.maxJsTotalGzipKB) {
  warnings.push(
    `[JS 总量预警] ${formatKB(totalJsGzip)} > ${warnBudgets.warnJsTotalGzipKB} KB`,
  )
}

if (toKB(totalCssGzip) > warnBudgets.warnCssTotalGzipKB && toKB(totalCssGzip) <= maxBudgets.maxCssTotalGzipKB) {
  warnings.push(
    `[CSS 总量预警] ${formatKB(totalCssGzip)} > ${warnBudgets.warnCssTotalGzipKB} KB`,
  )
}

if (warnings.length > 0) {
  console.warn('[bundle-budget] 预警提示：')
  for (const warning of warnings) {
    console.warn(`- ${warning}`)
  }
}

if (failures.length > 0) {
  console.error('[bundle-budget] 预算校验失败：')
  for (const failure of failures) {
    console.error(`- ${failure}`)
  }
  process.exit(1)
}

console.log('[bundle-budget] 预算校验通过')
