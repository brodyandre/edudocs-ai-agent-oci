"use client";

import React from "react";
import { FormEvent, KeyboardEvent, useEffect, useMemo, useRef, useState } from "react";

import { DocumentAnswerIcon } from "@/components/DocumentAnswerIcon";
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
const USER_STEPS = [
  {
    title: "Escolha ou escreva",
    description: "Use uma pergunta pronta ou digite com suas palavras.",
  },
  {
    title: "Leia a resposta",
    description: "A resposta aparece em linguagem direta, sem precisar conhecer termos técnicos.",
  },
  {
    title: "Confira a origem",
    description: "Quando houver base nos documentos, mostramos de onde a informação saiu.",
  },
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
    <main className="edudocs-shell">
      <a
        href="#conversation"
        className="sr-only focus:not-sr-only focus:fixed focus:left-4 focus:top-4 focus:z-50 focus:bg-paper focus:px-4 focus:py-2 focus:text-sm focus:font-semibold focus:text-ink"
      >
        Ir para a conversa
      </a>

      <div className="app-shell">
      <header className="hero-shell">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div>
            <p className="eyebrow">
              <span aria-hidden="true" className="status-dot bg-pine" />
              Assistente de consulta
            </p>
          </div>
          <StatusPill availability={availability} compact />
        </div>
        <div className="grid gap-10 lg:grid-cols-[1.65fr_0.85fr] lg:items-end">
          <div className="hero-title-visual">
            <div className="hero-title-copy">
              <p className="text-[0.82rem] font-semibold uppercase tracking-[0.25em] text-rose">
                EduDocs AI
              </p>
              <h1 className="hero-title">
                Pergunte aos documentos.
                <br />
                <em>Entenda a resposta.</em>
              </h1>
            </div>
            <div className="hero-icon" aria-hidden="true">
              <DocumentAnswerIcon className="hero-icon-svg" />
            </div>
          </div>
          <div>
            <p className="hero-copy">
              Escreva sua dúvida como falaria com uma pessoa. O EduDocs procura nos documentos
              disponíveis e mostra uma resposta simples, com a origem da informação quando houver base.
            </p>
            <div className="mt-7 flex flex-wrap gap-2">
              <span className="border border-pine/20 bg-pine/[0.035] px-3 py-2 text-[0.62rem] uppercase tracking-[0.06em] text-paper/75">
                Perguntas prontas
              </span>
              <span className="border border-pine/20 bg-pine/[0.035] px-3 py-2 text-[0.62rem] uppercase tracking-[0.06em] text-paper/75">
                Resposta direta
              </span>
              <span className="border border-pine/20 bg-pine/[0.035] px-3 py-2 text-[0.62rem] uppercase tracking-[0.06em] text-paper/75">
                Fonte conferível
              </span>
              <span className="border border-pine/20 bg-pine/[0.035] px-3 py-2 text-[0.62rem] uppercase tracking-[0.06em] text-paper/75">
                Sem cadastro
              </span>
            </div>
            <div className="my-7 h-px bg-gradient-to-r from-rose to-transparent" />
            <small className="text-muted">
              Os documentos são fictícios e servem apenas para demonstração. Revise a fonte antes de
              tomar qualquer decisão.
            </small>
          </div>
        </div>
      </header>

      <nav aria-label="Navegação principal" className="section-nav">
        <span className="font-serif text-lg italic text-rose">ED/AI</span>
        <div className="flex items-center gap-2 overflow-x-auto">
          <a className="nav-link" href="#how-it-works">
            Como funciona
          </a>
          <a className="nav-link" href="#conversation">
            Conversa
          </a>
          <a className="nav-link" href="#documents">
            Documentos
          </a>
          <a className="nav-link" href={GITHUB_URL} rel="noreferrer noopener" target="_blank">
            GitHub
          </a>
        </div>
      </nav>

      <aside className="responsible-use" aria-label="Avisos de uso responsável">
        <span>Se não encontrar a informação, o assistente avisa.</span>
        <span>Quando responder, ele mostra de onde tirou a informação.</span>
        <span>A conversa fica somente nesta sessão do navegador.</span>
      </aside>

      <div className="grid gap-6 py-10 lg:grid-cols-[minmax(0,1fr)_390px]">
        <section className="space-y-8">
          <section className="border-b border-line pb-8">
            <div className="grid gap-8 lg:grid-cols-[1fr_310px]">
              <div>
                <p className="eyebrow">Comece por aqui</p>
                <h2 className="mt-3 font-serif text-[clamp(2.6rem,5vw,4.8rem)] font-normal leading-none tracking-normal text-paper">
                  Pergunte sobre normas, certificados, reembolsos, matrícula e privacidade.
                </h2>
                <p className="mt-6 max-w-3xl text-base leading-7 text-paper/75">
                  Você não precisa saber o nome do documento nem escrever de um jeito especial.
                  Basta dizer o que quer descobrir. Se houver informação disponível, a resposta vem
                  acompanhada da fonte para conferência.
                </p>
                <p className="mt-5 border border-amber/30 bg-amber/[0.035] px-4 py-3 text-sm text-paper/80">
                  Os documentos utilizados neste projeto são fictícios e foram criados
                  exclusivamente para fins educacionais e de demonstração.
                </p>
              </div>
              <StatusPanel availability={availability} documents={documents} />
            </div>
          </section>

          <section aria-labelledby="examples-title" className="panel-soft p-5">
            <div className="section-heading">
              <div>
                <span className="eyebrow">Um clique para começar</span>
                <h2 id="examples-title" className="font-serif text-3xl font-normal text-paper">
                  Exemplos de perguntas
                </h2>
                <p className="mt-2 max-w-2xl text-sm leading-6 text-muted">
                  Clique em uma pergunta pronta para preencher o campo. Você pode editar o texto antes de enviar.
                </p>
              </div>
              <span className="section-number">01</span>
            </div>
            <div className="mt-4 flex flex-wrap gap-2">
              {EXAMPLES.map((example) => (
                <button
                  className="example-chip"
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
            className="panel"
            id="conversation"
          >
            <div className="border-b border-line p-5">
              <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                <div>
                  <span className="eyebrow">Tire sua dúvida</span>
                  <h2 id="conversation-title" className="mt-1 font-serif text-4xl font-normal text-paper">
                    Conversa
                  </h2>
                  <p className="mt-2 text-sm text-muted">
                    Faça uma pergunta por vez. O histórico permanece apenas nesta sessão do navegador.
                  </p>
                </div>
                <button
                  className="ghost-button"
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
                <div className="empty-guide">
                  <p className="eyebrow">Nenhuma pergunta enviada ainda</p>
                  <h3>Escolha um exemplo ou escreva sua dúvida.</h3>
                  <div className="mt-5 grid gap-3 md:grid-cols-3">
                    {USER_STEPS.map((step, index) => (
                      <div className="guide-step" key={step.title}>
                        <span>{String(index + 1).padStart(2, "0")}</span>
                        <strong>{step.title}</strong>
                        <p>{step.description}</p>
                      </div>
                    ))}
                  </div>
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
                <div className="border border-line bg-panelSoft p-4 text-sm text-paper/70">
                  Buscando nos documentos disponíveis...
                </div>
              ) : null}
            </div>

            <form className="border-t border-line p-5" onSubmit={submitQuestion}>
              <label className="text-sm font-semibold text-paper" htmlFor="question">
                Pergunta ao agente
              </label>
              <textarea
                aria-describedby="question-counter question-help"
                className="field"
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
                <p className="text-sm text-muted" id="question-help">
                  Escreva uma pergunta curta e objetiva. Não envie dados pessoais.
                </p>
                <p
                  className={question.length > MAX_QUESTION_LENGTH ? "text-sm text-rose" : "text-sm text-muted"}
                  id="question-counter"
                >
                  {question.length}/{MAX_QUESTION_LENGTH} caracteres
                </p>
              </div>
              <div className="mt-4 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                <SubmitHint availability={availability} documents={documents} />
                <button
                  className="primary-button"
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
          <section className="panel-soft p-5" id="how-it-works">
            <span className="eyebrow">O que acontece</span>
            <h2 className="mt-1 font-serif text-3xl font-normal text-paper">Como funciona</h2>
            <ol className="mt-4 space-y-3 text-sm leading-6 text-paper/75">
              <li>1. Você envia uma pergunta em linguagem comum.</li>
              <li>2. O assistente procura a resposta nos documentos disponíveis.</li>
              <li>3. Se encontrar base, ele responde e mostra a fonte. Se não encontrar, ele avisa.</li>
            </ol>
          </section>
          <section className="panel-soft border-rose/30 bg-[radial-gradient(circle_at_92%_5%,rgba(255,129,111,0.12),transparent_30%),#131c19] p-5">
            <span className="eyebrow text-rose">Uso responsável</span>
            <h2 className="mt-1 font-serif text-3xl font-normal text-paper">Avisos e limitações</h2>
            <p className="mt-3 text-sm leading-6 text-paper/75">
              Os documentos são fictícios. Não há login, envio de arquivos, histórico permanente ou
              consulta fora do conjunto disponível nesta demonstração.
            </p>
          </section>
        </aside>
      </div>

      <footer className="flex min-h-28 flex-col justify-center gap-2 border-t border-line py-6 text-[0.68rem] uppercase tracking-[0.1em] text-muted sm:flex-row sm:items-center sm:justify-between">
        <span>EduDocs AI · consulta guiada</span>
        <span>Projeto educacional com documentos fictícios.</span>
      </footer>
      </div>

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
      className={`status-chip ${
        ready
          ? "border-pine/40 bg-pine/10 text-pine"
          : "border-amber/40 bg-amber/10 text-paper"
      }`}
    >
      <span aria-hidden="true" className={ready ? "status-dot bg-pine" : "status-dot bg-amber"} />
      {compact ? (ready ? "API e corpus prontos" : "Verificando serviço") : label}
    </span>
  );
}

function StatusPanel({
  availability,
  documents,
}: Readonly<{ availability: Availability; documents: DocumentResponse[] }>) {
  return (
    <div className="panel-soft p-5">
      <span className="eyebrow">Estado local</span>
      <h2 className="mt-1 font-serif text-2xl font-normal text-paper">Pronto para usar?</h2>
      <dl className="mt-5 space-y-3 text-sm">
        <StatusRow label="Serviço" state={availability.health} />
        <StatusRow label="Base de consulta" state={availability.corpus} detail={chunksText(availability.chunks)} />
        <StatusRow label="Documentos" state={availability.documents} detail={`${documents.length} listados`} />
      </dl>
      {availability.message ? (
        <p className="mt-4 border border-amber/40 bg-amber/[0.035] px-3 py-2 text-sm text-paper/75">
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
      <dt className="font-medium text-muted">{label}</dt>
      <dd className="text-right">
        <span className="font-semibold text-paper">{stateLabel(state)}</span>
        {detail ? <span className="ml-2 text-muted">{detail}</span> : null}
      </dd>
    </div>
  );
}

function DocumentsPanel({
  documents,
  state,
}: Readonly<{ documents: DocumentResponse[]; state: LoadState }>) {
  return (
    <section aria-labelledby="documents-title" className="panel-soft p-5" id="documents">
      <div className="flex items-start justify-between gap-3">
        <div>
          <span className="eyebrow">Contrato público</span>
          <h2 id="documents-title" className="mt-1 font-serif text-3xl font-normal text-paper">
            Documentos disponíveis
          </h2>
          <p className="mt-2 text-sm text-muted">
            {documents.length} materiais que o assistente pode consultar.
          </p>
        </div>
        <span className="border border-line bg-ink px-3 py-1 text-sm font-semibold text-pine">
          {stateLabel(state)}
        </span>
      </div>
      {documents.length === 0 ? (
        <p className="mt-4 border border-dashed border-line bg-ink/50 p-4 text-sm text-muted">
          Nenhum documento público foi retornado pela API.
        </p>
      ) : (
        <ul className="mt-4 space-y-3">
          {documents.map((document) => (
            <li className="border border-line bg-panel p-3" key={document.id}>
              <h3 className="font-semibold text-paper">{document.title}</h3>
              <p className="mt-1 text-sm text-paper/75">
                Versão {document.version} · Tema {document.category}
              </p>
              <p className="mt-1 text-xs uppercase tracking-wide text-muted">
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
      className={`border p-4 ${
        isAssistant ? "border-line bg-panelSoft" : "ml-auto border-pine bg-paper text-ink"
      } max-w-[min(100%,760px)]`}
    >
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <p className={`text-sm font-semibold ${isAssistant ? "text-pine" : "text-ink"}`}>
            {isAssistant ? "EduDocs AI" : "Você"}
          </p>
          {isAssistant && message.answerable !== undefined ? (
            <p className="mt-1 text-sm text-muted">
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
      <p className={`mt-3 whitespace-pre-wrap text-sm leading-6 ${isAssistant ? "text-paper/85" : "text-ink"}`}>
        {message.text}
      </p>
      {message.latencyMs !== undefined || message.requestId ? (
        <p className={`mt-3 text-xs ${isAssistant ? "text-muted" : "text-ink/65"}`}>
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
    <section aria-labelledby="sources-title" className="panel-soft p-5">
      <span className="eyebrow">Conferência</span>
      <h2 id="sources-title" className="mt-1 font-serif text-3xl font-normal text-paper">
        De onde veio a resposta
      </h2>
      {sources.length === 0 ? (
        <p className="mt-3 text-sm leading-6 text-paper/75">
          Quando a resposta tiver base nos documentos, as fontes aparecem aqui em linguagem simples.
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
        <details className="border border-line bg-ink/55 p-3" key={source.key}>
          <summary className="cursor-pointer text-sm font-semibold text-paper">
            {source.title} · v{source.version} · página {source.page}
          </summary>
          <dl className="mt-3 space-y-2 text-sm text-paper/75">
            <div>
              <dt className="font-semibold text-pine">Documento</dt>
              <dd>{source.title}</dd>
            </div>
            <div>
              <dt className="font-semibold text-pine">Versão</dt>
              <dd>{source.version}</dd>
            </div>
            <div>
              <dt className="font-semibold text-pine">Página</dt>
              <dd>{source.page}</dd>
            </div>
            <div>
              <dt className="font-semibold text-pine">Seção</dt>
              <dd>{source.section ?? "Não informada"}</dd>
            </div>
            <div>
              <dt className="font-semibold text-pine">Trecho</dt>
              <dd className="mt-1 max-h-28 overflow-y-auto bg-panel p-3 leading-6 text-paper/80">
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
    return <p className="text-sm text-rose">O serviço ainda não está disponível para envio.</p>;
  }
  if (availability.corpus !== "ready") {
    return <p className="text-sm text-amber">A base de documentos ainda está sendo preparada.</p>;
  }
  if (documents.length === 0) {
    return <p className="text-sm text-amber">Ainda não há documentos disponíveis para consulta.</p>;
  }
  return <p className="text-sm text-muted">Tudo pronto. Você já pode enviar sua pergunta.</p>;
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
  return chunks === undefined ? undefined : `${chunks} trechos`;
}
