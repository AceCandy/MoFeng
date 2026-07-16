import { readFileSync } from 'node:fs'
import { dirname, resolve } from 'node:path'

const MAIN_CSS = 'src/assets/main.css'

/**
 * 读取 main.css 入口并递归内联相对 @import 的 partial 文件，返回并集文本
 * （@import 语句被 partial 内容替换）。
 *
 * 用于 UI 审计断言覆盖所有按域拆出的 partial，避免「不含」禁令断言读 main.css
 * 残壳而假绿（审计红线静默失效）。非相对 @import（如 'tailwindcss'）不内联，
 * 保留原文交由 Tailwind/Lightning CSS 处理。
 */
const readCssWithImports = (absPath: string, seen: Set<string>): string => {
  if (seen.has(absPath)) return ''
  seen.add(absPath)
  const content = readFileSync(absPath, 'utf8')
  const importRe = /@import\s+(['"])(\.{1,2}\/[^'"]+\.css)\1\s*;/g
  const parts: string[] = []
  let last = 0
  let m: RegExpExecArray | null
  while ((m = importRe.exec(content))) {
    parts.push(content.slice(last, m.index))
    parts.push(readCssWithImports(resolve(dirname(absPath), m[2]), seen))
    last = m.index + m[0].length
  }
  parts.push(content.slice(last))
  return parts.join('\n')
}

export const readGlobalCss = (): string =>
  readCssWithImports(resolve(process.cwd(), MAIN_CSS), new Set())
