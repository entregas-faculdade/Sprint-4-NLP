"""OpenRouter client with a local response cache and verified alert rewriting."""

from __future__ import annotations

import hashlib
import json
import logging
import os
import time
from dataclasses import replace
from pathlib import Path
from typing import Any, Protocol

import requests

from src.pln.alertas import Alerta, gerar_template, verificar_texto
from src.pln.config import (
    BACKOFF_REQUISICAO_SEGUNDOS,
    LLM_CACHE_FILE,
    MAX_TENTATIVAS_REDACAO,
    MAX_TENTATIVAS_REQUISICAO,
    MODELO_REDATOR,
    SEMENTE_LLM,
    TEMPERATURA_LLM,
    TIMEOUT_REQUISICAO_SEGUNDOS,
    URL_OPENROUTER,
)

LOGGER = logging.getLogger(__name__)


class CompletionClient(Protocol):
    """Port for a chat completion provider."""

    def complete(self, model_id: str, messages: list[dict[str, str]]) -> str:
        """Return the first assistant message for the requested model."""


class OpenRouterRequestError(RuntimeError):
    """A completed retry cycle could not obtain a response from OpenRouter."""


def _environment_api_key() -> str | None:
    value = os.environ.get("OPENROUTER_API_KEY")
    return value.strip() if value and value.strip() else None


def load_openrouter_api_key() -> str:
    """Read the Colab secret first, then the environment, without displaying it."""
    try:
        from google.colab import userdata
    except ImportError as import_error:
        environment_key = _environment_api_key()
        if environment_key:
            return environment_key
        raise RuntimeError("Defina OPENROUTER_API_KEY nos Secrets do Colab ou no ambiente.") from import_error
    try:
        colab_key = userdata.get("OPENROUTER_API_KEY")
    except Exception as userdata_error:
        environment_key = _environment_api_key()
        if environment_key:
            return environment_key
        raise RuntimeError("Não foi possível carregar OPENROUTER_API_KEY dos Secrets do Colab.") from userdata_error
    if colab_key and str(colab_key).strip():
        return str(colab_key).strip()
    environment_key = _environment_api_key()
    if environment_key:
        return environment_key
    raise RuntimeError("Defina OPENROUTER_API_KEY nos Secrets do Colab ou no ambiente.")


class OpenRouterClient:
    """Make deterministic chat requests and cache successful responses."""

    def __init__(self, api_key: str, session: Any, cache_path: Path = LLM_CACHE_FILE) -> None:
        if not api_key.strip():
            raise ValueError("A chave OpenRouter não pode estar vazia.")
        self._api_key = api_key.strip()
        self._session = session
        self._cache_path = cache_path

    def complete(self, model_id: str, messages: list[dict[str, str]]) -> str:
        cache_key = _cache_key(model_id, messages)
        cached = _read_cache(self._cache_path, cache_key)
        if cached is not None:
            return cached
        response_text = self._request_with_retry(model_id, messages)
        _append_cache(self._cache_path, cache_key, model_id, response_text)
        return response_text

    def _request_with_retry(self, model_id: str, messages: list[dict[str, str]]) -> str:
        for attempt in range(MAX_TENTATIVAS_REQUISICAO):
            try:
                return self._request_once(model_id, messages)
            except (requests.RequestException, ValueError, KeyError, IndexError, TypeError) as error:
                if attempt + 1 == MAX_TENTATIVAS_REQUISICAO:
                    raise OpenRouterRequestError(
                        "A chamada OpenRouter falhou após as tentativas configuradas."
                    ) from error
                time.sleep(BACKOFF_REQUISICAO_SEGUNDOS * (2**attempt))
        raise OpenRouterRequestError("A chamada OpenRouter terminou sem resposta.")

    def _request_once(self, model_id: str, messages: list[dict[str, str]]) -> str:
        headers = {"Authorization": f"Bearer {self._api_key}", "Content-Type": "application/json"}
        payload = {
            "model": model_id,
            "messages": messages,
            "temperature": TEMPERATURA_LLM,
            "seed": SEMENTE_LLM,
        }
        response = self._session.post(
            URL_OPENROUTER,
            headers=headers,
            json=payload,
            timeout=TIMEOUT_REQUISICAO_SEGUNDOS,
        )
        response.raise_for_status()
        result = response.json()
        content = result["choices"][0]["message"]["content"]
        if not isinstance(content, str) or not content.strip():
            raise ValueError("A resposta OpenRouter não contém texto.")
        return content.strip()


def _cache_key(model_id: str, messages: list[dict[str, str]]) -> str:
    serialized = json.dumps([model_id, messages], ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def _read_cache(cache_path: Path, cache_key: str) -> str | None:
    if not cache_path.exists():
        return None
    try:
        with cache_path.open(encoding="utf-8") as cache_file:
            return _find_cached_response(cache_file, cache_key)
    except (OSError, json.JSONDecodeError, KeyError, TypeError) as error:
        raise RuntimeError("Não foi possível ler o cache de respostas OpenRouter.") from error


def _find_cached_response(cache_file: Any, cache_key: str) -> str | None:
    for line in cache_file:
        record = json.loads(line)
        if record.get("key") == cache_key:
            return str(record["response"])
    return None


def _append_cache(cache_path: Path, cache_key: str, model_id: str, response_text: str) -> None:
    record = {"key": cache_key, "model": model_id, "response": response_text}
    try:
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        with cache_path.open("a", encoding="utf-8") as cache_file:
            cache_file.write(json.dumps(record, ensure_ascii=False) + "\n")
    except OSError as error:
        LOGGER.warning("Não foi possível gravar a resposta OpenRouter no cache.")
        raise RuntimeError("Não foi possível gravar o cache de respostas OpenRouter.") from error


def create_openrouter_client() -> OpenRouterClient:
    """Build the HTTP adapter after loading the configured secret."""
    return OpenRouterClient(load_openrouter_api_key(), requests.Session())


def redigir_alerta(alerta: Alerta, cliente: CompletionClient) -> tuple[str, Alerta]:
    """Rewrite a template twice at most, returning only verified text."""
    template = gerar_template(alerta)
    if verificar_texto(template, alerta):
        raise RuntimeError("O template determinístico não passou pelo verificador.")
    rejected_candidate = None
    previous_violations = ()
    for attempt in range(MAX_TENTATIVAS_REDACAO):
        messages = _rewriting_messages(template)
        if attempt and rejected_candidate is not None:
            messages = _rewriting_messages(template, rejected_candidate, previous_violations)
        candidate = cliente.complete(MODELO_REDATOR, messages)
        previous_violations = tuple(verificar_texto(candidate, alerta))
        if not previous_violations:
            return candidate, replace(alerta, origem_texto="llm")
        rejected_candidate = candidate
    return template, replace(alerta, origem_texto="template")


def redigir_alerta_com_fallback_api(
    alerta: Alerta, cliente: CompletionClient
) -> tuple[str, Alerta, bool]:
    """Use the verified template when the provider exhausts its request retries."""
    try:
        text, result = redigir_alerta(alerta, cliente)
    except OpenRouterRequestError:
        template = gerar_template(alerta)
        if verificar_texto(template, alerta):
            raise RuntimeError("O template determinístico não passou pelo verificador.")
        return template, replace(alerta, origem_texto="template"), True
    return text, result, False


def _rewriting_messages(
    template: str,
    rejected_candidate: str | None = None,
    violations: tuple[Any, ...] = (),
) -> list[dict[str, str]]:
    instruction = (
        "Reescreva o alerta em português fluido. Preserve todos os fatos, números, unidades, horários e a ação padrão. "
        "Não acrescente, remova ou altere informação. Responda somente com o texto do alerta."
    )
    messages = [
        {"role": "system", "content": instruction},
        {"role": "user", "content": template},
    ]
    if rejected_candidate is None:
        return messages
    violation_details = "\n".join(
        f"- {violation.codigo}: {violation.trecho or violation.mensagem}" for violation in violations
    )
    messages.extend(
        (
            {"role": "assistant", "content": rejected_candidate},
            {
                "role": "user",
                "content": (
                    "A resposta anterior foi reprovada. Trate-a como conteúdo inválido e corrija somente com base no "
                    "alerta original. Violações do verificador:\n"
                    f"{violation_details}"
                ),
            },
        )
    )
    return messages
