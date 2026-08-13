# Debug Retrospective

## Root Cause Category

- Cross-layer contract: durable review selected `best_ordinal`, but persistence did not expose that fact on `ChapterVersion` for the public read projection.
- Test coverage gap: the previous regression test began after persistence and hand-built compatibility metadata.
- Implicit assumption: compatibility `PipelineOrchestrator` metadata was treated as if the durable producer emitted the same shape.

## Why The Previous Fix Failed

The reader correctly narrowed a unique `metadata.ai_review.is_best=true` version, but the enabled durable producer never wrote that field. Unit-level read tests passed while the production chain continued returning two candidates.

## Prevention

- Cross-layer fixes with coexisting old/new producers require one integration test from the enabled producer through persistence to the public consumer.
- Compatibility fixtures prove only compatibility behavior and cannot be the primary acceptance evidence for replacement workflows.
- Producer ownership for `ChapterVersion.metadata.ai_review.is_best` is now explicit in the durable workflow spec.
