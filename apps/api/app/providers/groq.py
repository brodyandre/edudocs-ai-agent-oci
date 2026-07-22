from __future__ import annotations

import asyncio

from app.core.config import Settings
from app.core.errors import (
    LLMProviderRateLimitError,
    LLMProviderTimeoutError,
    LLMProviderUnavailableError,
)
from app.providers.base import EvidencePayload, LLMResult, ProviderCitation


class GroqProvider:
    name = "groq"

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._client: object | None = None

    def _client_or_raise(self) -> object:
        if self._client is not None:
            return self._client
        if self.settings.groq_api_key is None:
            raise LLMProviderUnavailableError("GROQ_API_KEY não configurada.")
        try:
            from groq import AsyncGroq
        except ImportError as exc:
            raise LLMProviderUnavailableError("Pacote groq não está instalado.") from exc
        self._client = AsyncGroq(api_key=self.settings.groq_api_key.get_secret_value())
        return self._client

    async def generate(
        self,
        question: str,
        evidences: list[EvidencePayload],
        system_prompt: str,
        timeout_seconds: float,
    ) -> LLMResult:
        client = self._client_or_raise()
        evidence_block = "\n\n".join(
            (
                f"[{index}] documento={item.document_id}; versão={item.document_version}; "
                f"página={item.page_start}; seção={item.section or 'não identificada'}\n{item.text}"
            )
            for index, item in enumerate(evidences, start=1)
        )
        user_prompt = (
            "Pergunta do usuário:\n"
            f"{question}\n\n"
            "Evidências disponíveis:\n"
            f"{evidence_block}\n\n"
            "Responda em texto natural e não crie fontes fora das evidências."
        )
        try:
            response = await client.chat.completions.create(
                model=self.settings.groq_model,
                temperature=self.settings.llm_temperature,
                max_tokens=700,
                timeout=timeout_seconds,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
            )
        except asyncio.TimeoutError as exc:
            raise LLMProviderTimeoutError("Timeout ao chamar Groq.") from exc
        except Exception as exc:
            class_name = exc.__class__.__name__.lower()
            status_code = getattr(exc, "status_code", None)
            if status_code == 429 or "ratelimit" in class_name or "rate_limit" in class_name:
                raise LLMProviderRateLimitError("Groq retornou limite de taxa.") from exc
            if "timeout" in class_name:
                raise LLMProviderTimeoutError("Timeout ao chamar Groq.") from exc
            raise LLMProviderUnavailableError("Groq indisponível ou retornou erro.") from exc

        answer = ""
        try:
            answer = str(response.choices[0].message.content or "").strip()
        except (AttributeError, IndexError) as exc:
            raise LLMProviderUnavailableError("Groq retornou resposta inválida.") from exc
        if not answer:
            raise LLMProviderUnavailableError("Groq retornou resposta vazia.")
        selected = evidences[: self.settings.evidence_limit]
        return LLMResult(
            answer=answer,
            used_chunk_ids=[evidence.chunk_id for evidence in selected],
            citations=[
                ProviderCitation(
                    document_id=evidence.document_id,
                    page=evidence.page_start,
                    excerpt=evidence.text[:160],
                )
                for evidence in selected
            ],
        )
