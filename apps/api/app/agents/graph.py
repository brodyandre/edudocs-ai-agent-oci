from __future__ import annotations

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
) -> Callable[[AgentState], Awaitable[AgentState]]:
    async def wrapped(state: AgentState) -> AgentState:
        return func(state, deps)

    return wrapped


def _wrap_async(
    func: Callable[[AgentState, AgentDependencies], Awaitable[AgentState]],
    deps: AgentDependencies,
) -> Callable[[AgentState], Awaitable[AgentState]]:
    async def wrapped(state: AgentState) -> AgentState:
        return await func(state, deps)

    return wrapped


async def after_validation(state: AgentState) -> str:
    if state.get("error"):
        return "insufficient"
    return "prepare"


async def after_evaluation(state: AgentState) -> str:
    if state.get("sufficient_context"):
        return "generate"
    if int(state.get("retrieval_attempt", 0)) < 2:
        return "reformulate"
    return "insufficient"


async def finalize(state: AgentState) -> AgentState:
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
    graph.add_edge("validar_citacoes", "finalizar")
    graph.add_edge("evidencia_insuficiente", "finalizar")
    graph.set_finish_point("finalizar")
    return graph.compile()
