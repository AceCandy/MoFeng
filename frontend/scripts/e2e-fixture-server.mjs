// AIMETA P=章节工作流E2E确定性API与SSE服务|R=认证_项目_工作流场景与控制面|NR=不模拟生产持久化或业务执行器|E=fixture:e2e-server|X=internal|A=e2e-fixture-server|D=node:http|S=net,memory|RD=../README.ai
import { createServer } from 'node:http'

const port = Number(process.env.E2E_FIXTURE_PORT || '6181')
const host = '127.0.0.1'
const projectId = 'project-e2e'
const runA = '11111111-1111-4111-8111-111111111111'
const rootA = '22222222-2222-4222-8222-222222222222'
const runB = '44444444-4444-4444-8444-444444444444'
const rootB = '55555555-5555-4555-8555-555555555555'

const workflowClients = new Set()
const globalClients = new Set()

const baseSnapshot = (overrides = {}) => ({
  run_id: runA,
  root_job_id: rootA,
  project_id: projectId,
  chapter_id: 1,
  chapter_number: 1,
  base_revision: 0,
  current_chapter_revision: 0,
  workflow_version: 1,
  state_schema_version: 1,
  context_schema_version: 1,
  status: 'running',
  root_job_status: 'running',
  node_key: 'generate_candidates',
  checkpoint_id: 'checkpoint-e2e',
  progress: 35,
  row_revision: 1,
  is_active: true,
  successor_run_id: null,
  error_category: null,
  public_error: null,
  allowed_commands: ['cancel'],
  retry_activity_key: null,
  resume_cursor: 10,
  ...overrides,
})

const scenarioSnapshot = (scenario) => {
  if (scenario === 'current-null-start' || scenario === 'duplicate-click') return null
  if (scenario === 'waiting-refresh') {
    return baseSnapshot({
      status: 'waiting_for_selection',
      root_job_status: 'waiting',
      node_key: 'waiting_for_selection',
      progress: 70,
      row_revision: 2,
      allowed_commands: [],
    })
  }
  if (scenario === 'projection-retry') {
    return baseSnapshot({
      status: 'projection_pending',
      root_job_status: 'needs_attention',
      node_key: 'projection_pending',
      progress: 90,
      row_revision: 3,
      allowed_commands: ['retry_projection'],
    })
  }
  if (scenario === 'external-retry') {
    return baseSnapshot({
      status: 'needs_attention',
      root_job_status: 'needs_attention',
      node_key: 'failed',
      progress: 45,
      row_revision: 3,
      error_category: 'external_side_effect_unknown',
      public_error: '外部模型调用结果未知，需要确认风险后重试。',
      allowed_commands: ['retry_external'],
      retry_activity_key: 'generate-candidates:attempt-1',
    })
  }
  if (scenario === 'cancelled-restart') {
    return baseSnapshot({
      status: 'cancelled',
      root_job_status: 'cancelled',
      node_key: 'cancelled',
      progress: 15,
      row_revision: 4,
      is_active: false,
      allowed_commands: [],
    })
  }
  if (scenario === 'superseded-follow') {
    return baseSnapshot({
      status: 'superseded',
      root_job_status: 'cancelled',
      node_key: 'superseded',
      row_revision: 5,
      is_active: false,
      successor_run_id: runB,
      allowed_commands: [],
    })
  }
  if (scenario === 'stale-event') {
    return baseSnapshot({ row_revision: 4, resume_cursor: 20 })
  }
  return baseSnapshot()
}

const initialState = (scenario = 'current-null-start') => ({
  scenario,
  snapshot: scenarioSnapshot(scenario),
  candidates: [],
  stats: {
    currentRequests: 0,
    startRequests: 0,
    workflowConnections: 0,
    lastEventIds: [],
    commands: [],
    unknownRequests: [],
  },
})

let state = initialState()

const closeClients = (clients) => {
  for (const response of clients) response.end()
  clients.clear()
}

const json = (response, status, payload) => {
  const body = JSON.stringify(payload)
  response.writeHead(status, {
    'Content-Type': 'application/json; charset=utf-8',
    'Content-Length': Buffer.byteLength(body),
    'Cache-Control': 'no-store',
  })
  response.end(body)
}

const readJson = async (request) => {
  const chunks = []
  for await (const chunk of request) chunks.push(chunk)
  if (chunks.length === 0) return {}
  return JSON.parse(Buffer.concat(chunks).toString('utf8'))
}

const connection = (snapshot) => ({
  snapshot,
  events_url: `/api/tasks/events?stream_type=workflow&stream_id=${snapshot.run_id}`,
})

const projectChapter = () => ({
  chapter_number: 1,
  title: '归档室的回声',
  summary: '记录员在归档室发现了一份被覆盖的旧版本。',
  goals: '确认事实来源并完成本章。',
  content: null,
  real_summary: null,
  versions: null,
  version_selections: state.candidates,
  evaluation: null,
  generation_status: state.candidates.length > 0 ? 'selecting' : 'not_generated',
  generation_progress: null,
  generation_step: null,
  generation_step_index: null,
  generation_step_total: null,
  generation_traces: state.scenario === 'external-retry'
    ? [{
        id: 1,
        node_key: 'quality_review',
        node_label: 'AI评审',
        stage: 'version_review',
        status: 'failed',
        uses_llm: true,
        error: 'AI评审失败：外部模型返回结果不确定',
        metadata: { run_id: runA },
      }]
    : [],
  word_count: 0,
})

const project = () => ({
  id: projectId,
  user_id: 1,
  title: '回声档案',
  initial_prompt: '一名记录员追查被覆盖的事实。',
  conversation_history: [],
  blueprint: {
    title: '回声档案',
    genre: '悬疑',
    style: '克制',
    tone: '冷静',
    target_audience: '成年读者',
    one_sentence_summary: '记录员追查被覆盖的事实。',
    full_synopsis: '记录员沿着版本痕迹，确认每一次改写留下的证据。',
    world_setting: {},
    characters: [],
    relationships: [],
    chapter_outline: [{
      chapter_number: 1,
      title: '归档室的回声',
      summary: '记录员在归档室发现了一份被覆盖的旧版本。',
      goals: '确认事实来源并完成本章。',
    }],
  },
  chapters: [projectChapter()],
})

const projectSummary = () => ({
  id: projectId,
  title: '回声档案',
  genre: '悬疑',
  total_chapters: 1,
  completed_chapters: 0,
  last_edited: '2026-07-31T00:00:00Z',
})

const task = (snapshot = state.snapshot) => ({
  id: snapshot?.root_job_id ?? rootA,
  user_id: 1,
  task_type: 'chapter_workflow',
  title: '章节工作流',
  status: 'running',
  progress: snapshot?.progress ?? 0,
  project_id: projectId,
  stream_type: 'workflow',
  stream_id: snapshot?.run_id ?? runA,
  payload: null,
  result: null,
  error: null,
  created_at: '2026-07-31T00:00:00Z',
  updated_at: '2026-07-31T00:00:01Z',
  started_at: '2026-07-31T00:00:00Z',
  completed_at: null,
  log_entries: [],
})

const taskSnapshot = (scope, cursor) => ({
  schema_version: 1,
  tasks: [],
  snapshot_revision: `e2e-${cursor}`,
  resume_cursor: cursor,
  stream_type: scope?.stream_type ?? null,
  stream_id: scope?.stream_id ?? null,
})

const taskEvent = (cursor) => ({
  schema_version: 1,
  cursor,
  event_type: 'job.progressed',
  task: task(),
})

const sendSSE = (response, event, payload, cursor) => {
  if (cursor !== undefined) response.write(`id: ${cursor}\n`)
  response.write(`event: ${event}\n`)
  response.write(`data: ${JSON.stringify(payload)}\n\n`)
}

const openSSE = (request, response, clients) => {
  response.writeHead(200, {
    'Content-Type': 'text/event-stream; charset=utf-8',
    'Cache-Control': 'no-cache, no-transform',
    Connection: 'keep-alive',
    'X-Accel-Buffering': 'no',
  })
  response.flushHeaders()
  clients.add(response)
  request.on('close', () => clients.delete(response))
}

const emitWorkflowTask = (cursor) => {
  for (const response of workflowClients) sendSSE(response, 'task', taskEvent(cursor), cursor)
}

const handleControlEvent = (action) => {
  if (action === 'waiting-ready') {
    state.candidates = [{
      id: 701,
      content: '记录员展开旧纸，先核对编号，再确认覆盖时间。',
      version_label: '证据链版本',
      workflow_run_id: runA,
    }]
    state.snapshot = baseSnapshot({
      status: 'waiting_for_selection',
      root_job_status: 'waiting',
      node_key: 'waiting_for_selection',
      progress: 75,
      row_revision: 3,
      current_chapter_revision: 1,
      allowed_commands: ['select', 'cancel'],
      resume_cursor: 11,
    })
    emitWorkflowTask(11)
    return
  }
  if (action === 'stale-success') {
    state.snapshot = baseSnapshot({
      status: 'successful',
      root_job_status: 'succeeded',
      node_key: 'successful',
      progress: 100,
      row_revision: 5,
      is_active: false,
      allowed_commands: [],
      resume_cursor: 21,
    })
    emitWorkflowTask(21)
    return
  }
  if (action === 'stale-event') {
    emitWorkflowTask(20)
    return
  }
  throw new Error(`Unknown fixture event: ${action}`)
}

const handleWorkflowStream = (request, response) => {
  state.stats.workflowConnections += 1
  state.stats.lastEventIds.push(request.headers['last-event-id'] ?? null)
  openSSE(request, response, workflowClients)
  const cursor = state.snapshot?.resume_cursor ?? 0
  const scope = {
    stream_type: 'workflow',
    stream_id: state.snapshot?.run_id ?? runA,
  }
  sendSSE(response, 'snapshot', taskSnapshot(scope, cursor), cursor)

  if (state.scenario === 'disconnect-replay' && state.stats.workflowConnections === 1) {
    setTimeout(() => response.end(), 80)
    return
  }
  if (state.scenario === 'disconnect-replay' && state.stats.workflowConnections === 2) {
    state.snapshot = baseSnapshot({
      status: 'waiting_for_selection',
      root_job_status: 'waiting',
      node_key: 'waiting_for_selection',
      progress: 70,
      row_revision: 2,
      allowed_commands: [],
      resume_cursor: 11,
    })
    setTimeout(() => sendSSE(response, 'task', taskEvent(11), 11), 40)
  }
}

const startWorkflow = async (request, response) => {
  await readJson(request)
  state.stats.startRequests += 1
  if (state.scenario === 'duplicate-click') {
    await new Promise((resolve) => setTimeout(resolve, 250))
  }
  const restarted = state.scenario === 'cancelled-restart'
  state.snapshot = baseSnapshot(restarted ? {
    run_id: runB,
    root_job_id: rootB,
    row_revision: 1,
    resume_cursor: 1,
  } : {})
  json(response, 202, { ...connection(state.snapshot), created: true })
}

const submitCommand = async (request, response) => {
  const body = await readJson(request)
  state.stats.commands.push(body)
  const type = body.type
  if (type === 'select') {
    state.snapshot = baseSnapshot({
      status: 'finalizing',
      root_job_status: 'running',
      node_key: 'finalize_revision',
      progress: 85,
      row_revision: (state.snapshot?.row_revision ?? 0) + 1,
      current_chapter_revision: 1,
      allowed_commands: ['cancel'],
      resume_cursor: (state.snapshot?.resume_cursor ?? 0) + 1,
    })
  } else {
    state.snapshot = baseSnapshot({
      row_revision: (state.snapshot?.row_revision ?? 0) + 1,
      resume_cursor: (state.snapshot?.resume_cursor ?? 0) + 1,
    })
  }
  json(response, 202, {
    command_id: body.command_id,
    type,
    status: 'pending',
    snapshot: state.snapshot,
  })
}

const server = createServer(async (request, response) => {
  const url = new URL(request.url ?? '/', `http://${host}:${port}`)
  const path = url.pathname

  try {
    if (request.method === 'GET' && path === '/__e2e/health') {
      json(response, 200, { ok: true })
      return
    }
    if (request.method === 'POST' && path === '/__e2e/scenario') {
      const body = await readJson(request)
      closeClients(workflowClients)
      state = initialState(String(body.scenario || 'current-null-start'))
      json(response, 200, { scenario: state.scenario })
      return
    }
    if (request.method === 'POST' && path === '/__e2e/event') {
      const body = await readJson(request)
      handleControlEvent(String(body.action || ''))
      json(response, 200, { ok: true })
      return
    }
    if (request.method === 'GET' && path === '/__e2e/stats') {
      json(response, 200, state.stats)
      return
    }
    if (request.method === 'GET' && path === '/api/auth/users/me') {
      json(response, 200, {
        id: 1,
        username: 'e2e-writer',
        is_admin: false,
        must_change_password: false,
      })
      return
    }
    if (request.method === 'GET' && path === '/api/auth/options') {
      json(response, 200, {
        allow_registration: true,
        enable_email_verification: false,
        enable_linuxdo_login: false,
      })
      return
    }
    if (request.method === 'GET' && path === '/api/llm-config') {
      json(response, 200, {
        legacy: null,
        providers: [],
        models: [],
        stage_routes: [],
      })
      return
    }
    if (request.method === 'GET' && path === '/api/novels') {
      json(response, 200, [projectSummary()])
      return
    }
    if (request.method === 'GET' && path === `/api/novels/${projectId}`) {
      json(response, 200, project())
      return
    }
    if (request.method === 'GET' && path === `/api/novels/${projectId}/chapters/1`) {
      json(response, 200, projectChapter())
      return
    }
    if (request.method === 'GET' && path === '/api/tasks') {
      json(response, 200, [])
      return
    }
    if (request.method === 'GET' && path === '/api/tasks/snapshot') {
      json(response, 200, taskSnapshot(undefined, 0))
      return
    }
    if (request.method === 'GET' && path === '/api/tasks/events') {
      if (url.searchParams.get('stream_type') === 'workflow') {
        handleWorkflowStream(request, response)
      } else {
        openSSE(request, response, globalClients)
        sendSSE(response, 'snapshot', taskSnapshot(undefined, 0), 0)
      }
      return
    }
    if (
      request.method === 'GET'
      && path === '/api/writer/chapter-workflows/current'
    ) {
      state.stats.currentRequests += 1
      if (state.scenario === 'fatal-contract' && state.stats.currentRequests === 1) {
        json(response, 200, connection(baseSnapshot({ workflow_version: 2 })))
        return
      }
      if (state.scenario === 'fatal-contract') {
        json(response, 200, null)
        return
      }
      if (state.scenario === 'superseded-follow' && state.stats.currentRequests > 1) {
        state.snapshot = baseSnapshot({
          run_id: runB,
          root_job_id: rootB,
          row_revision: 1,
          resume_cursor: 1,
        })
      }
      json(response, 200, state.snapshot === null ? null : connection(state.snapshot))
      return
    }
    if (request.method === 'POST' && path === '/api/writer/chapter-workflows') {
      await startWorkflow(request, response)
      return
    }
    if (
      request.method === 'POST'
      && /^\/api\/writer\/chapter-workflows\/[^/]+\/commands$/.test(path)
    ) {
      await submitCommand(request, response)
      return
    }

    state.stats.unknownRequests.push(`${request.method} ${path}`)
    json(response, 404, { detail: `No E2E fixture for ${request.method} ${path}` })
  } catch (error) {
    json(response, 500, {
      detail: error instanceof Error ? error.message : 'E2E fixture failure',
    })
  }
})

const shutdown = () => {
  closeClients(workflowClients)
  closeClients(globalClients)
  server.close(() => process.exit(0))
}

process.on('SIGINT', shutdown)
process.on('SIGTERM', shutdown)

server.listen(port, host, () => {
  process.stdout.write(`E2E fixture listening on http://${host}:${port}\n`)
})
