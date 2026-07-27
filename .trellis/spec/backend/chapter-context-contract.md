# Canonical Chapter Context Contract

## 1. Scope / Trigger

Apply this contract whenever generation, review, consistency checking, or durable chapter recovery needs project/chapter facts. `ChapterContextResolver` is the only boundary allowed to read those facts from the database or retrieval services. Downstream callers receive a frozen `ChapterContext` and use pure adapters.

## 2. Signatures

```python
await ChapterContextResolver.resolve(
    *,
    project_id: str,
    chapter_number: int,
    user_id: int,
    writing_notes: str | None = None,
    chapter_mission: dict[str, Any] | None = None,
    rag_enabled: bool = False,
    rag_query: str | None = None,
    rag_mode: str = "simple",
    pov_character: str | None = None,
) -> ChapterContext

resolver.with_runtime_inputs(
    context: ChapterContext,
    *,
    writing_notes: str | None,
    chapter_mission: dict[str, Any] | None,
) -> ChapterContext

await resolver.with_retrieval(
    context: ChapterContext,
    *,
    user_id: int,
    enabled: bool,
    query_text: str,
    mode: str = "simple",
    pov_character: str | None = None,
) -> ChapterContext

GenerationContextAdapter.to_context(context) -> dict[str, Any]
ReviewContextAdapter.to_prompt_context(context) -> dict[str, Any]
ConsistencyContextAdapter.to_prompt_context(context) -> dict[str, Any]
```

## 3. Contracts

- Every section is a `ContextSection` with exactly `value`, `source`, `source_revision`, `truncated`, and `fallback`.
- `source_revision` covers canonical database facts: blueprint (including normalized child data), target outline, chapter blueprint, constitution, writer persona, and successful selected-chapter history.
- Projection sources such as project memory, foreshadows, character states, and RAG do not enter the top-level `source_revision`. They carry their own section revision and participate in `input_hash`.
- Record revisions hash both normalized content and normalized UTC `updated_at`. Successful history revisions also hash selected content and `real_summary`; IDs/timestamps alone are insufficient.
- `input_hash` covers the complete normalized snapshot except `created_at` and itself. `ChapterContext.model_validate()` rejects a supplied hash that does not match the payload.
- A durable snapshot is reusable only for the same `project_id` and `chapter_number`. Invalid, legacy, or mismatched snapshots are rebuilt through the resolver.
- Recovery reapplies runtime notes/mission. RAG is refreshed or disabled when runtime inputs, enabled state, normalized query, or mode changes; an identical retrieval snapshot is reused.
- Writer visibility is applied before the contract reaches adapters. Review/generation adapters must not expose the full blueprint.
- Adapters perform no database or network I/O. Compatibility shadow mappings are independent pure mappings, and diff logs contain paths/types/sizes only, never prompt values.

Configuration:

| Environment key | Required | Contract |
|---|---:|---|
| `CHAPTER_CONTEXT_SHADOW_COMPARE` | no | Enables structured compatibility diffs; defaults to `false`. |
| `VECTOR_STORE_ENABLED` | no | Controls whether RAG retrieval can execute; disabled/unavailable states remain explicit fallbacks. |

## 4. Validation & Error Matrix

| Condition | Required result |
|---|---|
| Project is missing | Resolver raises the existing project-not-found error. |
| Required target outline is missing | Resolver raises a validation error; callers do not synthesize an outline. |
| Optional section is missing | Typed empty value plus `source_revision="missing"` and an explicit fallback. |
| RAG is disabled | `fallback="disabled"`; no embedding/vector call. |
| Embedding fails | `fallback="embedding_failed"`; no empty-success disguise. |
| Retrieval/filtering fails | `fallback="retrieval_failed"`; do not report `retrieval_empty`. |
| Retrieval succeeds with no results | `fallback="retrieval_empty"`. |
| Snapshot hash is invalid | Reject and rebuild; never trust or partially merge it. |
| Snapshot identity differs | Rebuild for the requested project/chapter. |
| Snapshot retrieval inputs are unchanged | Reuse the frozen RAG snapshot. |
| Snapshot retrieval inputs change | Re-run `with_retrieval`, including explicit disable. |

## 5. Good / Base / Bad Cases

- Good: resolve once, persist `snapshot_payload()`, and derive generation/review/consistency views from that same object.
- Base: a first chapter has typed empty history with `first_chapter`; missing optional projections remain explicit and serializable.
- Bad: a router or service queries memory/constitution/persona/RAG again after receiving `ChapterContext`, or reconstructs prompt context from ORM entities.

## 6. Tests Required

- `test_chapter_context_contract.py`: deterministic serialization, tamper rejection, every-section provenance, visibility, adapter equality, and structure-only shadow diffs.
- `test_chapter_context_resolver.py`: first chapter, budgets, projection versus canonical revisions, content-sensitive history/record revisions, RAG fallbacks, and no second DB read in two-stage retrieval.
- `test_pipeline_context_restore.py`: invalid/mismatched snapshot rebuild, runtime updates, retrieval input refresh/disable, and unchanged snapshot reuse.
- Static wiring tests must assert pipeline/writer/review/consistency use resolver/adapters and do not restore deleted context builders.

## 7. Wrong vs Correct

### Wrong

```python
context = ChapterContext.model_validate(snapshot)
if rag_enabled:
    return context  # silently reuses an old query or old disabled state
```

### Correct

```python
context = ChapterContext.model_validate(snapshot)
context = resolver.with_runtime_inputs(context, writing_notes=notes, chapter_mission=mission)
if retrieval_inputs_changed:
    context = await resolver.with_retrieval(context, enabled=rag_enabled, ...)
return context
```
