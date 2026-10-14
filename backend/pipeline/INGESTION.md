# Stride ingestion: actual backend files

Work on ingestion directly in this backend. The standalone document-tree lab has been deleted. Learning-plan changes come after ingestion is resolved.

## Processing flow

Upload → saved file and document record → transactional dispatch record → RabbitMQ → worker → extract text/images/audio → recursively split coherent sections → summarize → group into a bounded tree → save tree and citation passages → mark ready.

The worker currently requests a plan refresh after readiness. That is a separate operation: a plan failure does not discard the processed document.

## Upload and job execution

| File relative to backend | Responsibility and changes |
|---|---|
| `api/main.py` | Upload endpoint checks format/size, saves the original file, creates `Document`, `DocumentIngestion`, and the dispatch record together, then returns HTTP 202. Upload no longer waits for model processing. |
| `api/routes/journey_extras.py` | Lists material status and accepts an owned document's manual retry. Retry preserves the original file and checkpoints and starts a new attempt budget. |
| `api/services/material_service.py` | Builds safe material responses and filters ready documents. Internal paths and configuration hashes stay out of frontend responses. |
| `api/services/ingestion_queue.py` | Publishes durable RabbitMQ messages from the SQL outbox, waits for publisher confirmation before deleting dispatch records, validates message IDs, and supports delayed bounded retries. Messages contain a version and document ID. |
| `scripts/ingestion_worker.py` | Runs dispatch and message consumption. Prefetch is one. Processing runs on a separate thread so broker heartbeats continue. A storage-directory lock permits one worker; acknowledgements follow processing or durable retry scheduling. |
| `api/services/ingestion_jobs.py` | Claims a queued document, verifies the stored file, constructs adapters/cache, executes ingestion, saves tree and passages, updates status, and schedules retry on failure. Restart recovery requeues interrupted jobs. The ready tree is committed before plan refresh; processing caches clear after readiness. |

## Extraction and tree construction

| File relative to backend | Responsibility and changes |
|---|---|
| `pipeline/ingestor.py` | Orchestrator: chooses a parser by extension, injects tree builder/storage/providers, binds durable caches, consumes progress events, and flattens leaves into citation passages with page/timestamp metadata. |
| `pipeline/utils/parsers/extractors.py` | Extracts PDF pages and embedded images, DOCX paragraph/image/table content, and TXT/Markdown text. PDF uses physical pages. DOCX uses groups of 15 extracted text blocks, not physical pagination. TXT/Markdown uses approximately 6,000-character chunks without overlap. Page/image results can be reused after failure. |
| `pipeline/utils/parsers/page_types.py` | Defines the source-page data shape: text plus location metadata. |
| `pipeline/utils/parsers/document_parser.py` | Processes extracted units through splitting, saves completed-page checkpoints, then summarizes and clusters. Saves snapshots of summarized and completed trees to resume later phases. |
| `pipeline/utils/common/base_parser.py` | Shared checkpoint loading/saving, cancellation event, and last-leaf traversal. Deferred cleanup keeps checkpoints until the worker has saved the ready document. |
| `pipeline/tree_builder.py` | Retains the original recursive semantic algorithm. The LLM selects word starts; Python slices the original text. It validates indexes, corrects a nonzero first start when other boundaries are valid, retries invalid boundaries once, and preserves source text on invalid output or depth-limit fallback. The prompt favors coherent thoughts. The LLM still groups children; grouping enforces coverage, bounded fanout, and progress toward a smaller hierarchy. |
| `pipeline/ingestion_models.py` | Defines `Branch`, word-boundary responses, and cluster assignments. Current splitting uses `WordBoundaryList`; `SplitSection`/`SplitSectionList` are leftover definitions from the earlier content-returning approach. |
| `utils/text_rank.py` | Local extractive summaries: sentence processing, TF-IDF similarities, and graph ranking using scikit-learn/numerical libraries. Keeps selected source sentences. This removed summary-generation calls from the LLM by default. `SUMMARY_BACKEND=llm` selects the retained model-summary path. |
| `pipeline/utils/core/text_splitter.py` | Local character-based chunking utility used for TXT/Markdown and transcript input. These are processing units; semantic leaf boundaries are still selected recursively by the LLM. |
| `pipeline/utils/core/helper_fns.py` | Serializes branches to JSON and restores them, handling parent links without circular JSON. Used by saved trees and checkpoints. |

## Images and recordings

| File relative to backend | Responsibility and changes |
|---|---|
| `pipeline/utils/core/vision_helper.py` | Uses structured vision output. Text images return transcribed words; diagrams return explanations; mixed images return both. Missing required content fails instead of silently accepting incomplete extraction. |
| `pipeline/vision_models.py` | Schema for image kind, visible text, and diagram explanation. |
| `pipeline/utils/parsers/media_parser.py` | Extracts video audio, transcribes 30-second segments, saves transcripts and timestamps, then feeds approximately 2,000-character transcript chunks with 200-character overlap into the same semantic pipeline. These input chunks are not final leaves. |
| `providers/transcription.py` | Factory selects OpenAI-compatible transcription or optional local Whisper. Whisper loads lazily, reuses model weights, preserves the spoken language, and checks for empty transcripts. Successful segment outputs are checkpointed through the ingestor's cache binding. |

## Persistence, configuration, and reliability

| File relative to backend | Responsibility and changes |
|---|---|
| `pipeline/utils/storage/storage_manager.py` | SQL storage adapter for parser checkpoints and document trees. Supports deferred checkpoint deletion. |
| `pipeline/utils/storage/checkpoint_cache.py` | Durable cache for individual completed extraction/model steps. Keys include configuration and inputs; separate SQL sessions and per-key locks support concurrent image/cluster calls. A changed processing configuration invalidates reuse. |
| `db/models.py` | `Document`: name/journey and citation passages. `DocumentTree`: hierarchical content. `DocumentIngestion`: private file location, hash, status, progress, attempts, errors. `IngestionCheckpoint`: reusable processing state. `IngestionMessage`: transactional dispatch outbox. |
| `db/session.py` | Creates the configured SQLAlchemy engine and session factory. |
| `core/config.py` | Loads database/storage, model selection, fanout, summary mode, upload/media limits, transcription provider, and RabbitMQ settings from environment configuration. |
| `providers/pipeline_client.py` | Builds the OpenAI-compatible client used for splits, grouping, and vision, with tracing and configured timeout. |
| `utils/model_limits.py` | Shared model-call pacing/concurrency control and bounded rate-limit retries. This reduces bursts; it cannot create provider quota. |
| `utils/tracing.py` | LangSmith tracing and safe SDK-result serialization. Traces can include source text and model outputs; audio bytes and local audio paths are omitted from transcription trace inputs. |
| `utils/observability.py` | Structured logs, request IDs, exception classification, and user-friendly failure messages. |
| `utils/shutdown.py` | Cooperative cancellation on shutdown so new model work stops and unfinished work can resume. An active SDK/local-model call may need time to return. |

Project-root `compose.yaml` runs the API, broker, and worker together and shares database/uploads. `rabbitmq.conf` sets the long-job acknowledgement timeout. `backend/Dockerfile` installs FFmpeg over HTTPS and optionally local Whisper. `backend/pyproject.toml` and `uv.lock` declare and lock dependencies; `.env.example` documents configuration.

The frontend files `src/services/api.ts`, `src/types/learning.ts`, `src/features/workspace/use-workspace.ts`, and `src/features/workspace/components/materials.tsx` respectively call upload/retry endpoints, define material-status types, poll processing updates, and display upload/status/retry controls.

## What remains to verify before moving to planning

- Meaningful boundaries on a real document: labels, answer options, examples, and their explanations should remain together when dependent.
- Complete source coverage and correct page/timestamp attribution through splitting and clustering.
- Resume behavior when extraction, recursive splitting, summaries, or grouping fails.
- Model-call count and duration. Summaries are local by default, but splits, grouping, and vision still consume model tokens.
- Quality of image interpretation and real audio transcription. Structured output checks shape/completeness; it does not prove factual accuracy.

Relevant regression files are `tests/test_ingestion.py`, `test_original_pipeline.py`, `test_word_boundaries.py`, `test_vision.py`, `test_text_rank.py`, `test_local_transcription.py`, `test_ingestion_jobs.py`, `test_ingestion_queue.py`, `test_model_limits.py`, `test_shutdown.py`, and `test_tracing.py`.


## Real-PDF validation

See ../../MVP_VALIDATION.md (project-root MVP_VALIDATION.md) for the verified live RabbitMQ run. Splitting now explicitly distinguishes a shared subject from separate substantive subsections. The processing signature is v2. The real four-page PDF produced a complete source-preserving hierarchy; the plan and contextual chat were subsequently verified too.


## Oversized-cluster repair

Model clusters may initially exceed the configured fanout. They are passed to the original recursive repair instead of being rejected at batch parsing. Complete, source-preserving intermediate groups can be cached even when oversized. Regrouping that produces only singleton groups or keeps the entire unchanged child set in one oversized group is rejected to prevent infinite recursion. The 40-page exam PDF completed with 198 nodes, 137 leaves, depth 6, and full source coverage; the repair resumed from saved summaries rather than repeating extraction or splitting.

## Focused learning after ingestion
Planning reads every available leaf outline with its ancestor headings and stable source ID across ready documents. It infers essential concepts, prerequisites, and optional depth from the material and learner goal, without requiring a separate syllabus. Source exclusions remain respected. Oversized outlines fail visibly rather than silently dropping late topics. Guides retrieve original passages, prioritize plan citations, merge repetition, and retain examples and context; deeper content remains accessible through chat. Refresh existing plans and generate new guides to apply the new behaviour.
