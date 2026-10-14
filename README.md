# Stride

A monorepo with independently runnable FastAPI and Next.js applications.

## Backend
Run inside `backend/`:

```powershell
uv sync
uv run python -m uvicorn api.main:app --reload --port 8001
```

Copy `backend/.env.example` to `backend/.env` and configure `LLM_API_KEY`, `LEARNING_MODEL`, and optionally `LLM_BASE_URL`. Transcription uses `TRANSCRIPTION_MODEL` and optional separate credentials/endpoint. Install media dependencies with `uv sync --extra media`; FFmpeg is needed for codecs. PostgreSQL drivers are optional via `--extra postgres`.

API docs: http://localhost:8001/docs. Mutation requests must include `X-Stride-Request: 1`. Register or log in through `/auth/register` or `/auth/login`; subsequent requests use the HttpOnly session cookie. The frontend sends the header/cookie automatically. HTTPS deployments must set `SESSION_SECURE=true`.

## Frontend
Run inside `frontend/`:

```powershell
npm.cmd install
npm.cmd run dev
```

Open http://localhost:3000. Optional `.env.local` can configure `BACKEND_URL`; the default is http://127.0.0.1:8001. Authentication is proxied through the same origin. No model secrets belong in frontend configuration.

## Learning loop
Register/login ? create or resume a journey ? upload multiple materials ? updated topic map ? focused guide ? scenario ? correction ? targeted follow-up ? independent check ? delayed reassessment.

Failed answers prioritize revision. Immediate successful follow-ups are supported practice, not mastery. Independent correct answers schedule a later check (one day initially; seven days after demonstrated delayed success). These intervals are MVP heuristics, not scientifically validated personalization. Plan updates preserve all historical attempts and guides, flag older material revisions, and reject submitting outdated questions.

Chat keeps follow-up explanations with the journey and retrieves current source material. Source concerns compare an exact source quote with a possible alternative. The learner can follow the source, select an unverified alternative, keep both unresolved, or exclude cited passages. Decisions influence future learning and trigger a plan update; they are not factual verification.

## Persistence and upgrades
New additive tables store users, hashed sessions, journey ownership, plans, topic state, attempt metadata, chat, and source decisions. Existing prototype records are retained. A browser with the previous journey token can explicitly import that journey after signing in. Unclaimed journeys are not accessible through old token headers anymore. Saved guides and chat load from the backend; no session credentials are stored in browser local storage.

## Checks
Inside `backend/`: `uv run python -m unittest discover -s tests -v`.
Inside `frontend/`: `npm.cmd run typecheck` and `npm.cmd run build`.

## Current limits
Plans use sampled passages and semantic model routing, so coverage is provisional. AI consistency checks do not externally verify facts. Live AI quality and real media decoding still need evaluation. Upload/AI tasks run synchronously. Password reset, email verification, MFA, shared rate limiting, streaming, cancellation, and comprehensive syllabus coverage remain future work. Code is reviewed without execution.

## Administrator login
Create an admin from `backend/`:

```powershell
uv run python -m scripts.create_admin --email learnforward@gmail.com
```

The command prompts privately for a password (at least 15 characters) and confirmation. No default password is stored in configuration. It refuses existing emails instead of overwriting passwords. On the login page choose **Admin sign in**, or use `/auth/admin/login`. `/admin/me` checks admin authorization. Public registration always creates learners. Admins currently use the same learning UI with an Admin badge; no management dashboard or blanket access to other learners' journeys is implemented.

## Restored original ingestion and retrieval
Stride now carries an independent adaptation of the original pipeline: TreeBuilder recursively splits logical sections, rolls up local TextRank summaries (or configured model summaries), and groups sections semantically with bounded fanout. StatefulDocumentParser checkpoints source parsing and resumes interrupted attempts. StatefulMediaParser caches transcripts, maps semantic chunks to timestamps, and passes them through the same tree pipeline. Embedded PDF/DOCX images use vision extraction. Serialization preserves parent relationships without circular JSON.

Semantic trees persist in `lf_document_trees`; checkpoint state uses `lf_ingestion_checkpoints`. Query retrieval runs the original RouterResponse/ChildDecision traversal with parallel branch drilling; keyword ranking is removed. Original agentic search and drill-event generators remain available in the retriever. Learning endpoints use original source leaves for citation evidence even when a router summary helps navigation. Coverage planning deliberately enumerates source leaves rather than filtering by query relevance.

Existing document records are reindexed on first learning query, preserving their passage/citation IDs and saved progress. New uploads store semantic leaves and their tree together. No legacy backend imports, database connections, or environment loading are used.

Configure `TREE_BUILDER_MODEL`, `RETRIEVAL_MODEL`, and `VISION_MODEL` independently; blank values use the learning/tree model as appropriate. `TREE_FANOUT` defaults to five. `OLLAMA_ENABLED` selects a local OpenAI-compatible pipeline connection; other providers use LLM_API_KEY/LLM_BASE_URL. Pipeline clients can be injected for other compatible implementations and tests. Selected models must support the structured-output/vision features used by the pipeline.

Model failures do not silently switch to keyword retrieval. Invalid splits, missing source coverage, non-reducing clusters, and invalid source indices are rejected. Checkpoints are retained on cancellation or processing failure. The legacy media generator handoff, circular serialization, Windows console output, and unbounded split/clustering failure paths are corrected. API uploads return immediately after saving the file; the separate worker persists processing status for Materials and retains checkpoints for retries.

Tests exercise the real semantic algorithms with simulated model responses. Live model quality, image interpretation, and real media decoding still need separate validation.


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
