export type Method = 'rag' | 'rerank' | 'scoped' | 'okf' | 'agentic';

export const METHOD_INFO: Record<Method, { label: string; hint: string }> = {
  rag: { label: 'RAG', hint: 'Hybrid search (BM25 + embeddings), one model call' },
  rerank: { label: 'Rerank', hint: 'Top-20 hybrid hits, model keeps the best five' },
  scoped: { label: 'Scoped', hint: 'Model picks sections from the table of contents, hybrid search ranks inside them' },
  okf: { label: 'OKF', hint: 'Model navigates the outline to passages; no vector search' },
  agentic: { label: 'Agent', hint: 'LangGraph plans, retrieves, checks sufficiency and retries once' },
};

export interface Passage {
  id: string;
  page: number;
  section?: string;
  printed_page?: string | null;
  text?: string;
}

export interface Grounded {
  method: Method;
  document_id: string;
  reply: string;
  citations: Passage[];
  evidence: Passage[];
  steps: string[];
  seconds: number;
  model_calls: number;
  input_tokens: number;
  output_tokens: number;
  source_removed?: boolean;
}

export interface Message {
  role: 'user' | 'assistant';
  content: string;
  grounded?: Grounded;
  // Live state while a reply streams in.
  pending?: boolean;
  steps?: string[];
  evidence?: Passage[];
  error?: string;
}

export interface ConversationSummary {
  id: string;
  title: string;
}

export interface DocumentInfo {
  id: string;
  title: string;
  status: 'queued' | 'indexing' | 'ready' | 'failed';
  error: string | null;
  metadata: { pages?: number; chunks?: number; embedded?: number; seconds?: number };
}

export interface ComparisonResult {
  id: string;
  question: string;
  document_id: string;
  results: Record<string, ({ status: 'complete' } & Grounded) | { status: 'failed'; error: string }>;
}
