from __future__ import annotations

import asyncio
import threading
from collections.abc import Awaitable, Callable

from langgraph.graph import StateGraph

from app.agents.nodes import (
    AgentDependencies,
    evaluate_sufficiency,
    generate_answer,
    insufficient_evidence,
    prepare_query,
    reformulate_query,
    retrieve_evidence,
    validate_citations_node,
    validate_question,
)
from app.agents.state import AgentState


def _wrap_sync(
    func: Callable[[AgentState, AgentDependencies], AgentState],
    deps: AgentDependencies,
) -> Callable[[AgentState], AgentState]:
    def wrapped(state: AgentState) -> AgentState:
        return func(state, deps)

    return wrapped


def _wrap_async(
    func: Callable[[AgentState, AgentDependencies], Awaitable[AgentState]],
    deps: AgentDependencies,
) -> Callable[[AgentState], AgentState]:
    def wrapped(state: AgentState) -> AgentState:
        return _run_awaitable(func(state, deps))

    return wrapped


def _run_awaitable(awaitable: Awaitable[AgentState]) -> AgentState:
    # LangGraph 0.2.x executes this compiled graph through the synchronous API.
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(awaitable)

    result: AgentState | None = None
    error: BaseException | None = None

    def run() -> None:
        nonlocal error, result
        try:
            result = asyncio.run(awaitable)
        except BaseException as exc:
            error = exc

    thread = threading.Thread(target=run)
    thread.start()
    thread.join()
    if error is not None:
        raise error
    if result is None:
        raise RuntimeError("Nó assíncrono não retornou estado.")
    return result


def after_validation(state: AgentState) -> str:
    if state.get("error"):
        return "insufficient"
    return "prepare"


def after_evaluation(state: AgentState) -> str:
    if state.get("sufficient_context"):
        return "generate"
    if int(state.get("retrieval_attempt", 0)) < 2:
        return "reformulate"
    return "insufficient"


def after_citation_validation(state: AgentState) -> str:
    if state.get("answerable") and state.get("validated_sources"):
        return "finish"
    return "insufficient"


def finalize(state: AgentState) -> AgentState:
    return state


def build_graph(deps: AgentDependencies):
    graph = StateGraph(AgentState)
    graph.add_node("validar_pergunta", _wrap_sync(validate_question, deps))
    graph.add_node("preparar_consulta", _wrap_sync(prepare_query, deps))
    graph.add_node("recuperar_evidencias", _wrap_sync(retrieve_evidence, deps))
    graph.add_node("avaliar_suficiencia", _wrap_sync(evaluate_sufficiency, deps))
    graph.add_node("reformular_consulta", _wrap_sync(reformulate_query, deps))
    graph.add_node("gerar_resposta", _wrap_async(generate_answer, deps))
    graph.add_node("validar_citacoes", _wrap_sync(validate_citations_node, deps))
    graph.add_node("evidencia_insuficiente", _wrap_sync(insufficient_evidence, deps))
    graph.add_node("finalizar", finalize)

    graph.set_entry_point("validar_pergunta")
    graph.add_conditional_edges(
        "validar_pergunta",
        after_validation,
        {"prepare": "preparar_consulta", "insufficient": "evidencia_insuficiente"},
    )
    graph.add_edge("preparar_consulta", "recuperar_evidencias")
    graph.add_edge("recuperar_evidencias", "avaliar_suficiencia")
    graph.add_conditional_edges(
        "avaliar_suficiencia",
        after_evaluation,
        {
            "generate": "gerar_resposta",
            "reformulate": "reformular_consulta",
            "insufficient": "evidencia_insuficiente",
        },
    )
    graph.add_edge("reformular_consulta", "recuperar_evidencias")
    graph.add_edge("gerar_resposta", "validar_citacoes")
    graph.add_conditional_edges(
        "validar_citacoes",
        after_citation_validation,
        {"finish": "finalizar", "insufficient": "evidencia_insuficiente"},
    )
    graph.add_edge("evidencia_insuficiente", "finalizar")
    graph.set_finish_point("finalizar")
    return graph.compile()
