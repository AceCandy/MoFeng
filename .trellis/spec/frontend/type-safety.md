# Frontend Type Safety

> TypeScript `strict` mode. Types are hand-authored and colocated with their API module — there is no central `types/` dir.

---

## tsconfig

`tsconfig.app.json` extends `@vue/tsconfig/tsconfig.dom.json`, which sets `strict: true`. Path alias `@/* -> ./src/*`. `src/**/__tests__/*` is excluded from the build config but covered by `vitest`. Do not loosen these settings.

Type-check command: `npm run type-check` (`vue-tsc --build`).

---

## Where types live

Response interfaces are **hand-authored** in the API module that owns the endpoint, then re-exported and threaded into `Promise<T>` signatures, `useQuery<T>`, and component props. There is **no codegen** and **no central `types/` directory**. Reference: `src/api/novel.ts`.

```ts
export interface NovelProject {
  id: string
  title: string
  initial_prompt: string
  blueprint?: Blueprint
  chapters: Chapter[]
  conversation_history: ConversationMessage[]
}

export interface NovelProjectSummary {
  id: string
  title: string
  genre: string
  last_edited: string
  completed_chapters: number
  total_chapters: number
}
```

When adding an endpoint, define the response interface in the same `src/api/<domain>.ts` file and export it so `queries/<domain>.ts` and components can import it.

---

## Rules

- Type every `useQuery<T>` / `useMutation<T>` with the real response interface — never omit the type parameter.
- Type props and emits with the generic forms (see [component-guidelines](./component-guidelines.md)).
- For external/untrusted payloads (SSE events, parsed JSON), narrow with a type guard or `unknown` + runtime check before casting.
- Mirror the backend snake_case field names in API interfaces (`must_change_password`, `last_edited`); convert to camelCase at a typed boundary if a component needs it. Do not silently rename halfway.

---

## `any` policy

`any` is forbidden in new code under `src/api/*` signatures, prop/emit types, and `useQuery<T>` type parameters. Replace with:

- `unknown` when you cannot guarantee the shape, then narrow.
- A defined interface, when you can.
- `unknown[]` / `Record<string, unknown>` for opaque blobs, with a comment on what narrows them.

Current known hotspots (~49 occurrences across ~18 files) are documented as debt, not fixed inline:

- `src/api/novel.ts`: `Blueprint.world_setting?: any`, `relationships?: any[]`, `conversation_state: any`, and `conversationState: any = {}` parameters in converse method signatures.
- `src/components/novel-detail/ChapterOutlineSection.vue`: emit `(e: 'edit', payload: { field: string; title: string; value: any })`.
- `src/main.ts`: `(target as any).tagName` escape hatch.

When editing those files for another reason, narrowing these is welcome.

Bad example — an API signature with `any`:

```ts
// AVOID
async converse(novelId: string, conversationState: any): Promise<any> { ... }
```

Good example — typed with an interface and `unknown`:

```ts
async converse(novelId: string, conversationState: ConversationState): Promise<ConversationResponse> { ... }
```

---

## Anti-patterns to avoid

- `as any` to silence a type error.
- `any` in exported API signatures or emit payloads.
- Leaving `useQuery` / `useMutation` without a type parameter.
- Creating a `types/` directory; colocate with the API module instead.
- Loosening `tsconfig` strictness to make an error disappear.
