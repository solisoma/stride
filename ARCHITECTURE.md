# Stride architecture

## Monorepo boundaries
`backend/` and `frontend/` are independent applications with separate dependency manifests, lockfiles, environments, and run commands. They communicate through HTTP. Documentation is shared at the repository root. Backend imports start at `api`, `core`, `db`, `pipeline`, `providers`, `retrieval`, or `utils`.

```text
learnforward/
  backend/
    api/main.py                 # App factory, uploads, guides
    api/routes/accounts.py      # Account/session endpoints and legacy import
    api/routes/journey_extras.py # Plan, practice, chat, source decisions, history
    api/schemas/                # Request contracts
    api/services/               # Authentication, authorization, learning loop
    core/                       # Settings
    db/                         # Pluggable persistence
    pipeline/                   # Local ingestion models, hierarchy, media parsers
    retrieval/                  # Keyword-ranked hierarchy traversal
    providers/                  # Pluggable generation/transcription adapters
    utils/                      # Citation validation
    tests/
    pyproject.toml
    uv.lock
    .env.example
  frontend/
    src/app/                    # Next.js App Router
    src/components/             # Account form, sources, comparison UI
    src/services/               # Typed HTTP client
    src/hooks/                  # Account/session and selected journey state
    src/types/
    package.json
    package-lock.json
    next.config.ts
  PRD.md
  USER_FLOW.md
  LEARNING_RULES.md
  README.md
```

## Commands
Inside `backend/`: `uv sync`; `uv run python -m uvicorn api.main:app --reload --port 8001`.
Tests: `uv run python -m unittest discover -s tests -v`.
Inside `frontend/`: `npm.cmd install`; `npm.cmd run dev`. Checks: `npm.cmd run typecheck`, `npm.cmd run build`.

## Adapted components
The legacy project's ingestion, media segmentation, Branch hierarchy, retrieval, and evidence/session patterns informed this implementation. All needed models are local; there are no runtime imports from the legacy backend. The original recursive semantic splitter, summary rollup, clustering, checkpoints, and model router are now adapted locally. Trees are saved in Stride storage and reused during retrieval.

## Authentication and ownership
Email/password registration and login create server-side sessions. Passwords use salted scrypt; only SHA-256 session-token hashes are stored. Sessions expire after seven days and logout revokes the current session. Cookies are HttpOnly/SameSite=Lax; enable `SESSION_SECURE` for HTTPS. Mutation endpoints require a custom request header; no cross-origin CORS is enabled. Login/register throttling is per process.

Every journey endpoint checks account ownership. Prototype token-header access is removed. An authenticated user may explicitly claim an unowned legacy journey by proving its old capability token. New tables are additive, preserving old records without altering their schema. Production account recovery, verified email, MFA, shared throttling, and lifecycle migrations remain pending.

## Persistence
Existing Journey, Document, Activity, and Attempt records store journeys, passages, guides/questions, and answers/feedback. New tables store User, LoginSession, Ownership, JourneyState, Topic, AttemptMeta, ChatMessage, and SourceReview. Attempt metadata includes timestamp, submission ID, support status, and material revision. Guides/questions keep their evidence snapshot and revision. APIs retrieve saved guides and chat across sessions.

## Upload and plan refresh
Each uploaded file adds to its journey. The frontend allows multiple selections and uploads sequentially with partial-failure reporting. Successful extraction is committed before planning; AI failure leaves the document saved and the plan marked for retry. Ready materials increment material revision, rebuild topic maps across ready documents, and preserve prior topics and attempts. Existing topics are matched by normalized title; removed topics become inactive rather than deleted. Renamed topics retain historical attempts under the earlier title, not an invented equivalence.

Plans sample passages per document (bounded input), so coverage is provisional. Old guides remain accessible with a stale marker. Old questions cannot be submitted after a material becomes ready or a source decision changes the material revision; answer history remains available. Model generation receives previous scenarios and recent feedback to target gaps and reduce repetition, without claiming repetition is impossible.

## Adaptive learning loop
Failed or ambiguous answers trigger targeted revision and fresh scenarios. Immediate follow-ups after correction are supported practice. Independent correct attempts schedule reassessment after one day; delayed successful practice earns a seven-day interval and the label `retained_in_practice`, never guaranteed mastery. Existing history from before metadata was recorded is preserved and labeled accordingly. Prerequisite gaps are prioritized when the plan supplies them. Submission IDs prevent duplicate saved attempts on retries. The learner may choose another topic or answer format.

## Chat and source disagreements
Chat retrieves current materials, includes a bounded window of saved conversation, and persists source-linked replies. Source checks are AI-assisted inconsistency detection, not external factual verification. Concerns must quote cited passages accurately. The UI shows the source claim, unverified alternative, reasoning, and evidence. Learners choose source/alternative/unresolved/excluded and may add a note. Decisions change future retrieval context and trigger a plan refresh; selected interpretations are not relabeled verified. Exclusion applies to the entire cited passage. Unresolved conflicts stay visible. No automatic web verification is implemented.

## Configuration
Load `backend/.env` without overriding process variables. Database resolution: `LEARNFORWARD_DATABASE_URL`, then `DATABASE_URL`, then backend-local SQLite. SQLAlchemy databases require matching installed drivers; only SQLite has been tested. Upload storage is configured by `LEARNFORWARD_STORAGE`; relative paths resolve from backend cwd.

`LLM_API_KEY`, `LLM_BASE_URL`, and `LEARNING_MODEL` configure generation. `TRANSCRIPTION_MODEL` is separate; optional transcription credentials/URL fall back to the learning connection. Providers/transcribers can be injected into the app factory. Streaming, tools, automatic capability discovery, and provider-specific SDK adapters are pending. No silent provider fallback exists.

Default upload limits: 20 MiB and 1,800 seconds. PDF, DOCX, TXT, Markdown, MP3, WAV, M4A, MP4, AVI, MOV, MKV are accepted. Media dependencies are optional uv extras; FFmpeg is a system dependency. Transcription uses 30-second temporary segments with timestamps and rejects failed/empty segments. Embedded PDF/DOCX images are analyzed by the configured vision model; video visuals are not analyzed. Code is reviewed but not executed.

## Remaining limits and validation
Generation remains synchronous. Content-type validation, streaming/cancellation, semantic retrieval, exhaustive syllabus mapping, and learner efficacy studies remain pending. Citation IDs and concern quotes are checked; this does not establish every generated claim's accuracy. Automated tests use simulated AI/transcription, including account isolation, saved state, revision invalidation, retries, retention scheduling, source decisions, and outage recovery. Live providers, real media decoding, and human learning outcomes require separate evaluation.

## Administrator role
An additive `lf_admin_roles` table grants admin status independently of the user schema. Only the local `scripts.create_admin` bootstrap creates admins; public registration cannot elevate roles. Admin-specific sign-in uses the same hashed-password/session flow, denying non-admin credentials. `/admin/me` enforces administrator access on the server. Admin membership is checked against the database on each role lookup. This does not bypass journey ownership checks or add a management dashboard. Passwords are entered through getpass, not command-line arguments or committed settings.

## Unified learning workspace
Practice and follow-up chat share one Learn workspace: scenarios, answers, and correction sit beside the saved conversation, with a stacked layout on small screens. Asking about a mistake prefills and focuses the chat composer without leaving the scenario. Dashboard navigation includes real resource/attempt/topic counts, recent activity, a learning path, and the next recommendation; no progress metrics are fabricated.

Study now pairs the focused guide with the same journey conversation used by Practice. Chat sends only an owned activity ID; the backend resolves guide/scenario context and validates journey ownership. Hidden question rubrics are not passed into pre-answer chat. Earlier guides are identified as stale, and replies retrieve current sources.

## Tailwind styling
The Next.js App Router frontend uses Tailwind CSS v4 through @tailwindcss/postcss. Shared styles use Tailwind utilities via @apply in the components layer; JSX can use utilities directly. Theme variables, gradients, complex borders, and browser-specific dialog details retain native CSS where appropriate. Existing breakpoints and expandable-chat behavior are preserved.

## Modular workspace frontend
`src/app/page.tsx` only composes the workspace. `src/features/workspace/use-workspace.ts` owns journey state/loading and shared actions; `context.tsx` shares it across feature components, and `config.ts` holds navigation/goal labels. Separate components handle the shell, overview, journey setup, materials, learning plan, source reviews, study, practice, progress, legacy import, and notifications. Generic chat/auth/source components remain in `src/components/`; API calls stay in `src/services/`, and guide export lives in `src/utils/download-guide.ts`. Use `npm.cmd run format` for consistent formatting.

## App Router URLs
`/` is the public landing page; `/login` handles learner/admin sign-in. `/dashboard` lists saved journeys; `/dashboard/new` creates a journey. `/dashboard/journeys/[id]` is the journey overview, with `/materials`, `/plan`, `/study`, `/practice`, and `/progress` child pages. `dashboard/layout.tsx` provides shared account/workspace state and navigation; the journey layout verifies the journey is available in the signed-in user's list. The URL determines journey/section selection, including refresh and back/forward. API ownership checks remain the security boundary. Chat drafts and temporary learning UI stay in the persistent dashboard provider. Anonymous dashboard visits redirect to login with a return path.

## Restored original ingestion and retrieval
Stride now carries an independent adaptation of the original pipeline: TreeBuilder recursively splits logical sections, rolls up model-generated summaries, and groups sections semantically with bounded fanout. StatefulDocumentParser checkpoints source parsing and resumes interrupted attempts. StatefulMediaParser caches transcripts, maps semantic chunks to timestamps, and passes them through the same tree pipeline. Embedded PDF/DOCX images use vision extraction. Serialization preserves parent relationships without circular JSON.

Semantic trees persist in `lf_document_trees`; checkpoint state uses `lf_ingestion_checkpoints`. Query retrieval runs the original RouterResponse/ChildDecision traversal with parallel branch drilling; keyword ranking is removed. Original agentic search and drill-event generators remain available in the retriever. Learning endpoints use original source leaves for citation evidence even when a router summary helps navigation. Coverage planning deliberately enumerates source leaves rather than filtering by query relevance.

Existing document records are reindexed on first learning query, preserving their passage/citation IDs and saved progress. New uploads store semantic leaves and their tree together. No legacy backend imports, database connections, or environment loading are used.

Configure `TREE_BUILDER_MODEL`, `RETRIEVAL_MODEL`, and `VISION_MODEL` independently; blank values use the learning/tree model as appropriate. `TREE_FANOUT` defaults to five. `OLLAMA_ENABLED` selects a local OpenAI-compatible pipeline connection; other providers use LLM_API_KEY/LLM_BASE_URL. Pipeline clients can be injected for other compatible implementations and tests. Selected models must support the structured-output/vision features used by the pipeline.

Model failures do not silently switch to keyword retrieval. Invalid splits, missing source coverage, non-reducing clusters, and invalid source indices are rejected. Checkpoints are retained on cancellation or processing failure. The legacy media generator handoff, circular serialization, Windows console output, and unbounded split/clustering failure paths are corrected. API uploads remain synchronous: streamed parser/drill events are available internally but not yet connected to frontend progress/cancellation controls.

Tests exercise the real semantic algorithms with simulated model responses. Live model quality, image interpretation, and real media decoding still need separate validation.

## Failure diagnostics

Backend logs are JSON lines in `backend/logs/backend.jsonl` and the terminal. Files rotate at 5 MB with five backups. `LOG_LEVEL` controls verbosity and `LOG_DIR` overrides storage. Every API response has `X-Request-ID`; errors also return `error.code`, `error.request_id`, and the failing stage when known. Search that ID in logs for the operation, exception types, stack locations, response status, and elapsed time. Model credentials, timeout, quota, endpoint, malformed response, and ingestion/retrieval errors have distinct explanations. Saved uploads report plan-refresh failures without losing the material.

Frontend logs structured API failures, runtime errors, and unhandled promises to the browser console. API errors on screen include the same request reference. Next.js error boundaries provide retry controls. Browser logs are local console output, not a remote monitoring service. Request bodies, learner answers, document text, passwords, cookies, API keys, and raw provider exception messages are excluded. Backend access logs use route templates to avoid capturing user-supplied URL content. Uvicorn's own access logs can be disabled with `--no-access-log` to avoid duplicate unstructured request logs.

User-facing failures use plain language with a support reference. Technical error codes are kept out of visible notifications; failure stages, provider configuration guidance, and sanitized diagnostics remain in backend logs. The browser API client masks server-error details defensively so an unexpected technical message cannot appear in the learner interface.

## LangSmith model tracing

All production OpenAI-compatible chat calls (semantic splits, summaries, clustering, vision, routing, and coaching) use the LangSmith OpenAI wrapper. Transcription uses a traceable LLM operation and records its transcript without uploading the audio file to tracing. Traces include request IDs and component labels. `LANGSMITH_TRACING` defaults to true; configure `LANGSMITH_API_KEY` and `LANGSMITH_PROJECT` in backend/.env. `LANGSMITH_ENDPOINT` supports alternate regions. With tracing enabled, a missing key raises a configuration error rather than silently skipping traces. Set tracing false only for offline tests or deliberate disabling. Prompts, source excerpts, learner answers, and model outputs are sent to LangSmith for developer inspection; they are not frontend logs. Keep the LangSmith project private. Simulated clients in unit tests do not emit real traces.

## Source-preserving semantic boundaries

Python numbers whitespace-delimited source words and sends positions to the model. The model returns only section titles and start_word offsets. Python validates a first start at zero, strictly increasing positions, nonempty titles, and positions within the source; it slices original character offsets, including original PDF ligatures, punctuation, and whitespace. Invalid boundary responses keep the complete input as one section and log a warning. Provider failures still surface normally. A recursion limit retains the current section intact. Existing saved trees remain usable; new ingestion and indexing use this boundary protocol.

## Model request limits

Each extracted page or segment is split recursively using numbered-word boundaries until the model identifies atomic sections. Intermediate branches retain their children and parent links. Depth-first traversal avoids nested thread pools. The depth limit preserves remaining source text and records split_stop_reason=depth_limit. Summaries and clustering still make calls. A shared process-wide gate limits concurrent requests and spaces starts using LLM_MAX_CONCURRENCY (default 1) and LLM_MIN_INTERVAL_SECONDS (default 1). Transient rate limits use bounded exponential backoff with jitter and numeric Retry-After, sharing cooldown with all threads. LLM_RATE_LIMIT_RETRIES defaults to 2; SDK automatic retries are disabled to prevent duplicate retry layers. Quota/billing failures and requested waits beyond 60 seconds are surfaced immediately. Limits are per backend process; multiple workers need a distributed limiter. Provider token quotas still apply; increase the interval to match request limits.

## Cooperative server shutdown

During production lifespan, SIGINT/SIGTERM handlers set the shared shutdown event before forwarding to Uvicorn, so cancellation begins before request draining. Model semaphore waits poll for cancellation; rate pacing/backoff uses interruptible event waits. Recursive tree work checks shutdown before scheduling more model calls, and upload parsers share the event. SDK calls check cancellation before/after execution. LLM_TIMEOUT_SECONDS defaults to 30 and bounds SDK network waits; synchronous HTTP requests already in progress cannot be interrupted immediately, and SDK timeouts apply to network phases rather than a strict total deadline. Parser checkpoints remain available through cancelled work. Signal handlers are restored at shutdown and are skipped when lifespan runs off the main thread (TestClient).

## Structured image extraction

Vision calls use SDK parse with ImageExtraction: kind, visible_text, and diagram_explanation. Text images contribute transcription only; diagrams contribute grounded explanations; mixed images contribute both. Decorative images are skipped, unreadable images produce a warning, and missing required content fails validation. Source wrappers retain the reminder to verify image-derived content against the original image. Structured output controls the response shape; factual extraction still requires quality evaluation.

## Local summary experiment

SUMMARY_BACKEND defaults to textrank; llm retains the previous model-generated summary path for comparison. Local summaries use scikit-learn TF-IDF sentence similarity and iterative TextRank to select two original sentences, preserving source order. Large inputs are reduced in bounded batches. Leaves and parent rollups use local summaries; cluster-node summaries retain all child titles to support routing. Semantic splitting, cluster assignments, routing, vision, and learner-facing coaching still use their configured LLMs. Existing nonempty summaries are reused; stored trees are not automatically rebuilt. The first evaluation target is a 5?10-page document; accuracy and cost reduction on live documents have not yet been benchmarked. Sentence segmentation is heuristic, especially for abbreviations, code, and languages without whitespace. No model downloads or API calls are used for local summaries.


## Persistent ingestion

Uploads save the original file and a queued document record immediately (HTTP 202). Run the ingestion worker in a second backend terminal:

```powershell
uv run python -m scripts.ingestion_worker
```

RabbitMQ delivers one ingestion job at a time to the worker. Materials displays queued, processing, ready, and failed states and offers retry for failed jobs. Only ready documents enter retrieval and learning plans. Plan refresh failure does not discard a ready document.

Completed extraction, page processing, model results, and tree phases are checkpointed in the database. Failed processing keeps the file and checkpoints; retry reuses saved work. Worker restart requeues interrupted jobs. Successful ingestion clears processing checkpoints only after saving the ready tree. Changing model or pipeline configuration invalidates processing caches. An exclusive worker lock prevents competing recovery processes. Existing document records without job records remain usable.


## RabbitMQ ingestion

From the project root, start the API, broker, and worker together:

```powershell
docker compose up --build -d
```

Keep running the frontend with its existing Next.js command. The API remains at localhost:8001. Broker administration is at http://localhost:15672 (local defaults: learnforward / learnforward-local). Set RABBITMQ_PASSWORD for a different broker password; URL-encode reserved characters in AMQP credentials. Docker Desktop must be running.

The Compose services share backend uploads and the existing SQLite database. Stop the locally running API and old worker before starting Compose. COMPOSE_DATABASE_URL can select an external database. New containers read backend/.env for model credentials; that file is excluded from the image. Local model endpoints using localhost must use a Docker-reachable address instead.

Uploads and retry requests atomically save an outbox message alongside their database updates. The worker's dispatcher sends persistent messages to a durable RabbitMQ queue using publisher confirms, then removes the outbox record. Broker outages leave dispatch records available for the next attempt. Messages contain only version and document ID.

A separate processing thread keeps RabbitMQ heartbeats responsive during long ingestion. Prefetch is one; acknowledgements occur after readiness, terminal failure, or durable retry scheduling. Duplicate deliveries are guarded by the database's queued-to-processing transition. Failed processing receives up to INGESTION_MAX_ATTEMPTS (default 3) total attempts, with 30-second retry delays. Exhausted jobs remain failed with the existing manual retry button; manual retry starts a new attempt budget and preserves checkpoints. Interrupted jobs resume on worker restart. This MVP deliberately permits one ingestion worker per storage directory.

Native development remains available: start RabbitMQ, configure RABBITMQ_URL, then run the API and `uv run python -m scripts.ingestion_worker`. Check logs using `docker compose logs -f worker api`. Restarting containers preserves RabbitMQ messages, uploads, and database checkpoints.


## Local Whisper transcription

The transcription factory selects the existing OpenAI-compatible API provider by default. To run locally, set `TRANSCRIPTION_PROVIDER=whisper`, `WHISPER_MODEL=base`, and `WHISPER_DEVICE=cpu` in backend/.env. Leave WHISPER_LANGUAGE empty for detection or specify a language code. Local transcription does not require a transcription API key; other learning operations retain their configured model provider.

For native execution, run `uv sync --extra local-whisper` and install FFmpeg on the host. For Docker, set `$env:INSTALL_LOCAL_WHISPER="true"` in PowerShell before `docker compose up --build -d`. The opt-in extra includes PyTorch and increases dependency/image size. CUDA requires a GPU-enabled runtime; the standard Compose setup uses CPU.

Whisper loads only when audio is processed, downloads weights on first use, and reuses the model across segments. Weights persist in backend/.whisper (the shared /data volume under Docker). Successful segment transcripts use existing ingestion checkpoints. Provider/model/language changes invalidate processing caches. LangSmith records local transcript text when tracing is enabled, without audio bytes or local paths. A real lecture accuracy/speed benchmark is still needed before selecting local Whisper as the default.



## Stride branding compatibility

The project is named Stride. STRIDE_DATABASE_URL and STRIDE_STORAGE are preferred; the old LEARNFORWARD_* settings remain supported. Existing SQLite filenames, session cookies, browser storage keys, RabbitMQ queue names and credentials, and Docker project resources retain their current identifiers to preserve data and access. The existing project folder remains at C:/Users/hp/projects/learnforward.


## Ingestion development

Ingestion is developed and tested directly in backend/pipeline and its backend services. The standalone document-tree lab has been removed. See backend/pipeline/INGESTION.md for the processing flow and file responsibilities. Resolve extraction, hierarchy, source preservation, and recovery issues before changing learning-plan generation.
