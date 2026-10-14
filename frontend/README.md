# Stride frontend

Next.js App Router and TypeScript. Run `npm.cmd install`, then `npm.cmd run dev` from this folder. Open http://localhost:3000; FastAPI runs separately on port 8001.

Optional `.env.local` configures server-only `BACKEND_URL`. The `/api/backend` rewrite forwards requests and cookies. The proxy accepts 25 MiB including multipart overhead and allows long synchronous transcription requests; backend limits still apply.

The UI includes account registration/login/logout, a saved journey selector, multi-file uploads, learning maps and next steps, saved guides/downloads, scenarios and corrections, persistent chat, source comparison/decision cards, and progress history. Failed uploads stay selected for retry. Session credentials are HttpOnly cookies; local storage remembers only the selected journey ID. Earlier prototype journeys can be imported explicitly using a locally stored legacy token.

`src/app/` contains routes/styles, `src/components/` shared UI, `src/services/` API calls, `src/hooks/` account/journey state, and `src/types/` contracts. AI secrets remain in the backend.

Checks: `npm.cmd run typecheck` and `npm.cmd run build`. Live generation needs backend model configuration. Cross-device progress uses the same account; unsent answer drafts are not synced.

Choose Admin sign in for administrator credentials. Bootstrap the account with the backend CLI documented in the root README. No public admin registration or management dashboard exists.

## Unified learning workspace
Practice and follow-up chat share one Learn workspace: scenarios, answers, and correction sit beside the saved conversation, with a stacked layout on small screens. Asking about a mistake prefills and focuses the chat composer without leaving the scenario. Dashboard navigation includes real resource/attempt/topic counts, recent activity, a learning path, and the next recommendation; no progress metrics are fabricated.

Study now pairs the focused guide with the same journey conversation used by Practice. Chat sends only an owned activity ID; the backend resolves guide/scenario context and validates journey ownership. Hidden question rubrics are not passed into pre-answer chat. Earlier guides are identified as stale, and replies retrieve current sources.

The coach is opened with the floating Ask your coach button in Study/Practice. Closing it preserves the conversation and draft. The panel supports Escape, backdrop dismissal, native dialog focus trapping, and a mobile sheet layout. Reading/practice occupy full width while chat is closed.

## Tailwind styling
The Next.js App Router frontend uses Tailwind CSS v4 through @tailwindcss/postcss. Shared styles use Tailwind utilities via @apply in the components layer; JSX can use utilities directly. Theme variables, gradients, complex borders, and browser-specific dialog details retain native CSS where appropriate. Existing breakpoints and expandable-chat behavior are preserved.

## Modular workspace frontend
`src/app/page.tsx` only composes the workspace. `src/features/workspace/use-workspace.ts` owns journey state/loading and shared actions; `context.tsx` shares it across feature components, and `config.ts` holds navigation/goal labels. Separate components handle the shell, overview, journey setup, materials, learning plan, source reviews, study, practice, progress, legacy import, and notifications. Generic chat/auth/source components remain in `src/components/`; API calls stay in `src/services/`, and guide export lives in `src/utils/download-guide.ts`. Use `npm.cmd run format` for consistent formatting.

## App Router URLs
`/` is the public landing page; `/login` handles learner/admin sign-in. `/dashboard` lists saved journeys; `/dashboard/new` creates a journey. `/dashboard/journeys/[id]` is the journey overview, with `/materials`, `/plan`, `/study`, `/practice`, and `/progress` child pages. `dashboard/layout.tsx` provides shared account/workspace state and navigation; the journey layout verifies the journey is available in the signed-in user's list. The URL determines journey/section selection, including refresh and back/forward. API ownership checks remain the security boundary. Chat drafts and temporary learning UI stay in the persistent dashboard provider. Anonymous dashboard visits redirect to login with a return path.
