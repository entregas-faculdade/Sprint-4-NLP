"""OpenRouter client with a local response cache and verified alert rewriting."""

from __future__ import annotations

import hashlib
import json
import logging
import os
import time
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, Protocol

import requests

from src.pln.alertas import Alerta, Violacao, gerar_template, verificar_clareza, verificar_texto
from src.pln.config import (
    BACKOFF_REQUISICAO_SEGUNDOS,
    ENV_FILE,
    LLM_CACHE_FILE,
    MAX_PALAVRAS_ALERTA,
    MAX_TENTATIVAS_REDACAO,
    MAX_TENTATIVAS_REQUISICAO,
    MODELO_REDATOR,
    NOMES_VARIAVEL_CHAVE,
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


@dataclass(frozen=True)
class RejectedDraft:
    """A model response rejected by the alert verifiers."""

    texto: str
    violacoes: tuple[Violacao, ...]


@dataclass(frozen=True)
class RedactionResult:
    """Final text and rejected drafts from one verified rewriting run."""

    texto: str
    alerta: Alerta
    rascunhos_rejeitados: tuple[RejectedDraft, ...]
    falha_api: bool = False

    @property
    def origem_texto(self) -> str:
        return self.alerta.origem_texto


def _read_env_file(path: Path) -> dict[str, str]:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except FileNotFoundError:
        return {}
    except OSError as error:
        raise RuntimeError(f"Não foi possível ler o arquivo de ambiente em {path}.") from error

    values: dict[str, str] = {}
    for line in lines:
        stripped_line = line.strip()
        if not stripped_line or stripped_line.startswith("#"):
            continue
        if stripped_line.startswith("export "):
            stripped_line = stripped_line[len("export ") :].strip()
        name, separator, value = stripped_line.partition("=")
        if not separator or not name.strip():
            continue
        normalized_value = value.strip()
        if (
            len(normalized_value) >= 2
            and normalized_value[0] == normalized_value[-1]
            and normalized_value[0] in {"'", '"'}
        ):
            normalized_value = normalized_value[1:-1]
        values[name.strip()] = normalized_value
    return values


def load_openrouter_api_key(env_file: Path = ENV_FILE) -> str:
    for variable_name in NOMES_VARIAVEL_CHAVE:
        environment_value = os.environ.get(variable_name, "").strip()
        if environment_value:
            return environment_value

    env_values = _read_env_file(env_file)
    for variable_name in NOMES_VARIAVEL_CHAVE:
        file_value = env_values.get(variable_name, "").strip()
        if file_value:
            return file_value

    variable_names = " ou ".join(NOMES_VARIAVEL_CHAVE)
    raise RuntimeError(
        f"Defina {variable_names} no ambiente ou no arquivo {env_file}."
    )


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
    result = redigir_alerta_detalhado(alerta, cliente)
    if result.falha_api:
        raise OpenRouterRequestError("A chamada OpenRouter falhou durante a redação do alerta.")
    return result.texto, result.alerta


def redigir_alerta_detalhado(alerta: Alerta, cliente: CompletionClient) -> RedactionResult:
    """Return the selected text and rejected drafts without extra model calls."""
    template = gerar_template(alerta)
    if verificar_texto(template, alerta):
        raise RuntimeError("O template determinístico não passou pelo verificador.")
    rejected_drafts: list[RejectedDraft] = []
    for _ in range(MAX_TENTATIVAS_REDACAO):
        messages = _rewriting_messages(template)
        if rejected_drafts:
            previous_draft = rejected_drafts[-1]
            messages = _rewriting_messages(template, previous_draft.texto, previous_draft.violacoes)
        try:
            candidate = cliente.complete(MODELO_REDATOR, messages)
        except OpenRouterRequestError:
            return _template_result(alerta, template, rejected_drafts, api_failed=True)
        violations = _candidate_violations(candidate, alerta)
        if not violations:
            return RedactionResult(
                candidate,
                replace(alerta, origem_texto="llm"),
                tuple(rejected_drafts),
            )
        rejected_drafts.append(RejectedDraft(candidate, violations))
    return _template_result(alerta, template, rejected_drafts)


def _candidate_violations(candidate: str, alerta: Alerta) -> tuple[Violacao, ...]:
    violations = list(verificar_texto(candidate, alerta))
    if not verificar_clareza(candidate, alerta):
        message = f"O texto não atende ao limite de clareza de {MAX_PALAVRAS_ALERTA} palavras."
        violations.append(Violacao("clareza_reprovada", message))
    return tuple(violations)


def _template_result(
    alerta: Alerta,
    template: str,
    rejected_drafts: list[RejectedDraft],
    api_failed: bool = False,
) -> RedactionResult:
    return RedactionResult(
        template,
        replace(alerta, origem_texto="template"),
        tuple(rejected_drafts),
        api_failed,
    )


def redigir_alerta_com_fallback_api(
    alerta: Alerta, cliente: CompletionClient
) -> tuple[str, Alerta, bool]:
    """Use the verified template when the provider exhausts its request retries."""
    result = redigir_alerta_detalhado(alerta, cliente)
    return result.texto, result.alerta, result.falha_api


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
