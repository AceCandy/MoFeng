# Thinking Guides

> **Purpose**: Expand your thinking to catch things you might not have considered before writing code in MoFeng.

---

## Why thinking guides?

**Most bugs come from "didn't think of that"**, not from lack of skill:

- Didn't think about what happens at the router↔service↔repository boundary → cross-layer bugs.
- Didn't think about the backend↔frontend response-shape mirror → UI shows `undefined`.
- Didn't think about reusing `BaseRepository` / `http.ts` / `xxxQueryKeys` → duplicated, drifting logic.
- Didn't think about which other sites a value change touches → "forgot to update X" bugs.

These guides help you ask the right questions before coding.

---

## Available guides

| Guide | Purpose | When to use |
|-------|---------|-------------|
| [Cross-Layer Thinking Guide](./cross-layer-thinking-guide.md) | Trace data component → query → api → router → service → repository → model | Any feature touching 2+ layers; adding/renaming a field or path |
| [Code Reuse Thinking Guide](./code-reuse-thinking-guide.md) | Reuse existing symbols; avoid forking HTTP/schema/query-key contracts | Before adding any helper, wrapper, schema, or type |

---

## Quick reference: thinking triggers

### When to think about cross-layer issues

- [ ] Feature touches 3+ layers (component, query, api, router, service, repository, model).
- [ ] You are adding or renaming a field on a backend Pydantic `*Read` model.
- [ ] You are adding a column to an ORM model (→ `_ensure_schema_updates` + `.sql`).
- [ ] You are renaming an API path (→ frontend call sites + legacy redirect).
- [ ] A Read schema reads a relation — is it eager-loaded in the repository?
- [ ] Error messages stop surfacing in the UI — does the router raise them in `detail`?
- [ ] A Celery task needs DB access — does it reuse `AsyncSessionLocal`?

→ Read [Cross-Layer Thinking Guide](./cross-layer-thinking-guide.md)

### When to think about code reuse

- [ ] You're about to write a fetch/timeout/abort wrapper → use `src/api/http.ts`.
- [ ] You're about to write `select(model).filter_by(...)` in a service → subclass `BaseRepository`.
- [ ] You're about to define a Pydantic schema inside a router → move it to `app/schemas/`.
- [ ] You're about to inline-cast an untyped payload field → define the interface in `src/api/*`.
- [ ] You're adding a query key → use the domain's `xxxQueryKeys` factory.
- [ ] You're modifying a `Literal`/enum value → grep every if/elif/else that switches on it.
- [ ] You're changing a value that has N copies (schema field, path, error field) → update all sites.

→ Read [Code Reuse Thinking Guide](./code-reuse-thinking-guide.md)

### When verifying AI cross-review results

- [ ] Reviewer claims "user input can be malicious" → check the actual data source (auth-gated API? admin only? external?).
- [ ] Reviewer flags "missing validation" → is the data already validated by Pydantic at the router?
- [ ] Reviewer says "behavior change" → read the code comment / `AIMETA` header — is it intentional design?
- [ ] Reviewer identifies a "bug" in a test → mentally delete the feature; does the test still pass? If yes → tautological test.

**Common AI reviewer false positives in this repo**:

1. **Trust-boundary confusion** — flagging auth-gated admin inputs as if they were public untrusted input.
2. **Ignoring design comments** — flagging intentional behavior documented in `AIMETA` or docstrings as a bug.
3. **Layer confusion** — asking a repository to `commit()`, or a service to avoid `HTTPException`, without reading the spec.

**Rule**: every CRITICAL/WARNING finding must be verified against the actual code (and the matching spec) before prioritizing. Budget a meaningful false-positive rate for AI reviews.

---

## Pre-modification rule

> **Before changing any value that has copies, search first.**

```bash
# A field rename — find every site
grep -rn "old_field_name" backend/app frontend/src

# A path rename — find every call site + redirect
grep -rn "/api/old-path" backend/app frontend/src
```

This single habit prevents most "forgot to update X" bugs. The high-value targets in MoFeng: ORM columns, Pydantic schema fields, API paths, error-message field names, query keys.

---

## How to use this directory

1. **Before coding**: skim the relevant guide.
2. **During coding**: if something feels repetitive or spans layers, re-check the triggers above.
3. **After a bug**: add the lesson to the relevant guide.

Found a new "didn't think of that" moment? Add it to the relevant guide.

---

**Core principle**: 30 minutes of tracing data flow and grepping for existing symbols saves 3 hours of debugging.
