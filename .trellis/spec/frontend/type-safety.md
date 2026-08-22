# Frontend Type Safety

> TypeScript `strict` mode. Migrated HTTP wire DTOs are generated from backend OpenAPI;
> UI/domain types and not-yet-migrated contracts stay colocated. There is no central
> `types/` directory.

---

## tsconfig

`tsconfig.app.json` extends `@vue/tsconfig/tsconfig.dom.json`, which sets `strict: true`. Path alias `@/* -> ./src/*`. `src/**/__tests__/*` is excluded from the build config but covered by `vitest`. Do not loosen these settings.

Type-check command: `npm run type-check` (`vue-tsc --build`).

---

## Where types live

The canonical generated artifact is `src/api/generated/schema.d.ts`, produced from
`backend/openapi.json`. Do not edit it. Migrated API modules expose readable indexed
aliases and thread them through `Promise<T>`, `useQuery<T>`, and component props.

```ts
export type NovelProject = components['schemas']['NovelProject']
export type Chapter = components['schemas']['Chapter']
```

Legacy endpoints without generated ownership still keep their types in the owning
`src/api/<domain>.ts` file. Do not move them to a central directory. When migrating a
domain, add the generated alias first, cut consumers over, then remove the old field
declaration in the same release unit. See
[Generated Transport Contract](../backend/transport-contracts.md).

---

## Rules

- Type every `useQuery<T>` / `useMutation<T>` with the real response interface — never omit the type parameter.
- Type props and emits with the generic forms (see [component-guidelines](./component-guidelines.md)).
- For external/untrusted payloads (SSE events, parsed JSON), narrow with a type guard or `unknown` + runtime check before casting.
- Mirror the backend snake_case field names in API interfaces (`must_change_password`, `last_edited`); convert to camelCase at a typed boundary if a component needs it. Do not silently rename halfway.
- Do not restore a migrated DTO as an interface or object-literal type alias. Run `npm run api:check` to execute byte and ownership gates.
- Keep genuine dynamic dictionaries as `unknown` and narrow them once in a domain utility. Do not weaken a generated alias with `any`.

---

## `any` policy

`any` is forbidden in new code under `src/api/*` signatures, prop/emit types, and `useQuery<T>` type parameters. Replace with:

- `unknown` when you cannot guarantee the shape, then narrow.
- A defined interface, when you can.
- `unknown[]` / `Record<string, unknown>` for opaque blobs, with a comment on what narrows them.

Remaining known hotspots are documented as debt, not fixed inline:

- Legacy editor components still use runtime props/emits contracts that permit dynamic values without generic TypeScript signatures.
- A few isolated UI sites outside the novel-detail boundary still use local casts for dynamic component refs or evaluation records.

Dynamic chapter/version metadata and parsed evaluation payloads now start as
`Record<string, unknown>`; every consumer must narrow nested objects and scalar fields
before reading them. Novel-detail section edit events carry `unknown` until the existing
editor input union is checked at the modal boundary.

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
- Hand-writing fields for a migrated OpenAPI schema instead of indexing `components`/`operations`.
- Creating a `types/` directory; use generated aliases or colocate legacy/domain types with their owner.
- Loosening `tsconfig` strictness to make an error disappear.
