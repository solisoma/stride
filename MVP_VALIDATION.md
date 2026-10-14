# MVP validation ? 14 October 2026

Verified using the four-page Erran business PDF already present in backend/uploads, the configured gpt-4.1-mini model, and the actual Docker API/RabbitMQ worker.

## Changes

- Refined semantic splitting: one overall subject no longer causes independently useful sections to collapse into a single page-sized leaf. Original word-boundary slicing, coherence rules, and source preservation remain.
- Changed the processing configuration version so interrupted work from the prior prompt is not reused. Existing ready documents are not automatically rewritten.
- Rejected unsupported optional source concerns without discarding valid plan topics. Invalid topic citations remain errors; invalid concerns are logged without source text.
- Kept a displayed guide's current cited passages available to its follow-up chat, while respecting source exclusions and revisions.
- Added one bounded corrective attempt for malformed JSON or invalid citation IDs. Persistently invalid responses still fail validation.

## Verified result

The live worker produced 35 nodes, 23 source leaves, and four hierarchy levels. Every node satisfies fanout <= 5. All non-whitespace source characters on all four pages were preserved exactly once; source leaves retain physical page references.

Passed: registration/login, queued upload, real RabbitMQ processing, learning plan, cited study guide, scenario question, detailed correction, contextual chat, progress/chat persistence after login, and real mobile browser navigation/refresh without page overflow. The incorrect practice answer received needs_revision.

95 backend regression tests passed. Backend type checking and unused-import checks passed. Frontend type checking and the opt-in live mobile browser test passed.

## Review/demo artifacts

- backend/.mvp-validation/live/tree.json ? actual saved hierarchy and source text.
- backend/.mvp-validation/live/report.json ? live verification results.
- backend/.mvp-validation/live/demo-login.json ? separate demo learner credentials; admin credentials were not changed.

Artifacts contain document content or credentials and are excluded from source control and Docker build contexts.

This verifies the tested four-page PDF demo flow. It does not establish accuracy/performance for every PDF, large documents, image-only material, or audio languages.

## Repeat

In backend, `uv run python -m scripts.validate_mvp uploads/043e8b7f8bbe7e176bee6a5a2a439494.pdf` uses the actual backend in a separate validation database. Add --ingestion-only to check just the tree, or --reprocess to rebuild that validation document.

`uv run python -m scripts.validate_live_mvp` creates a separate demo learner and processes the PDF through the running Docker services. It makes real model calls.

In frontend, set `$env:STRIDE_LIVE_TEST="true"`, then run `npm.cmd run test:browser -- mvp-live.spec.ts` to inspect the prepared live demo account without generating additional model answers.
