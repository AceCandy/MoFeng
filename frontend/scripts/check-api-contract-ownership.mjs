// AIMETA P=API契约所有权检查|R=阻止已迁移DTO恢复手写结构|NR=不校验运行时payload|E=tool:api-contract-ownership|X=internal|A=typescript_ast|D=typescript|S=none|RD=../README.ai
import { readdir, readFile } from 'node:fs/promises'
import { dirname, relative, resolve } from 'node:path'
import process from 'node:process'
import { fileURLToPath } from 'node:url'
import ts from 'typescript'

const frontendRoot = resolve(dirname(fileURLToPath(import.meta.url)), '..')
const apiRoot = resolve(frontendRoot, 'src/api')

const migratedTypeNamesByFile = new Map([
  ['src/api/tasks.ts', new Set([
    'BackgroundTask',
    'BackgroundTaskCursorReset',
    'BackgroundTaskEvent',
    'BackgroundTaskLogEntry',
    'BackgroundTaskSnapshot',
  ])],
  ['src/api/novel.ts', new Set([
    'Chapter',
    'ChapterGenerationTrace',
    'ChapterOutline',
    'NovelProject',
    'NovelProjectSummary',
    'NovelSectionResponse',
    'NovelSectionType',
  ])],
  ['src/api/admin.ts', new Set([
    'AdminNovelSummary',
    'AdminUser',
    'Chapter',
    'NovelProject',
    'NovelProjectSummary',
    'PromptCreatePayload',
    'PromptItem',
    'PromptUpdatePayload',
    'Statistics',
    'SystemConfig',
    'SystemConfigUpdatePayload',
    'SystemConfigUpsertPayload',
    'UpdateLog',
    'UpdateLogPayload',
    'UserCreatePayload',
    'UserUpdatePayload',
  ])],
])

const containsTypeLiteral = (node) => {
  if (ts.isTypeLiteralNode(node)) return true
  let found = false
  ts.forEachChild(node, (child) => {
    if (!found && containsTypeLiteral(child)) found = true
  })
  return found
}

export const findStructuralOwnershipViolations = (source, fileName) => {
  const migratedTypeNames = migratedTypeNamesByFile.get(fileName.replaceAll('\\', '/'))
  if (!migratedTypeNames) return []
  const sourceFile = ts.createSourceFile(
    fileName,
    source,
    ts.ScriptTarget.Latest,
    true,
    ts.ScriptKind.TS,
  )
  const violations = []

  const visit = (node) => {
    if (ts.isInterfaceDeclaration(node) && migratedTypeNames.has(node.name.text)) {
      const { line } = sourceFile.getLineAndCharacterOfPosition(node.name.getStart(sourceFile))
      violations.push({ fileName, line: line + 1, name: node.name.text, kind: 'interface' })
    } else if (
      ts.isTypeAliasDeclaration(node)
      && migratedTypeNames.has(node.name.text)
      && containsTypeLiteral(node.type)
    ) {
      const { line } = sourceFile.getLineAndCharacterOfPosition(node.name.getStart(sourceFile))
      violations.push({ fileName, line: line + 1, name: node.name.text, kind: 'object type' })
    }
    ts.forEachChild(node, visit)
  }

  visit(sourceFile)
  return violations
}

export const checkApiContractOwnership = async () => {
  const entries = await readdir(apiRoot, { withFileTypes: true })
  const files = entries
    .filter((entry) => entry.isFile() && entry.name.endsWith('.ts') && !entry.name.endsWith('.d.ts'))
    .map((entry) => resolve(apiRoot, entry.name))
    .sort()
  const violations = []

  for (const filePath of files) {
    const fileName = relative(frontendRoot, filePath)
    violations.push(...findStructuralOwnershipViolations(await readFile(filePath, 'utf8'), fileName))
  }
  return violations
}

const isMain = process.argv[1]
  && resolve(process.argv[1]) === fileURLToPath(import.meta.url)

if (isMain) {
  const violations = await checkApiContractOwnership()
  if (violations.length > 0) {
    for (const violation of violations) {
      console.error(
        `[api-contract-ownership] ${violation.fileName}:${violation.line} ${violation.name} 不得重新定义为 ${violation.kind}`,
      )
    }
    process.exitCode = 1
  } else {
    console.log('[api-contract-ownership] 已迁移 DTO 均由 generated aliases 所有')
  }
}
