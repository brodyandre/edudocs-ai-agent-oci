"use client";

import React from "react";
import { FormEvent, KeyboardEvent, useEffect, useMemo, useRef, useState } from "react";

import { createApiClient, EduDocsApiError } from "@/lib/api-client";
import type { ChatResponse, DocumentResponse, SourceResponse } from "@/types/api";

const MAX_QUESTION_LENGTH = 800;
const GITHUB_URL = "https://github.com/brodyandre/edudocs-ai-agent-oci";
const EXAMPLES = [
  "Como solicito meu certificado?",
  "Qual é o prazo para pedir reembolso?",
  "Quais são os critérios de aprovação?",
  "Como posso corrigir meu nome no certificado?",
  "Por quanto tempo meus dados são armazenados?",
  "O que acontece se eu cancelar depois do prazo de arrependimento?",
];

type LoadState = "loading" | "ready" | "unavailable";

interface Availability {
  health: LoadState;
  corpus: LoadState;
  documents: LoadState;
  chunks?: number;
  message?: string;
}

interface ConversationMessage {
  id: string;
  role: "user" | "assistant";
  text: string;
  answerable?: boolean;
  sources?: SourceResponse[];
  requestId?: string;
  latencyMs?: number;
  error?: string;
}

export function EduDocsApp() {
  const api = useMemo(() => createApiClient(), []);
  const [availability, setAvailability] = useState<Availability>({
    health: "loading",
    corpus: "loading",
    documents: "loading",
  });
  const [documents, setDocuments] = useState<DocumentResponse[]>([]);
  const [question, setQuestion] = useState("");
  const [messages, setMessages] = useState<ConversationMessage[]>([]);
  const [isSending, setIsSending] = useState(false);
  const [copyStatus, setCopyStatus] = useState<string | null>(null);
  const [liveMessage, setLiveMessage] = useState("Carregando disponibilidade da API.");
  const textAreaRef = useRef<HTMLTextAreaElement | null>(null);
  const conversationRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    let active = true;
    async function loadInitialData() {
      try {
        const [health, readiness, docs] = await Promise.allSettled([
          api.getHealth(),
          api.getReadiness(),
          api.getDocuments(),
        ]);
        if (!active) {
          return;
        }
        const nextAvailability: Availability = {
          health: health.status === "fulfilled" ? "ready" : "unavailable",
          corpus: readiness.status === "fulfilled" ? "ready" : "unavailable",
          documents: docs.status === "fulfilled" ? "ready" : "unavailable",
          chunks: readiness.status === "fulfilled" ? readiness.value.chunks : undefined,
          message: summarizeInitialErrors(health, readiness, docs),
        };
        setAvailability(nextAvailability);
        setDocuments(docs.status === "fulfilled" ? docs.value.documents : []);
        setLiveMessage(statusSentence(nextAvailability));
      } catch (error) {
        if (!active) {
          return;
        }
        const message = errorToMessage(error);
        setAvailability({
          health: "unavailable",
          corpus: "unavailable",
          documents: "unavailable",
          message,
        });
        setLiveMessage(message);
      }
    }
    loadInitialData();
    return () => {
      active = false;
    };
  }, [api]);

  useEffect(() => {
    const lastElement = conversationRef.current?.lastElementChild;
    if (lastElement instanceof HTMLElement && typeof lastElement.scrollIntoView === "function") {
      lastElement.scrollIntoView({
        block: "nearest",
        behavior: "smooth",
      });
    }
  }, [messages.length]);

  const latestAssistant = [...messages].reverse().find((message) => message.role === "assistant");
  const canSend =
    question.trim().length > 0 &&
    question.length <= MAX_QUESTION_LENGTH &&
    !isSending &&
    availability.health === "ready" &&
    availability.corpus === "ready" &&
    documents.length > 0;

  async function submitQuestion(event?: FormEvent<HTMLFormElement>) {
    event?.preventDefault();
    const trimmed = question.trim();
    if (!trimmed || !canSend) {
      if (!trimmed) {
        setLiveMessage("Digite uma pergunta antes de enviar.");
      }
      return;
    }

    const userMessage: ConversationMessage = {
      id: `user-${Date.now()}`,
      role: "user",
      text: trimmed,
    };
    setMessages((current) => [...current, userMessage]);
    setQuestion("");
    setIsSending(true);
    setLiveMessage("Pergunta enviada. Aguardando resposta do agente.");

    try {
      const response = await api.sendQuestion(trimmed);
      setMessages((current) => [...current, responseToMessage(response)]);
      setLiveMessage(
        response.answerable
          ? "Resposta fundamentada recebida com fontes."
          : "Resposta recebida sem evidência suficiente nos documentos.",
      );
    } catch (error) {
      const apiError = error instanceof EduDocsApiError ? error : null;
      const text = errorToMessage(error);
      setMessages((current) => [
        ...current,
        {
          id: `assistant-error-${Date.now()}`,
          role: "assistant",
          text,
          requestId: apiError?.requestId,
          latencyMs: apiError?.latencyMs,
          error: text,
        },
      ]);
      setLiveMessage(text);
    } finally {
      setIsSending(false);
    }
  }

  function handleExampleClick(example: string) {
    setQuestion(example);
    textAreaRef.current?.focus();
  }

  function handleQuestionKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      void submitQuestion();
    }
  }

  async function copyAnswer(message: ConversationMessage) {
    if (!message.text) {
      return;
    }
    const text = formatAnswerForCopy(message);
    try {
      if (navigator.clipboard?.writeText) {
        await navigator.clipboard.writeText(text);
      } else {
        fallbackCopy(text);
      }
      setCopyStatus("Resposta copiada.");
    } catch {
      setCopyStatus("Não foi possível copiar a resposta.");
    }
  }

  function clearConversation() {
    setMessages([]);
    setCopyStatus(null);
    setLiveMessage("Conversa limpa. Nenhuma chamada foi feita à API.");
    textAreaRef.current?.focus();
  }

  return (
    <main className="min-h-screen">
      <a
        href="#conversation"
        className="sr-only focus:not-sr-only focus:fixed focus:left-4 focus:top-4 focus:z-50 focus:rounded-md focus:bg-white focus:px-4 focus:py-2 focus:text-sm focus:font-semibold focus:text-pine"
      >
        Ir para a conversa
      </a>

      <header className="border-b border-line bg-white/86 backdrop-blur">
        <div className="mx-auto flex max-w-7xl flex-col gap-4 px-4 py-5 sm:px-6 lg:flex-row lg:items-center lg:justify-between lg:px-8">
          <div>
            <p className="text-sm font-semibold uppercase tracking-wide text-teal">EduDocs AI</p>
            <h1 className="text-2xl font-semibold tracking-normal text-ink">
              Assistente inteligente para consulta de documentos educacionais.
            </h1>
          </div>
          <nav aria-label="Navegação principal" className="flex flex-wrap items-center gap-3">
            <StatusPill availability={availability} compact />
            <a className="nav-link" href="#how-it-works">
              Como funciona
            </a>
            <a className="nav-link" href={GITHUB_URL} rel="noreferrer noopener" target="_blank">
              GitHub
            </a>
          </nav>
        </div>
      </header>

      <div className="mx-auto grid max-w-7xl gap-6 px-4 py-6 sm:px-6 lg:grid-cols-[minmax(0,1fr)_380px] lg:px-8">
        <section className="space-y-6">
          <section className="border-b border-line bg-white pb-6">
            <div className="grid gap-5 lg:grid-cols-[1fr_280px]">
              <div>
                <p className="mb-3 text-sm font-semibold uppercase tracking-wide text-teal">
                  Consulta fundamentada
                </p>
                <h2 className="text-3xl font-semibold tracking-normal text-ink">
                  Pergunte sobre normas, certificados, reembolsos, matrícula e privacidade.
                </h2>
                <p className="mt-4 max-w-3xl text-base leading-7 text-slate-700">
                  O agente consulta PDFs do corpus, responde somente quando encontra sustentação
                  documental e mostra as fontes usadas por documento, versão, página, seção e trecho.
                </p>
                <p className="mt-4 rounded-md border border-amber/40 bg-amber/10 px-4 py-3 text-sm text-slate-800">
                  Os documentos utilizados neste projeto são fictícios e foram criados
                  exclusivamente para fins educacionais e de demonstração.
                </p>
              </div>
              <StatusPanel availability={availability} documents={documents} />
            </div>
          </section>

          <section aria-labelledby="examples-title" className="rounded-lg border border-line bg-white p-5">
            <h2 id="examples-title" className="text-lg font-semibold text-ink">
              Exemplos de perguntas
            </h2>
            <div className="mt-4 flex flex-wrap gap-2">
              {EXAMPLES.map((example) => (
                <button
                  className="rounded-md border border-line bg-paper px-3 py-2 text-left text-sm font-medium text-ink transition hover:border-teal hover:bg-white"
                  key={example}
                  onClick={() => handleExampleClick(example)}
                  type="button"
                >
                  {example}
                </button>
              ))}
            </div>
          </section>

          <section
            aria-labelledby="conversation-title"
            aria-busy={isSending}
            className="rounded-lg border border-line bg-white"
            id="conversation"
          >
            <div className="border-b border-line p-5">
              <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                <div>
                  <h2 id="conversation-title" className="text-xl font-semibold text-ink">
                    Conversa
                  </h2>
                  <p className="mt-1 text-sm text-slate-600">
                    O histórico permanece apenas nesta sessão do navegador.
                  </p>
                </div>
                <button
                  className="rounded-md border border-line px-3 py-2 text-sm font-semibold text-pine disabled:cursor-not-allowed disabled:opacity-50"
                  disabled={messages.length === 0 || isSending}
                  onClick={clearConversation}
                  type="button"
                >
                  Limpar conversa
                </button>
              </div>
            </div>

            <div className="max-h-[620px] space-y-4 overflow-y-auto p-5" ref={conversationRef}>
              {messages.length === 0 ? (
                <div className="rounded-lg border border-dashed border-line bg-paper p-5 text-sm text-slate-700">
                  Escolha um exemplo ou escreva uma pergunta sobre o corpus educacional.
                </div>
              ) : (
                messages.map((message) => (
                  <ConversationBubble
                    key={message.id}
                    message={message}
                    onCopy={() => void copyAnswer(message)}
                  />
                ))
              )}
              {isSending ? (
                <div className="rounded-lg border border-line bg-paper p-4 text-sm text-slate-700">
                  Consultando documentos e validando fontes...
                </div>
              ) : null}
            </div>

            <form className="border-t border-line p-5" onSubmit={submitQuestion}>
              <label className="text-sm font-semibold text-ink" htmlFor="question">
                Pergunta ao agente
              </label>
              <textarea
                aria-describedby="question-counter question-help"
                className="mt-2 min-h-28 w-full resize-y rounded-md border border-line bg-white px-3 py-3 text-base text-ink shadow-sm transition placeholder:text-slate-400 disabled:bg-slate-100"
                disabled={isSending}
                id="question"
                maxLength={MAX_QUESTION_LENGTH}
                onChange={(event) => setQuestion(event.target.value)}
                onKeyDown={handleQuestionKeyDown}
                placeholder="Ex.: Qual é o prazo para pedir reembolso?"
                ref={textAreaRef}
                value={question}
              />
              <div className="mt-2 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                <p className="text-sm text-slate-600" id="question-help">
                  Perguntas vazias ou acima do limite não são enviadas.
                </p>
                <p
                  className={question.length > MAX_QUESTION_LENGTH ? "text-sm text-rose" : "text-sm text-slate-600"}
                  id="question-counter"
                >
                  {question.length}/{MAX_QUESTION_LENGTH} caracteres
                </p>
              </div>
              <div className="mt-4 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                <SubmitHint availability={availability} documents={documents} />
                <button
                  className="rounded-md bg-pine px-5 py-3 text-sm font-semibold text-white transition hover:bg-teal disabled:cursor-not-allowed disabled:bg-slate-400"
                  disabled={!canSend}
                  type="submit"
                >
                  {isSending ? "Enviando..." : "Enviar pergunta"}
                </button>
              </div>
            </form>
          </section>
        </section>

        <aside className="space-y-6">
          <DocumentsPanel documents={documents} state={availability.documents} />
          <SourcesPanel message={latestAssistant} />
          <section className="rounded-lg border border-line bg-white p-5" id="how-it-works">
            <h2 className="text-lg font-semibold text-ink">Como funciona</h2>
            <ol className="mt-3 space-y-3 text-sm leading-6 text-slate-700">
              <li>1. A pergunta é enviada para a API FastAPI.</li>
              <li>2. O grafo LangGraph recupera evidências do índice local.</li>
              <li>3. A resposta é retornada com fontes ou uma recusa quando falta evidência.</li>
            </ol>
          </section>
          <section className="rounded-lg border border-line bg-white p-5">
            <h2 className="text-lg font-semibold text-ink">Avisos e limitações</h2>
            <p className="mt-3 text-sm leading-6 text-slate-700">
              O corpus é fictício, não há autenticação, upload público, histórico persistente ou
              consulta a documentos fora do conjunto disponível nesta demonstração.
            </p>
          </section>
        </aside>
      </div>

      <footer className="border-t border-line px-4 py-6 text-center text-sm text-slate-600">
        EduDocs AI. Projeto educacional de demonstração com documentos fictícios.
      </footer>

      <div aria-live="polite" className="sr-only" role="status">
        {liveMessage}
      </div>
      {copyStatus ? (
        <div aria-live="polite" className="sr-only" role="status">
          {copyStatus}
        </div>
      ) : null}
    </main>
  );
}

function StatusPill({
  availability,
  compact = false,
}: Readonly<{ availability: Availability; compact?: boolean }>) {
  const label = statusSentence(availability);
  const ready = availability.health === "ready" && availability.corpus === "ready";
  return (
    <span
      className={`inline-flex items-center gap-2 rounded-full border px-3 py-1 text-sm font-semibold ${
        ready
          ? "border-teal/40 bg-teal/10 text-pine"
          : "border-amber/40 bg-amber/10 text-slate-800"
      }`}
    >
      <span aria-hidden="true" className={ready ? "status-dot bg-teal" : "status-dot bg-amber"} />
      {compact ? (ready ? "API e corpus prontos" : "Verificando serviço") : label}
    </span>
  );
}

function StatusPanel({
  availability,
  documents,
}: Readonly<{ availability: Availability; documents: DocumentResponse[] }>) {
  return (
    <div className="rounded-lg border border-line bg-paper p-4">
      <h2 className="text-base font-semibold text-ink">Disponibilidade</h2>
      <dl className="mt-4 space-y-3 text-sm">
        <StatusRow label="API" state={availability.health} />
        <StatusRow label="Corpus" state={availability.corpus} detail={chunksText(availability.chunks)} />
        <StatusRow label="Documentos" state={availability.documents} detail={`${documents.length} listados`} />
      </dl>
      {availability.message ? (
        <p className="mt-4 rounded-md border border-amber/40 bg-white px-3 py-2 text-sm text-slate-700">
          {availability.message}
        </p>
      ) : null}
    </div>
  );
}

function StatusRow({
  label,
  state,
  detail,
}: Readonly<{ label: string; state: LoadState; detail?: string }>) {
  return (
    <div className="flex items-center justify-between gap-3">
      <dt className="font-medium text-slate-700">{label}</dt>
      <dd className="text-right">
        <span className="font-semibold text-ink">{stateLabel(state)}</span>
        {detail ? <span className="ml-2 text-slate-600">{detail}</span> : null}
      </dd>
    </div>
  );
}

function DocumentsPanel({
  documents,
  state,
}: Readonly<{ documents: DocumentResponse[]; state: LoadState }>) {
  return (
    <section aria-labelledby="documents-title" className="rounded-lg border border-line bg-white p-5">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h2 id="documents-title" className="text-lg font-semibold text-ink">
            Documentos disponíveis
          </h2>
          <p className="mt-1 text-sm text-slate-600">{documents.length} documentos no contrato público.</p>
        </div>
        <span className="rounded-full bg-paper px-3 py-1 text-sm font-semibold text-pine">
          {stateLabel(state)}
        </span>
      </div>
      {documents.length === 0 ? (
        <p className="mt-4 rounded-md border border-dashed border-line bg-paper p-4 text-sm text-slate-700">
          Nenhum documento público foi retornado pela API.
        </p>
      ) : (
        <ul className="mt-4 space-y-3">
          {documents.map((document) => (
            <li className="rounded-md border border-line bg-paper p-3" key={document.id}>
              <h3 className="font-semibold text-ink">{document.title}</h3>
              <p className="mt-1 text-sm text-slate-700">
                Versão {document.version} · Categoria {document.category}
              </p>
              <p className="mt-1 text-xs uppercase tracking-wide text-slate-500">
                {document.language} · vigente desde {document.effective_date}
              </p>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

function ConversationBubble({
  message,
  onCopy,
}: Readonly<{ message: ConversationMessage; onCopy: () => void }>) {
  const isAssistant = message.role === "assistant";
  return (
    <article
      className={`rounded-lg border p-4 ${
        isAssistant ? "border-line bg-paper" : "ml-auto border-pine/30 bg-pine text-white"
      } max-w-[min(100%,760px)]`}
    >
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <p className={`text-sm font-semibold ${isAssistant ? "text-pine" : "text-white"}`}>
            {isAssistant ? "EduDocs AI" : "Você"}
          </p>
          {isAssistant && message.answerable !== undefined ? (
            <p className="mt-1 text-sm text-slate-600">
              {message.answerable
                ? "Resposta baseada nos documentos."
                : "Sem evidência suficiente nos documentos."}
            </p>
          ) : null}
        </div>
        {isAssistant && !message.error ? (
          <button className="copy-button" onClick={onCopy} type="button">
            Copiar resposta
          </button>
        ) : null}
      </div>
      <p className={`mt-3 whitespace-pre-wrap text-sm leading-6 ${isAssistant ? "text-slate-800" : "text-white"}`}>
        {message.text}
      </p>
      {message.latencyMs !== undefined || message.requestId ? (
        <p className={`mt-3 text-xs ${isAssistant ? "text-slate-500" : "text-white/80"}`}>
          {message.latencyMs !== undefined ? `Latência: ${message.latencyMs} ms. ` : ""}
          {message.requestId ? `Referência técnica: ${message.requestId}.` : ""}
        </p>
      ) : null}
      {isAssistant && message.sources && message.sources.length > 0 ? (
        <SourceList sources={message.sources} />
      ) : null}
    </article>
  );
}

function SourcesPanel({ message }: Readonly<{ message?: ConversationMessage }>) {
  const sources = message?.sources ?? [];
  return (
    <section aria-labelledby="sources-title" className="rounded-lg border border-line bg-white p-5">
      <h2 id="sources-title" className="text-lg font-semibold text-ink">
        Fontes da resposta
      </h2>
      {sources.length === 0 ? (
        <p className="mt-3 text-sm leading-6 text-slate-700">
          As fontes aparecem aqui quando a API retorna uma resposta fundamentada.
        </p>
      ) : (
        <SourceList sources={sources} compact />
      )}
    </section>
  );
}

function SourceList({
  sources,
  compact = false,
}: Readonly<{ sources: SourceResponse[]; compact?: boolean }>) {
  const grouped = groupSources(sources);
  return (
    <div className={compact ? "mt-4 space-y-3" : "mt-4 grid gap-3"}>
      {grouped.map((source) => (
        <details className="rounded-md border border-line bg-white p-3" key={source.key}>
          <summary className="cursor-pointer text-sm font-semibold text-ink">
            {source.title} · v{source.version} · página {source.page}
          </summary>
          <dl className="mt-3 space-y-2 text-sm text-slate-700">
            <div>
              <dt className="font-semibold text-slate-900">Documento</dt>
              <dd>{source.title}</dd>
            </div>
            <div>
              <dt className="font-semibold text-slate-900">Versão</dt>
              <dd>{source.version}</dd>
            </div>
            <div>
              <dt className="font-semibold text-slate-900">Página</dt>
              <dd>{source.page}</dd>
            </div>
            <div>
              <dt className="font-semibold text-slate-900">Seção</dt>
              <dd>{source.section ?? "Não informada"}</dd>
            </div>
            <div>
              <dt className="font-semibold text-slate-900">Trecho</dt>
              <dd className="mt-1 max-h-28 overflow-y-auto rounded bg-paper p-3 leading-6">
                {source.excerpt}
              </dd>
            </div>
          </dl>
        </details>
      ))}
    </div>
  );
}

function SubmitHint({
  availability,
  documents,
}: Readonly<{ availability: Availability; documents: DocumentResponse[] }>) {
  if (availability.health !== "ready") {
    return <p className="text-sm text-rose">API indisponível para envio.</p>;
  }
  if (availability.corpus !== "ready") {
    return <p className="text-sm text-amber">Corpus ainda não está pronto.</p>;
  }
  if (documents.length === 0) {
    return <p className="text-sm text-amber">Não há documentos públicos disponíveis.</p>;
  }
  return <p className="text-sm text-slate-600">Pronto para consultar o corpus.</p>;
}

function responseToMessage(response: ChatResponse): ConversationMessage {
  return {
    id: `assistant-${response.request_id}`,
    role: "assistant",
    text: response.answer,
    answerable: response.answerable,
    sources: response.sources,
    requestId: response.request_id,
    latencyMs: response.latency_ms,
  };
}

function groupSources(sources: SourceResponse[]): SourceResponseWithKey[] {
  return sources.map((source, index) => ({
    ...source,
    key: `${source.document_id}-${source.version}-${source.page}-${source.section ?? "sem-secao"}-${index}`,
  }));
}

interface SourceResponseWithKey extends SourceResponse {
  key: string;
}

function formatAnswerForCopy(message: ConversationMessage): string {
  const sourceText =
    message.sources && message.sources.length > 0
      ? "\n\nFontes:\n" +
        message.sources
          .map((source) => `- ${source.title}, versão ${source.version}, página ${source.page}`)
          .join("\n")
      : "";
  return `${message.text}${sourceText}`;
}

function fallbackCopy(text: string) {
  const textarea = document.createElement("textarea");
  textarea.value = text;
  textarea.setAttribute("readonly", "true");
  textarea.style.position = "fixed";
  textarea.style.left = "-9999px";
  document.body.appendChild(textarea);
  textarea.select();
  const copied = document.execCommand("copy");
  document.body.removeChild(textarea);
  if (!copied) {
    throw new Error("Clipboard indisponível.");
  }
}

function summarizeInitialErrors(
  health: PromiseSettledResult<unknown>,
  readiness: PromiseSettledResult<unknown>,
  docs: PromiseSettledResult<unknown>,
): string | undefined {
  if (health.status === "rejected") {
    return errorToMessage(health.reason);
  }
  if (readiness.status === "rejected") {
    return errorToMessage(readiness.reason);
  }
  if (docs.status === "rejected") {
    return errorToMessage(docs.reason);
  }
  return undefined;
}

function errorToMessage(error: unknown): string {
  if (error instanceof EduDocsApiError) {
    const reference = error.requestId ? ` Referência técnica: ${error.requestId}.` : "";
    return `${error.message}${reference}`;
  }
  return "Ocorreu um erro inesperado ao comunicar com a API.";
}

function statusSentence(availability: Availability): string {
  if (availability.health === "loading" || availability.corpus === "loading") {
    return "Verificando disponibilidade da API e do corpus.";
  }
  if (availability.health !== "ready") {
    return "API indisponível.";
  }
  if (availability.corpus !== "ready") {
    return "API operacional, mas corpus não pronto.";
  }
  return "API operacional e corpus pronto.";
}

function stateLabel(state: LoadState): string {
  if (state === "loading") {
    return "Carregando";
  }
  if (state === "ready") {
    return "Operacional";
  }
  return "Indisponível";
}

function chunksText(chunks?: number): string | undefined {
  return chunks === undefined ? undefined : `${chunks} chunks`;
}
