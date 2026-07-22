export interface HealthResponse {
  status: "ok";
  service: string;
}

export interface ReadyResponse {
  status: "ready";
  index_format_version: string;
  chunks: number;
}

export interface DocumentResponse {
  id: string;
  title: string;
  version: string;
  effective_date: string;
  category: string;
  language: string;
}

export interface DocumentsResponse {
  documents: DocumentResponse[];
}

export interface ChatRequest {
  question: string;
}

export interface SourceResponse {
  document_id: string;
  title: string;
  version: string;
  page: number;
  section: string | null;
  excerpt: string;
}

export interface ChatResponse {
  answer: string;
  answerable: boolean;
  sources: SourceResponse[];
  request_id: string;
  latency_ms: number;
}

export interface ApiErrorPayload {
  detail: string;
  request_id?: string | null;
  latency_ms?: number | null;
}
