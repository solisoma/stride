import type { Journey, Goal, Guide, Question, Feedback, Progress, User, Plan, Material, ChatMessage, SourceReview, SavedActivity } from '@/types/learning';
import { logger } from '@/utils/logger';
export class ApiError extends Error {
  constructor(message: string, public status: number, public code: string, public requestId: string) {
    super(`${message} Reference: ${requestId}`);
    this.name = 'ApiError';
  }
}
async function request<T>(path: string, _journey?: Journey, body?: object | FormData): Promise<T> {
  const correlation = crypto.randomUUID();
  const method = body ? 'POST' : 'GET';
  const started = performance.now();
  const headers: Record<string, string> = {'X-Stride-Request': '1', 'X-LearnForward-Request': '1', 'X-Request-ID': correlation};
  if (body && !(body instanceof FormData)) headers['Content-Type'] = 'application/json';
  let response: Response;
  try {
    response = await fetch(`/api/backend${path}`, { method, headers, body: body instanceof FormData ? body : body ? JSON.stringify(body) : undefined, cache: 'no-store', credentials: 'same-origin' });
  } catch {
    logger.error('api_network_failed', {method, path, requestId: correlation, durationMs: Math.round(performance.now() - started)});
    throw new ApiError('Could not connect. Check your internet connection and try again.', 0, 'NETWORK_ERROR', correlation);
  }
  const data = await response.json().catch(() => null);
  const requestId = response.headers.get('X-Request-ID') || data?.error?.request_id || correlation;
  const fields = {method, path, status: response.status, requestId, durationMs: Math.round(performance.now() - started)};
  if (!response.ok) {
    const code = typeof data?.error?.code === 'string' ? data.error.code : `HTTP_${response.status}`;
    logger[response.status >= 500 ? 'error' : 'warn']('api_request_failed', {...fields, code});
    const message = response.status >= 500
      ? code === 'PROVIDER_TIMEOUT' ? 'This is taking longer than expected. Please try again.'
        : code === 'PROVIDER_RATE_LIMIT' ? 'Stride is busy right now. Please try again in a few minutes.'
        : 'We could not complete this request right now. Please try again later.'
      : code === 'CSRF_HEADER_MISSING' ? 'Please refresh this page and try again.'
        : typeof data?.detail === 'string' ? data.detail : 'Check your information and try again.';
    throw new ApiError(message, response.status, code, requestId);
  }
  if (data === null) {
    logger.error('api_invalid_response', fields);
    throw new ApiError('We could not load this information. Please try again.', response.status, 'INVALID_RESPONSE', requestId);
  }
  logger.debug('api_request_completed', fields);
  return data as T;
}
const path = (j: Journey) => `/journeys/${j.id}`;
export const api = {
  me: () => request<User>('/auth/me'),
  login: (email: string, password: string) => request<User>('/auth/login', undefined, { email, password }),
  adminLogin: (email: string, password: string) => request<User>('/auth/admin/login', undefined, { email, password }),
  register: (name: string, email: string, password: string) => request<User>('/auth/register', undefined, { name, email, password }),
  logout: () => request<{ ok: boolean }>('/auth/logout', undefined, {}),
  journeys: () => request<Journey[]>('/journeys'),
  claim: (journey_id: number, access_token: string) => request<Journey>('/journeys/claim', undefined, { journey_id, access_token }),
  retryDocument: (j: Journey, id: number) => request<Material>(`${path(j)}/documents/${id}/retry`, j, {}),
  documents: (j: Journey) => request<Material[]>(`${path(j)}/documents`, j),
  plan: (j: Journey) => request<Plan>(`${path(j)}/plan`, j),
  rebuild: (j: Journey) => request<Plan>(`${path(j)}/plan`, j, {}),
  activities: (j: Journey) => request<SavedActivity[]>(`${path(j)}/activities`, j),
  chatHistory: (j: Journey) => request<ChatMessage[]>(`${path(j)}/chat`, j),
  chat: (j: Journey, message: string, activity_id?: number) => request<ChatMessage>(`${path(j)}/chat`, j, { message, activity_id }),
  reviews: (j: Journey) => request<SourceReview[]>(`${path(j)}/reviews`, j),
  decide: (j: Journey, id: number, decision: string, note: string) => request<{plan_error: string | null}>(`${path(j)}/reviews/${id}`, j, { decision, note }),
  create: (goal: Goal, subject: string) => request<Journey>('/journeys', undefined, { goal, subject }),
  upload: (j: Journey, file: File) => { const body = new FormData(); body.append('file', file); return request<Material>(`${path(j)}/documents`, j, body); },
  guide: (j: Journey, topic: string) => request<Guide>(`${path(j)}/guides`, j, { topic }),
  question: (j: Journey, topic: string, format: string) => request<Question>(`${path(j)}/questions`, j, { topic, format }),
  answer: (j: Journey, id: number, answer: string, submission_id: string) => request<Feedback>(`${path(j)}/questions/${id}/answers`, j, { answer, submission_id }),
  progress: (j: Journey) => request<Progress>(`${path(j)}/progress`, j),
};
