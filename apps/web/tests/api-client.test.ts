import { afterEach, describe, expect, it, vi } from "vitest";

import { createApiClient, EduDocsApiError, normalizeBaseUrl } from "@/lib/api-client";

function jsonResponse(body: unknown, init: ResponseInit = {}) {
  return new Response(JSON.stringify(body), {
    status: init.status ?? 200,
    headers: { "Content-Type": "application/json" },
  });
}

describe("api-client", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("normaliza URL configurável", () => {
    expect(normalizeBaseUrl("http://localhost:8000///")).toBe("http://localhost:8000");
    expect(normalizeBaseUrl("/")).toBe("");
  });

  it("carrega /health", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse({ status: "ok", service: "api" })));
    await expect(createApiClient({ baseUrl: "" }).getHealth()).resolves.toEqual({
      status: "ok",
      service: "api",
    });
  });

  it("carrega /ready", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(jsonResponse({ status: "ready", index_format_version: "1", chunks: 41 })),
    );
    await expect(createApiClient({ baseUrl: "" }).getReadiness()).resolves.toMatchObject({
      chunks: 41,
    });
  });

  it("carrega documentos", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse({ documents: [] })));
    await expect(createApiClient({ baseUrl: "" }).getDocuments()).resolves.toEqual({
      documents: [],
    });
  });

  it("envia pergunta com JSON tipado", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      jsonResponse({
        answer: "Resposta",
        answerable: true,
        sources: [],
        request_id: "req-1",
        latency_ms: 5,
      }),
    );
    vi.stubGlobal("fetch", fetchMock);
    await createApiClient({ baseUrl: "" }).sendQuestion("Como solicito certificado?");
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/chat",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({ question: "Como solicito certificado?" }),
      }),
    );
  });

  it.each([
    [400, "bad-request"],
    [422, "validation"],
    [429, "rate-limit"],
    [503, "unavailable"],
    [504, "timeout"],
    [500, "internal"],
  ] as const)("trata HTTP %s", async (status, kind) => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        jsonResponse({ detail: { detail: "Falha pública.", request_id: "req-erro" } }, { status }),
      ),
    );
    await expect(createApiClient({ baseUrl: "" }).sendQuestion("x")).rejects.toMatchObject({
      kind,
      requestId: "req-erro",
    });
  });

  it("trata JSON inválido", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(new Response("html", { status: 200 })),
    );
    await expect(createApiClient({ baseUrl: "" }).getHealth()).rejects.toMatchObject({
      kind: "invalid-json",
    });
  });

  it("trata falha de rede", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("network")));
    await expect(createApiClient({ baseUrl: "" }).getHealth()).rejects.toMatchObject({
      kind: "network",
    });
  });

  it("trata timeout ou cancelamento", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockRejectedValue(new DOMException("Abortado", "AbortError")),
    );
    await expect(createApiClient({ baseUrl: "" }).getHealth()).rejects.toMatchObject({
      kind: "timeout",
    });
  });

  it("preserva request_id discreto em erro tipado", () => {
    const error = new EduDocsApiError("Falha", "unavailable", { requestId: "req-123" });
    expect(error.requestId).toBe("req-123");
  });
});
