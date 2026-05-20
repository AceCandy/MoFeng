import { readdir, readFile } from 'node:fs/promises'
import { resolve } from 'node:path'
import process from 'node:process'
import { gzipSync } from 'node:zlib'

const distAssetsDir = resolve(process.cwd(), 'dist/assets')

const parseNumber = (rawValue, fallbackValue) => {
  const parsed = Number(rawValue)
  return Number.isFinite(parsed) && parsed > 0 ? parsed : fallbackValue
}

const budgets = {
  maxJsAssetGzipKB: parseNumber(process.env.BUNDLE_BUDGET_MAX_JS_GZIP_KB, 60),
  maxCssAssetGzipKB: parseNumber(process.env.BUNDLE_BUDGET_MAX_CSS_GZIP_KB, 20),
  maxJsTotalGzipKB: parseNumber(process.env.BUNDLE_BUDGET_MAX_JS_TOTAL_GZIP_KB, 480),
  maxCssTotalGzipKB: parseNumber(process.env.BUNDLE_BUDGET_MAX_CSS_TOTAL_GZIP_KB, 90),
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

const files = (await ensureAssetsExist()).filter((fileName) =>
  /\.(js|css)$/u.test(fileName),
)

if (files.length === 0) {
  throw new Error(`在 ${distAssetsDir} 未找到 JS/CSS 构建产物。`)
}

const assets = await Promise.all(
  files.map(async (fileName) => {
    const fullPath = resolve(distAssetsDir, fileName)
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
  if (toKB(asset.gzipSize) > budgets.maxJsAssetGzipKB) {
    failures.push(
      `[JS 单文件超限] ${asset.fileName} = ${formatKB(asset.gzipSize)} > ${budgets.maxJsAssetGzipKB} KB`,
    )
  }
}

for (const asset of cssAssets) {
  if (toKB(asset.gzipSize) > budgets.maxCssAssetGzipKB) {
    failures.push(
      `[CSS 单文件超限] ${asset.fileName} = ${formatKB(asset.gzipSize)} > ${budgets.maxCssAssetGzipKB} KB`,
    )
  }
}

if (toKB(totalJsGzip) > budgets.maxJsTotalGzipKB) {
  failures.push(
    `[JS 总量超限] ${formatKB(totalJsGzip)} > ${budgets.maxJsTotalGzipKB} KB`,
  )
}

if (toKB(totalCssGzip) > budgets.maxCssTotalGzipKB) {
  failures.push(
    `[CSS 总量超限] ${formatKB(totalCssGzip)} > ${budgets.maxCssTotalGzipKB} KB`,
  )
}

const topHeavyAssets = [...assets]
  .sort((left, right) => right.gzipSize - left.gzipSize)
  .slice(0, 8)

console.log('[bundle-budget] gzip 汇总')
console.log(
  `- JS: ${formatKB(totalJsGzip)} / ${budgets.maxJsTotalGzipKB} KB`,
)
console.log(
  `- CSS: ${formatKB(totalCssGzip)} / ${budgets.maxCssTotalGzipKB} KB`,
)
console.log('[bundle-budget] Top 8 体积文件')
for (const asset of topHeavyAssets) {
  console.log(`- ${asset.fileName}: ${formatKB(asset.gzipSize)}`)
}

if (failures.length > 0) {
  console.error('[bundle-budget] 预算校验失败：')
  for (const failure of failures) {
    console.error(`- ${failure}`)
  }
  process.exit(1)
}

console.log('[bundle-budget] 预算校验通过')
