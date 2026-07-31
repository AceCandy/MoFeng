// AIMETA P=章节工作流Query_current与命令缓存|R=current查询_start与command原子协调|NR=不持有UI状态或推导workflow终态|E=query:chapter-workflow|X=internal|A=useCurrentChapterWorkflowQuery|D=@tanstack/vue-query|S=net,cache|RD=./README.ai
import { computed, toValue, type MaybeRefOrGetter } from 'vue'
import { useMutation, useQuery, useQueryClient, type QueryClient } from '@tanstack/vue-query'

import {
  ChapterWorkflowAPI,
  ChapterWorkflowContractError,
  decodeChapterWorkflowCommandConflict,
  type ChapterWorkflowCommandConflictDetail,
  type ChapterWorkflowCommandEnvelope,
  type ChapterWorkflowCommandResponse,
  type ChapterWorkflowConnection,
  type ChapterWorkflowScope,
  type ChapterWorkflowSnapshot,
  type ChapterWorkflowStartRequest,
  type ChapterWorkflowStartResponse,
} from '@/api/chapterWorkflow'
import { HttpRequestError } from '@/api/http'
import { TaskAPI } from '@/api/tasks'
import type { ChapterWorkflowActorPorts } from '@/composables/useChapterWorkflowActor'
import { useNovelMutationRefresh } from '@/queries/novel'

type ProjectIdSource = MaybeRefOrGetter<string | null | undefined>
type ChapterNumberSource = MaybeRefOrGetter<number | null | undefined>

export interface ChapterWorkflowCommandMutationVariables extends ChapterWorkflowScope {
  runId: string
  command: ChapterWorkflowCommandEnvelope
}

export class ChapterWorkflowCommandConflictError extends Error {
  readonly detail: ChapterWorkflowCommandConflictDetail

  constructor(detail: ChapterWorkflowCommandConflictDetail) {
    super('章节工作流状态已变化，请按最新状态重试')
    this.name = 'ChapterWorkflowCommandConflictError'
    this.detail = detail
  }
}

export const chapterWorkflowQueryKeys = {
  all: ['chapter-workflow'] as const,
  current: (projectId: string, chapterNumber: number) =>
    [...chapterWorkflowQueryKeys.all, 'current', projectId, chapterNumber] as const,
}

const toConnection = (
  response: ChapterWorkflowStartResponse,
): ChapterWorkflowConnection => ({
  events_url: response.events_url,
  snapshot: response.snapshot,
})

const setCurrentConnection = (
  queryClient: QueryClient,
  scope: ChapterWorkflowScope,
  connection: ChapterWorkflowConnection,
) => {
  queryClient.setQueryData<ChapterWorkflowConnection | null>(
    chapterWorkflowQueryKeys.current(scope.projectId, scope.chapterNumber),
    (current) => {
      if (
        current?.snapshot.run_id === connection.snapshot.run_id
        && current.snapshot.row_revision > connection.snapshot.row_revision
      ) {
        return current
      }
      return connection
    },
  )
}

const reconcileCurrentSnapshot = (
  queryClient: QueryClient,
  scope: ChapterWorkflowScope,
  fallback: ChapterWorkflowConnection,
  snapshot: ChapterWorkflowSnapshot,
) => {
  queryClient.setQueryData<ChapterWorkflowConnection | null>(
    chapterWorkflowQueryKeys.current(scope.projectId, scope.chapterNumber),
    (current) => {
      const connection = current ?? fallback
      if (connection.snapshot.run_id !== snapshot.run_id) {
        return current
      }
      if (connection.snapshot.row_revision > snapshot.row_revision) {
        return connection
      }
      if (connection.snapshot.row_revision === snapshot.row_revision) {
        return snapshot.resume_cursor > connection.snapshot.resume_cursor
          ? {
              ...connection,
              snapshot: {
                ...connection.snapshot,
                resume_cursor: snapshot.resume_cursor,
              },
            }
          : connection
      }
      return { ...connection, snapshot }
    },
  )
}

const requireCurrentConnection = (
  queryClient: QueryClient,
  variables: ChapterWorkflowCommandMutationVariables,
) => {
  const connection = queryClient.getQueryData<ChapterWorkflowConnection | null>(
    chapterWorkflowQueryKeys.current(variables.projectId, variables.chapterNumber),
  )
  if (
    !connection
    || connection.snapshot.run_id !== variables.runId
    || connection.snapshot.project_id !== variables.projectId
    || connection.snapshot.chapter_number !== variables.chapterNumber
  ) {
    throw new ChapterWorkflowContractError('identity_mismatch', 'command_cache')
  }
  return connection
}

export function useCurrentChapterWorkflowQuery(
  projectId: ProjectIdSource,
  chapterNumber: ChapterNumberSource,
) {
  const currentScope = () => ({
    projectId: toValue(projectId) || '',
    chapterNumber: toValue(chapterNumber) || 0,
  })

  return useQuery<ChapterWorkflowConnection | null>({
    queryKey: computed(() => {
      const scope = currentScope()
      return chapterWorkflowQueryKeys.current(scope.projectId || '__missing__', scope.chapterNumber)
    }),
    queryFn: ({ signal, queryKey }) => {
      const resolvedProjectId = queryKey[2]
      const resolvedChapterNumber = queryKey[3]
      if (typeof resolvedProjectId !== 'string' || typeof resolvedChapterNumber !== 'number') {
        throw new ChapterWorkflowContractError('malformed', 'query_key')
      }
      return ChapterWorkflowAPI.getCurrent({
        projectId: resolvedProjectId,
        chapterNumber: resolvedChapterNumber,
      }, { signal })
    },
    enabled: computed(() => {
      const scope = currentScope()
      return Boolean(scope.projectId) && Number.isInteger(scope.chapterNumber) && scope.chapterNumber > 0
    }),
    staleTime: 0,
    retry: false,
  })
}

export function useStartChapterWorkflowMutation() {
  const queryClient = useQueryClient()

  return useMutation<ChapterWorkflowStartResponse, Error, ChapterWorkflowStartRequest>({
    mutationFn: async (input) => {
      const response = await ChapterWorkflowAPI.start(input)
      setCurrentConnection(
        queryClient,
        { projectId: input.project_id, chapterNumber: input.chapter_number },
        toConnection(response),
      )
      return response
    },
  })
}

export function useChapterWorkflowCommandMutation() {
  const queryClient = useQueryClient()

  return useMutation<
    ChapterWorkflowCommandResponse,
    Error,
    ChapterWorkflowCommandMutationVariables
  >({
    mutationFn: async (variables) => {
      const scope = {
        projectId: variables.projectId,
        chapterNumber: variables.chapterNumber,
      }
      const connection = requireCurrentConnection(queryClient, variables)
      try {
        const response = await ChapterWorkflowAPI.submitCommand(
          scope,
          variables.runId,
          variables.command,
        )
        reconcileCurrentSnapshot(queryClient, scope, connection, response.snapshot)
        return response
      } catch (error) {
        if (!(error instanceof HttpRequestError) || error.status !== 409) {
          throw error
        }
        const conflict = decodeChapterWorkflowCommandConflict(error.payload, {
          scope,
          runId: variables.runId,
        })
        reconcileCurrentSnapshot(
          queryClient,
          scope,
          connection,
          conflict.detail.current_snapshot,
        )
        throw new ChapterWorkflowCommandConflictError(conflict.detail)
      }
    },
  })
}

export function useChapterWorkflowActorPorts(): ChapterWorkflowActorPorts {
  const queryClient = useQueryClient()
  const startMutation = useStartChapterWorkflowMutation()
  const commandMutation = useChapterWorkflowCommandMutation()
  const { refreshProjectQueries, refreshChapter } = useNovelMutationRefresh()

  return {
    lookup: (scope, signal) => queryClient.fetchQuery<ChapterWorkflowConnection | null>({
      queryKey: chapterWorkflowQueryKeys.current(scope.projectId, scope.chapterNumber),
      queryFn: () => ChapterWorkflowAPI.getCurrent(scope, { signal }),
      staleTime: 0,
      retry: false,
    }),
    start: (request) => startMutation.mutateAsync(request),
    command: async (input) => {
      try {
        const response = await commandMutation.mutateAsync(input)
        return { kind: 'response', response }
      } catch (error) {
        if (!(error instanceof ChapterWorkflowCommandConflictError)) throw error
        return {
          kind: 'conflict',
          detail: error.detail,
          message: error.message,
        }
      }
    },
    subscribeTasks: (subscription) => TaskAPI.subscribeTasks(subscription),
    invalidateChapterAndProject: async (scope) => {
      await Promise.all([
        refreshProjectQueries(scope.projectId),
        refreshChapter(scope.projectId, scope.chapterNumber),
      ])
    },
    schedule: (callback, delayMs) => globalThis.setTimeout(callback, delayMs),
    cancelScheduled: (handle) => {
      globalThis.clearTimeout(handle as ReturnType<typeof globalThis.setTimeout>)
    },
  }
}
