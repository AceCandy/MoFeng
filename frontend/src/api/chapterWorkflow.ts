// AIMETA P=章节工作流API_快照契约解码|R=current_start_command请求与运行时校验|NR=不持有服务端缓存或UI状态|E=api:chapter-workflow|X=internal|A=ChapterWorkflowAPI|D=fetch,openapi|S=net|RD=./README.ai
import { API_BASE_URL, API_PREFIX } from './base'
import { authJson } from './client'
import type { components } from './generated/schema'
import type { HttpRequestOptions } from './http'

export type ChapterWorkflowCommandConflictDetail =
  components['schemas']['ChapterWorkflowCommandConflictDetail']
export type ChapterWorkflowCommandConflictResponse =
  components['schemas']['ChapterWorkflowCommandConflictResponse']
export type ChapterWorkflowCommandEnvelope =
  components['schemas']['ChapterWorkflowCommandEnvelope']
export type ChapterWorkflowCommandResponse =
  components['schemas']['ChapterWorkflowCommandResponse']
export type ChapterWorkflowConnection = components['schemas']['ChapterWorkflowConnection']
export type ChapterWorkflowSnapshot = components['schemas']['ChapterWorkflowSnapshot']
export type ChapterWorkflowStartRequest = components['schemas']['ChapterWorkflowStartRequest']
export type ChapterWorkflowStartResponse = components['schemas']['ChapterWorkflowStartResponse']

export type ChapterWorkflowCommand = ChapterWorkflowCommandEnvelope['type']
export type ChapterWorkflowCommandStatus = ChapterWorkflowCommandResponse['status']
export type ChapterWorkflowNodeKey = ChapterWorkflowSnapshot['node_key']
export type ChapterWorkflowRootJobStatus = ChapterWorkflowSnapshot['root_job_status']
export type ChapterWorkflowStatus = ChapterWorkflowSnapshot['status']

export interface ChapterWorkflowScope {
  projectId: string
  chapterNumber: number
}

interface ChapterWorkflowSnapshotExpectation {
  scope?: ChapterWorkflowScope
  runId?: string
}

interface ChapterWorkflowCommandExpectation extends ChapterWorkflowSnapshotExpectation {
  commandId?: string
  commandType?: ChapterWorkflowCommand
}

export type ChapterWorkflowContractErrorCode =
  | 'identity_mismatch'
  | 'malformed'
  | 'scope_mismatch'
  | 'unsupported_version'

export class ChapterWorkflowContractError extends Error {
  readonly code: ChapterWorkflowContractErrorCode
  readonly reason: string

  constructor(code: ChapterWorkflowContractErrorCode, reason: string) {
    const message = code === 'unsupported_version'
      ? '章节工作流数据版本不受支持'
      : code === 'scope_mismatch' || code === 'identity_mismatch'
        ? '章节工作流数据身份不匹配'
        : '章节工作流数据格式无效'
    super(message)
    this.name = 'ChapterWorkflowContractError'
    this.code = code
    this.reason = reason
  }
}

const exactStringValues =
  <Expected extends string>() =>
  <const Values extends readonly Expected[]>(
    values: Values & ([Expected] extends [Values[number]] ? unknown : never),
  ) => values

export const CHAPTER_WORKFLOW_STATUS_VALUES = exactStringValues<ChapterWorkflowStatus>()([
  'queued',
  'running',
  'retry_wait',
  'waiting_for_selection',
  'finalizing',
  'projection_pending',
  'needs_attention',
  'successful',
  'failed',
  'cancelled',
  'superseded',
] as const)

export const CHAPTER_WORKFLOW_ROOT_JOB_STATUS_VALUES =
  exactStringValues<ChapterWorkflowRootJobStatus>()([
    'queued',
    'running',
    'retry_wait',
    'waiting',
    'succeeded',
    'failed',
    'dead_letter',
    'needs_attention',
    'cancelled',
  ] as const)

export const CHAPTER_WORKFLOW_NODE_KEY_VALUES = exactStringValues<ChapterWorkflowNodeKey>()([
  'freeze_base_context',
  'retrieve_context',
  'plan_chapter',
  'generate_candidate_1',
  'generate_candidate_2',
  'review_candidates',
  'refine_candidate',
  'enhance_content',
  'repair_consistency',
  'optimize_style',
  'enrich_content',
  'compress_candidate',
  'persist_drafts',
  'wait_for_selection',
  'finalize_revision',
  'wait_for_projections',
  'reconcile_projections',
  'successful',
  'failed',
  'cancelled',
  'superseded',
] as const)

export const CHAPTER_WORKFLOW_COMMAND_VALUES = exactStringValues<ChapterWorkflowCommand>()([
  'select',
  'retry',
  'retry_external',
  'retry_projection',
  'cancel',
] as const)

export const CHAPTER_WORKFLOW_COMMAND_STATUS_VALUES =
  exactStringValues<ChapterWorkflowCommandStatus>()([
    'pending',
    'applied',
    'rejected',
  ] as const)

const WORKFLOW_BASE = `${API_BASE_URL}${API_PREFIX}/writer/chapter-workflows`
const CANONICAL_UUID_PATTERN =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/

const isRecord = (value: unknown): value is Record<string, unknown> =>
  typeof value === 'object' && value !== null && !Array.isArray(value)

const isIntegerInRange = (value: unknown, min: number, max = Number.MAX_SAFE_INTEGER) =>
  typeof value === 'number' && Number.isInteger(value) && value >= min && value <= max

const isStringInRange = (value: unknown, min: number, max: number) =>
  typeof value === 'string' && value.length >= min && value.length <= max

const isOptionalNullableString = (
  value: unknown,
  max: number,
  min = 0,
) => value === undefined || value === null || isStringInRange(value, min, max)

const isCanonicalUuid = (value: unknown): value is string =>
  typeof value === 'string' && CANONICAL_UUID_PATTERN.test(value)

const isOptionalNullableCanonicalUuid = (value: unknown) =>
  value === undefined || value === null || isCanonicalUuid(value)

const isStringValue = <Value extends string>(
  value: unknown,
  values: readonly Value[],
): value is Value => typeof value === 'string' && (values as readonly string[]).includes(value)

const failContract = (
  code: ChapterWorkflowContractErrorCode,
  reason: string,
): never => {
  throw new ChapterWorkflowContractError(code, reason)
}

const requireRecord = (payload: unknown, reason: string): Record<string, unknown> => {
  if (!isRecord(payload)) {
    throw new ChapterWorkflowContractError('malformed', reason)
  }
  return payload
}

const requireSupportedVersions = (value: Record<string, unknown>) => {
  const versionFields = [
    'workflow_version',
    'state_schema_version',
    'context_schema_version',
  ] as const
  for (const field of versionFields) {
    if (!isIntegerInRange(value[field], 0)) {
      failContract('malformed', field)
    }
    if (value[field] !== 1) {
      failContract('unsupported_version', field)
    }
  }
}

export const decodeChapterWorkflowSnapshot = (
  payload: unknown,
  expectation: ChapterWorkflowSnapshotExpectation = {},
): ChapterWorkflowSnapshot => {
  const value = requireRecord(payload, 'snapshot')
  requireSupportedVersions(value)
  if (
    !isCanonicalUuid(value.run_id)
    || !isCanonicalUuid(value.root_job_id)
    || !isStringInRange(value.project_id, 1, 36)
    || !isIntegerInRange(value.chapter_id, 1)
    || !isIntegerInRange(value.chapter_number, 1)
    || !isIntegerInRange(value.base_revision, 0)
    || !isIntegerInRange(value.current_chapter_revision, 0)
    || !isStringValue(value.status, CHAPTER_WORKFLOW_STATUS_VALUES)
    || !isStringValue(value.root_job_status, CHAPTER_WORKFLOW_ROOT_JOB_STATUS_VALUES)
    || !isStringValue(value.node_key, CHAPTER_WORKFLOW_NODE_KEY_VALUES)
    || !isOptionalNullableString(value.checkpoint_id, 512)
    || !isIntegerInRange(value.progress, 0, 100)
    || !isIntegerInRange(value.row_revision, 0)
    || typeof value.is_active !== 'boolean'
    || !isOptionalNullableCanonicalUuid(value.successor_run_id)
    || !isOptionalNullableString(value.error_category, 64)
    || !isOptionalNullableString(value.public_error, 512)
    || !Array.isArray(value.allowed_commands)
    || !value.allowed_commands.every((command) =>
      isStringValue(command, CHAPTER_WORKFLOW_COMMAND_VALUES))
    || !Object.prototype.hasOwnProperty.call(value, 'retry_activity_key')
    || !(value.retry_activity_key === null
      || isStringInRange(value.retry_activity_key, 1, 128))
    || !isIntegerInRange(value.resume_cursor, 0)
  ) {
    failContract('malformed', 'snapshot')
  }
  if (
    expectation.scope
    && (
      value.project_id !== expectation.scope.projectId
      || value.chapter_number !== expectation.scope.chapterNumber
    )
  ) {
    failContract('scope_mismatch', 'project_or_chapter')
  }
  if (expectation.runId && value.run_id !== expectation.runId) {
    failContract('identity_mismatch', 'run_id')
  }
  return value as ChapterWorkflowSnapshot
}

export const decodeChapterWorkflowConnection = (
  payload: unknown,
  scope: ChapterWorkflowScope,
): ChapterWorkflowConnection => {
  const value = requireRecord(payload, 'connection')
  if (!isStringInRange(value.events_url, 1, 2_048)) {
    failContract('malformed', 'connection')
  }
  return {
    events_url: value.events_url as string,
    snapshot: decodeChapterWorkflowSnapshot(value.snapshot, { scope }),
  }
}

export const decodeCurrentChapterWorkflow = (
  payload: unknown,
  scope: ChapterWorkflowScope,
): ChapterWorkflowConnection | null =>
  payload === null ? null : decodeChapterWorkflowConnection(payload, scope)

export const decodeChapterWorkflowStartResponse = (
  payload: unknown,
  scope: ChapterWorkflowScope,
): ChapterWorkflowStartResponse => {
  const value = requireRecord(payload, 'start_response')
  if (typeof value.created !== 'boolean') {
    failContract('malformed', 'start_response')
  }
  return {
    ...decodeChapterWorkflowConnection(value, scope),
    created: value.created as boolean,
  }
}

export const decodeChapterWorkflowCommandResponse = (
  payload: unknown,
  expectation: ChapterWorkflowCommandExpectation,
): ChapterWorkflowCommandResponse => {
  const value = requireRecord(payload, 'command_response')
  if (
    !isCanonicalUuid(value.command_id)
    || !isStringValue(value.type, CHAPTER_WORKFLOW_COMMAND_VALUES)
    || !isStringValue(value.status, CHAPTER_WORKFLOW_COMMAND_STATUS_VALUES)
  ) {
    failContract('malformed', 'command_response')
  }
  if (expectation.commandId && value.command_id !== expectation.commandId) {
    failContract('identity_mismatch', 'command_id')
  }
  if (expectation.commandType && value.type !== expectation.commandType) {
    failContract('identity_mismatch', 'command_type')
  }
  return {
    command_id: value.command_id as string,
    type: value.type as ChapterWorkflowCommand,
    status: value.status as ChapterWorkflowCommandStatus,
    snapshot: decodeChapterWorkflowSnapshot(value.snapshot, expectation),
  }
}

export const decodeChapterWorkflowCommandConflict = (
  payload: unknown,
  expectation: ChapterWorkflowSnapshotExpectation,
): ChapterWorkflowCommandConflictResponse => {
  const value = requireRecord(payload, 'command_conflict')
  const detail = requireRecord(value.detail, 'command_conflict')
  if (!isStringInRange(detail.reason_code, 1, 64)) {
    failContract('malformed', 'command_conflict_reason')
  }
  return {
    detail: {
      reason_code: detail.reason_code as string,
      current_snapshot: decodeChapterWorkflowSnapshot(
        detail.current_snapshot,
        expectation,
      ),
    },
  }
}

const request = (url: string, options: HttpRequestOptions = {}) =>
  authJson<unknown>(url, {
    ...options,
    fallbackErrorMessage: '章节工作流接口请求失败',
  })

export class ChapterWorkflowAPI {
  static async getCurrent(
    scope: ChapterWorkflowScope,
    options: HttpRequestOptions = {},
  ): Promise<ChapterWorkflowConnection | null> {
    const params = new URLSearchParams({
      project_id: scope.projectId,
      chapter_number: String(scope.chapterNumber),
    })
    const payload = await request(`${WORKFLOW_BASE}/current?${params.toString()}`, options)
    return decodeCurrentChapterWorkflow(payload, scope)
  }

  static async getSnapshot(
    scope: ChapterWorkflowScope,
    runId: string,
    options: HttpRequestOptions = {},
  ): Promise<ChapterWorkflowSnapshot> {
    const payload = await request(`${WORKFLOW_BASE}/${encodeURIComponent(runId)}`, options)
    return decodeChapterWorkflowSnapshot(payload, { scope, runId })
  }

  static async start(
    input: ChapterWorkflowStartRequest,
    options: HttpRequestOptions = {},
  ): Promise<ChapterWorkflowStartResponse> {
    const payload = await request(WORKFLOW_BASE, {
      ...options,
      method: 'POST',
      body: JSON.stringify(input),
    })
    return decodeChapterWorkflowStartResponse(payload, {
      projectId: input.project_id,
      chapterNumber: input.chapter_number,
    })
  }

  static async submitCommand(
    scope: ChapterWorkflowScope,
    runId: string,
    command: ChapterWorkflowCommandEnvelope,
    options: HttpRequestOptions = {},
  ): Promise<ChapterWorkflowCommandResponse> {
    const payload = await request(
      `${WORKFLOW_BASE}/${encodeURIComponent(runId)}/commands`,
      {
        ...options,
        method: 'POST',
        body: JSON.stringify(command),
      },
    )
    return decodeChapterWorkflowCommandResponse(payload, {
      scope,
      runId,
      commandId: command.command_id,
      commandType: command.type,
    })
  }
}
