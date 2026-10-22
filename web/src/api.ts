import { EventParser } from './sse';
import type { ComparisonResult, ConversationSummary, DocumentInfo, Grounded, Message, Method, Passage } from './types';

let csrf = '';

export class ApiError extends Error {}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const isForm = options.body instanceof FormData;
  const response = await fetch(path, {
    ...options,
    headers: { ...(isForm ? {} : { 'Content-Type': 'application/json' }), 'X-CSRF-Token': csrf },
  });
  if (response.status === 204) return undefined as T;
  const data = await response.json().catch(() => ({ error: 'Unexpected server response.' }));
  if (!response.ok) throw new ApiError(data.error || 'Request failed.');
  return data as T;
}

export interface Session {
  provider: string;
  methods: Method[];
}

export async function startSession(): Promise<Session> {
  const data = await request<Session & { csrf: string }>('/api/session');
  csrf = data.csrf;
  return data;
}

export const listConversations = () =>
  request<{ conversations: ConversationSummary[] }>('/api/conversations').then((d) => d.conversations);

export const createConversation = (title = 'New conversation') =>
  request<ConversationSummary>('/api/conversations', { method: 'POST', body: JSON.stringify({ title }) });

export const renameConversation = (id: string, title: string) =>
  request<ConversationSummary>(`/api/conversations/${id}`, { method: 'PATCH', body: JSON.stringify({ title }) });

export const deleteConversation = (id: string) => request<void>(`/api/conversations/${id}`, { method: 'DELETE' });

export async function loadConversation(id: string): Promise<{ title: string; messages: Message[] }> {
  const data = await request<{
    title: string;
    messages: { role: 'user' | 'assistant'; content: string }[];
    grounded_turns: Record<string, Grounded>;
  }>(`/api/conversations/${id}`);
  let turn = 0;
  const messages = data.messages.map((m) => {
    if (m.role !== 'assistant') return m;
    turn += 1;
    return { ...m, grounded: data.grounded_turns[String(turn)] };
  });
  return { title: data.title, messages };
}

export const listDocuments = () => request<{ documents: DocumentInfo[] }>('/api/documents').then((d) =>
  d.documents.map((doc) => ({ ...doc, metadata: typeof doc.metadata === 'string' ? JSON.parse(doc.metadata) : doc.metadata })));

export function importDocument(file: File) {
  const form = new FormData();
  form.append('file', file);
  return request<DocumentInfo>('/api/documents', { method: 'POST', body: form });
}

export const importDemo = () => request<DocumentInfo>('/api/documents/demo', { method: 'POST', body: '{}' });
export const retryDocument = (id: string) => request<DocumentInfo>(`/api/documents/${id}/retry`, { method: 'POST', body: '{}' });
export const removeDocument = (id: string) => request<void>(`/api/documents/${id}`, { method: 'DELETE' });
export const loadSource = (documentId: string, id: string) =>
  request<Passage & { text: string }>(`/api/documents/${documentId}/sources/${id}`);

export const compare = (documentId: string, question: string) =>
  request<ComparisonResult>('/api/comparisons', { method: 'POST', body: JSON.stringify({ document_id: documentId, question }) });

export interface StreamHandlers {
  onStep(label: string): void;
  onEvidence(passages: Passage[]): void;
  onToken(text: string): void;
}

/** POST a message and consume the server-sent event stream until `done` or `error`. */
export async function sendMessage(
  conversationId: string,
  body: { message: string; document_id?: string; method?: Method },
  handlers: StreamHandlers,
): Promise<{ reply: string; grounded?: Grounded }> {
  const response = await fetch(`/api/conversations/${conversationId}/messages`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': csrf },
    body: JSON.stringify(body),
  });
  if (!response.ok || !response.body) {
    const data = await response.json().catch(() => ({}));
    throw new ApiError(data.error || 'Request failed.');
  }
  const parser = new EventParser();
  const reader = response.body.pipeThrough(new TextDecoderStream()).getReader();
  for (;;) {
    const { value, done } = await reader.read();
    if (done) break;
    for (const { event, data } of parser.feed(value)) {
      const payload = data as Record<string, unknown>;
      if (event === 'step') handlers.onStep(payload.label as string);
      else if (event === 'evidence') handlers.onEvidence(payload.passages as Passage[]);
      else if (event === 'token') handlers.onToken(payload.text as string);
      else if (event === 'error') throw new ApiError(payload.error as string);
      else if (event === 'done') return payload as unknown as { reply: string; grounded?: Grounded };
    }
  }
  throw new ApiError('The connection closed before the reply finished. Reload to see whether it was saved.');
}

export const listComparisons = () =>
  request<{ comparisons: { id: string; question: string }[] }>('/api/comparisons').then((d) => d.comparisons);
export const loadComparison = (id: string) => request<ComparisonResult>(`/api/comparisons/${id}`);
