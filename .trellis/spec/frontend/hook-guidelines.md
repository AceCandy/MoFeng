# Frontend Hook / Data-Fetching Guidelines

> UI helpers in `composables/`, server cache in `queries/`. All server data flows through TanStack Vue Query.

---

## Two kinds of `useXxx`

| Location | Contains | Example |
|----------|----------|---------|
| `src/composables/` | UI-only stateful helpers (DOM, viewport, local UI state). No `fetch`, no `useQuery`. | `useAlert.ts`, `useDialogA11y.ts`, `useResponsiveViewport.ts` |
| `src/queries/` | Server-cache hooks (`useXxxQuery` / `useXxxMutation`) + a `xxxQueryKeys` factory. One file per API domain. | `queries/tasks.ts`, `queries/novel.ts`, `queries/llm.ts`, `queries/admin.ts`, `queries/auth.ts`, `queries/updates.ts` |

If a hook calls the API, it belongs in `queries/`. If it only touches the DOM or local reactive state, it belongs in `composables/`.

---

## Query-key factories

Every domain exports a `xxxQueryKeys` object with hierarchical keys. Use it for both `useQuery` and `invalidateQueries`. Reference: `src/queries/tasks.ts`.

```ts
export const tasksQueryKeys = {
  all: ['tasks'] as const,
  list: () => [...tasksQueryKeys.all, 'list'] as const,
  detail: (taskId: string) => [...tasksQueryKeys.all, 'detail', taskId] as const,
}

export function useTasksQuery() {
  return useQuery<BackgroundTask[]>({
    queryKey: tasksQueryKeys.list(),
    queryFn: () => TaskAPI.getTasks(),
    refetchInterval: 15_000,
  })
}
```

Rules:

- Always type the hook: `useQuery<T>(...)` with the real response interface.
- Source the queryKey from the domain's factory, never an inline literal.
- Detail queries take reactive sources via `MaybeRefOrGetter` + `toValue`, and gate with `enabled`:

```ts
export function useTaskQuery(taskId: TaskIdSource) {
  return useQuery<BackgroundTask>({
    queryKey: computed(() => tasksQueryKeys.detail(toValue(taskId) || '__missing__')),
    queryFn: () => TaskAPI.getTask(toValue(taskId) || ''),
    enabled: computed(() => Boolean(toValue(taskId))),
  })
}
```

---

## QueryClient setup

Configured once in `src/lib/queryClient.ts` (`staleTime` 30s, `gcTime` 5m, `shouldRetryQuery` skips 400/401/403/404/422) and registered in `src/main.ts`:

```ts
app.use(VueQueryPlugin, { queryClient })
```

Do not create ad-hoc `QueryClient` instances in components.

For one-shot reads outside a hook (e.g. router guard session restore), use `queryClient.fetchQuery(options)` with the same options object the hook would use. Reference: `src/router/index.ts` imports `currentUserQueryOptions` from `@/queries/auth`.

---

## Mutations and invalidation

- Define mutations in `queries/<domain>.ts` via `useMutation`. Call the typed `src/api/<domain>.ts` function in `mutationFn`.
- On success, invalidate via the affected domains' key factories. Cross-domain invalidation imports the other domain's `xxxQueryKeys` (there is intentionally no central key index).
- Surface mutation errors through the mutation's own state + `useAlert()`, not via `try/catch` + manual fetch.

---

## Polling and SSE

When SSE is the primary sync channel, keep a long `refetchInterval` as a fallback for connection drops (see `useTasksQuery` above). Do not remove polling just because SSE exists.

For cursor-based task SSE:

- Keep the last applied durable cursor and ignore events whose cursor is not greater.
- Send the same cursor in the query and `Last-Event-ID` when both are present.
- Treat `reset` as a state replacement boundary: fetch a new `snapshot_revision + resume_cursor` pair for the same stream scope, replace the cached task list/cursor, then reconnect.
- Clear snapshot and cursor before reconnecting when the authenticated user or `(stream_type, stream_id)` changes.
- Redis availability is not a frontend state signal. The backend event log and snapshot pair remain authoritative, while the long polling interval remains the final fallback.

See [Durable Job And Event Log](../backend/durable-job-guidelines.md) for the cross-layer contract.

---

## Anti-patterns to avoid

- Calling `TaskAPI.<method>` (or any `src/api/*`) directly inside a component for read data — wrap it in a `useXxxQuery` hook so the cache and loading state are reusable.
- Inline query-key literals (`['tasks']`) instead of the factory.
- Putting a `useQuery` hook in `composables/`.
- Recreating `QueryClient` per component.
- `any` as the `useQuery<T>` type parameter (see [type-safety](./type-safety.md)).
