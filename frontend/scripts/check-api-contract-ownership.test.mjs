// AIMETA P=API契约所有权检查测试|R=验证AST拒绝结构副本|NR=不扫描产品运行时数据|E=test:api-contract-ownership|X=internal|A=node_test|D=node:test,typescript|S=none|RD=../README.ai
import assert from 'node:assert/strict'
import test from 'node:test'

import { findStructuralOwnershipViolations } from './check-api-contract-ownership.mjs'

test('rejects migrated interfaces and nested object-literal aliases', () => {
  const novelSource = `
interface Chapter { title: string }
interface UnownedLocalType { value: string }
`
  const tasksSource = `
type BackgroundTask = { id: string }
`
  const adminSource = `
type AdminNovelSummary = BaseSummary & { owner_id: number }
`

  const violations = [
    ...findStructuralOwnershipViolations(novelSource, 'src/api/novel.ts'),
    ...findStructuralOwnershipViolations(tasksSource, 'src/api/tasks.ts'),
    ...findStructuralOwnershipViolations(adminSource, 'src/api/admin.ts'),
  ]
  assert.deepEqual(
    violations.map(({ name, kind }) => ({
      name,
      kind,
    })),
    [
      { name: 'Chapter', kind: 'interface' },
      { name: 'BackgroundTask', kind: 'object type' },
      { name: 'AdminNovelSummary', kind: 'object type' },
    ],
  )
})

test('allows generated indexed aliases and canonical re-exports', () => {
  const novelSource = `
type Chapter = components['schemas']['Chapter']
type NovelProject = NovelProjectContract
`
  const adminSource = `
type SystemConfigUpsertPayload = Omit<components['schemas']['SystemConfigCreate'], 'key'>
`

  assert.deepEqual([
    ...findStructuralOwnershipViolations(novelSource, 'src/api/novel.ts'),
    ...findStructuralOwnershipViolations(adminSource, 'src/api/admin.ts'),
  ], [])
})
