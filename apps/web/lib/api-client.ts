import type {
  ApiErrorPayload,
  ChatResponse,
  DocumentsResponse,
  HealthResponse,
  ReadyResponse,
} from "@/types/api";

const DEFAULT_TIMEOUT_MS = 12_000;
const DEFAULT_API_BASE_URL = "http://localhost:8000";

export type ApiErrorKind =
  | "bad-request"
  | "validation"
  | "rate-limit"
  | "unavailable"
  | "timeout"
  | "internal"
  | "invalid-json"
  | "network"
  | "cancelled"
  | "unknown";

export class EduDocsApiError extends Error {
  readonly kind: ApiErrorKind;
  readonly status?: number;
  readonly requestId?: string;
  readonly latencyMs?: number;

  constructor(
    message: string,
    kind: ApiErrorKind,
    options: { status?: number; requestId?: string; latencyMs?: number } = {},
  ) {
    super(message);
    this.name = "EduDocsApiError";
    this.kind = kind;
    this.status = options.status;
    this.requestId = options.requestId;
    this.latencyMs = options.latencyMs;
  }
}

export interface ApiClientOptions {
  baseUrl?: string;
  timeoutMs?: number;
}

export function getConfiguredApiBaseUrl(): string {
  return process.env.NEXT_PUBLIC_API_BASE_URL ?? DEFAULT_API_BASE_URL;
}

export function normalizeBaseUrl(value: string): string {
  const trimmed = value.trim();
  if (!trimmed || trimmed === "/") {
    return "";
  }
  return trimmed.replace(/\/+$/, "");
}

export function createApiClient(options: ApiClientOptions = {}) {
  const baseUrl = normalizeBaseUrl(options.baseUrl ?? getConfiguredApiBaseUrl());
  const timeoutMs = options.timeoutMs ?? DEFAULT_TIMEOUT_MS;

  return {
    getHealth: () => request<HealthResponse>("/health", { baseUrl, timeoutMs }),
    getReadiness: () => request<ReadyResponse>("/ready", { baseUrl, timeoutMs }),
    getDocuments: () => request<DocumentsResponse>("/api/documents", { baseUrl, timeoutMs }),
    sendQuestion: (question: string) =>
      request<ChatResponse>("/api/chat", {
        baseUrl,
        timeoutMs,
        init: {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ question }),
        },
      }),
  };
}

interface RequestOptions {
  baseUrl: string;
  timeoutMs: number;
  init?: RequestInit;
}

async function request<T>(path: string, options: RequestOptions): Promise<T> {
  const controller = new AbortController();
  const timeout = window.setTimeout(() => controller.abort("timeout"), options.timeoutMs);

  try {
    const response = await fetch(`${options.baseUrl}${path}`, {
      ...options.init,
      signal: controller.signal,
    });
    const payload = await parseJson(response);
    if (!response.ok) {
      throw apiErrorFromResponse(response.status, payload);
    }
    return payload as T;
  } catch (error) {
    if (error instanceof EduDocsApiError) {
      throw error;
    }
    if (error instanceof DOMException && error.name === "AbortError") {
      throw new EduDocsApiError("A requisição demorou demais e foi cancelada.", "timeout");
    }
    if (String(error).includes("timeout")) {
      throw new EduDocsApiError("A requisição demorou demais e foi cancelada.", "timeout");
    }
    throw new EduDocsApiError("Não foi possível conectar à API EduDocs.", "network");
  } finally {
    window.clearTimeout(timeout);
  }
}

async function parseJson(response: Response): Promise<unknown> {
  try {
    return await response.json();
  } catch {
    throw new EduDocsApiError("A API retornou uma resposta JSON inválida.", "invalid-json");
  }
}

function apiErrorFromResponse(status: number, payload: unknown): EduDocsApiError {
  const parsed = parseErrorPayload(payload);
  const message = messageForStatus(status, parsed.detail);
  return new EduDocsApiError(message, kindForStatus(status), {
    status,
    requestId: parsed.request_id ?? undefined,
    latencyMs: parsed.latency_ms ?? undefined,
  });
}

function parseErrorPayload(payload: unknown): ApiErrorPayload {
  if (isRecord(payload)) {
    const rawDetail = payload.detail;
    if (typeof rawDetail === "string") {
      return {
        detail: rawDetail,
        request_id: stringOrNull(payload.request_id),
        latency_ms: numberOrNull(payload.latency_ms),
      };
    }
    if (isRecord(rawDetail)) {
      return {
        detail:
          typeof rawDetail.detail === "string"
            ? rawDetail.detail
            : "A API retornou um erro sem mensagem pública.",
        request_id: stringOrNull(rawDetail.request_id),
        latency_ms: numberOrNull(rawDetail.latency_ms),
      };
    }
  }
  return { detail: "A API retornou um erro sem mensagem pública." };
}

function messageForStatus(status: number, detail: string): string {
  const messages: Record<number, string> = {
    400: `Pergunta inválida. ${detail}`,
    422: "A pergunta não pôde ser validada pela API.",
    429: "O provedor atingiu limite de requisições. Tente novamente em instantes.",
    503: "A API ou o corpus estão indisponíveis no momento.",
    504: "A geração da resposta excedeu o tempo limite.",
  };
  return messages[status] ?? "A API retornou um erro inesperado.";
}

function kindForStatus(status: number): ApiErrorKind {
  if (status === 400) return "bad-request";
  if (status === 422) return "validation";
  if (status === 429) return "rate-limit";
  if (status === 503) return "unavailable";
  if (status === 504) return "timeout";
  if (status >= 500) return "internal";
  return "unknown";
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

function stringOrNull(value: unknown): string | null {
  return typeof value === "string" ? value : null;
}

function numberOrNull(value: unknown): number | null {
  return typeof value === "number" ? value : null;
}
