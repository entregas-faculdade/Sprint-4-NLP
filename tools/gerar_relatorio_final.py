"""Preenche os números de entrega/relatorio-final.md a partir de data/saida/*.json e do notebook da Sprint 3.

Como se roda: python tools/gerar_relatorio_final.py          # reescreve os valores dos marcadores
              python tools/gerar_relatorio_final.py --check  # falha se algum marcador não resolve ou diverge

Marcador: <!--{caminho|formato}-->valor<!--/-->. O caminho começa pelo nome do arquivo de saída (sem .json) ou
por `nb3` (valores lidos das saídas executadas de entrega/sprint3_pln_alertas.ipynb) e segue por chaves
separadas por ponto. Um segmento aceita seletor de lista, `chave[campo=valor,campo=valor]`, e a chave `#`
devolve o tamanho. Formatos: d (inteiro), f1/f2/f3 (decimais), p0/p1 (fração em porcentagem), s (texto).
"""

from __future__ import annotations

import argparse
import ast
import json
import re
import sys
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parents[1]
OUTPUT_DIR = ROOT_DIR / "data" / "saida"
REPORT_PATH = ROOT_DIR / "entrega" / "relatorio-final.md"
ALERTS_NOTEBOOK = ROOT_DIR / "entrega" / "sprint3_pln_alertas.ipynb"

MARKER = re.compile(r"<!--\{(?P<path>[^}|]+)\|(?P<fmt>[a-z0-9]+)\}-->(?P<value>.*?)<!--/-->", re.S)
SEGMENT = re.compile(r"^(?P<key>[^\[\]]*)(?:\[(?P<selector>[^\]]+)\])?$")
NOTEBOOK_PATTERNS = {
    "rouge_template": (r"ROUGE template: (\{.*\})", "dict"),
    "rouge_llm": (r"ROUGE LLM: (\{.*\})", "dict"),
    "fidelidade_templates_pct": (r"Fidelidade dos templates: ([\d.]+)%", "number"),
    "taxa_aceitacao_pct": (r"Taxa de aceitação: ([\d.]+)%", "number"),
    "alert_counts": (r"Contagem por severidade: (\{.*\})", "dict"),
    "readings": (r"Leituras carregadas: (\d+)", "number"),
    "events_total": (r"Total de eventos: (\d+)", "number"),
}
MISSING = object()


class InvalidMarker(Exception):
    """Marcador cujo caminho não existe nas saídas ou cujo formato é desconhecido."""


def _notebook_output_text(notebook_path: Path) -> str:
    notebook = json.loads(notebook_path.read_text(encoding="utf-8"))
    parts = []
    for cell in notebook.get("cells", []):
        for output in cell.get("outputs", []):
            parts.append("".join(output.get("text", "")))
    return "\n".join(parts)


def _notebook_value(text: str, pattern: str, kind: str) -> Any:
    found = re.search(pattern, text)
    if found is None:
        return MISSING
    return ast.literal_eval(found.group(1)) if kind == "dict" else float(found.group(1))


def load_sources(output_dir: Path, notebook_path: Path) -> dict[str, Any]:
    sources: dict[str, Any] = {
        file.stem: json.loads(file.read_text(encoding="utf-8")) for file in output_dir.glob("*.json")
    }
    text = _notebook_output_text(notebook_path)
    values = {name: _notebook_value(text, pattern, kind) for name, (pattern, kind) in NOTEBOOK_PATTERNS.items()}
    sources["nb3"] = {name: value for name, value in values.items() if value is not MISSING}
    return sources


def _apply_selector(items: Any, selector: str) -> Any:
    if not isinstance(items, list):
        return MISSING
    filters = [pair.split("=", 1) for pair in selector.split(",")]
    for item in items:
        if isinstance(item, dict) and all(str(item.get(field)) == value for field, value in filters):
            return item
    return MISSING


def _step(current: Any, segment: str) -> Any:
    parts = SEGMENT.match(segment)
    if parts is None:
        return MISSING
    key, selector = parts.group("key"), parts.group("selector")
    if key == "#":
        current = len(current) if hasattr(current, "__len__") else MISSING
    elif key:
        current = current.get(key, MISSING) if isinstance(current, dict) else MISSING
    if current is MISSING or selector is None:
        return current
    return _apply_selector(current, selector)


def resolve(sources: dict[str, Any], path: str) -> Any:
    current: Any = sources
    for segment in path.split("."):
        current = _step(current, segment)
        if current is MISSING:
            raise InvalidMarker(f"caminho sem valor nas saídas: {path}")
    return current


def _decimal(value: float, places: int) -> str:
    return f"{value:.{places}f}".replace(".", ",")


def format_value(value: Any, fmt: str) -> str:
    if fmt == "s":
        return str(value)
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise InvalidMarker(f"formato {fmt} exige número, veio {type(value).__name__}")
    if fmt == "d":
        return str(int(round(value)))
    if fmt in ("f1", "f2", "f3"):
        return _decimal(value, int(fmt[1]))
    if fmt in ("p0", "p1"):
        return _decimal(value * 100, int(fmt[1])) + " %"
    raise InvalidMarker(f"formato desconhecido: {fmt}")


def fill_markers(text: str, sources: dict[str, Any]) -> tuple[str, list[str]]:
    errors: list[str] = []

    def replace(found: re.Match[str]) -> str:
        try:
            value = format_value(resolve(sources, found.group("path")), found.group("fmt"))
        except InvalidMarker as error:
            errors.append(str(error))
            return found.group(0)
        return f"<!--{{{found.group('path')}|{found.group('fmt')}}}-->{value}<!--/-->"

    return MARKER.sub(replace, text), errors


def check_document(text: str, sources: dict[str, Any]) -> list[str]:
    """Erros de um documento: marcador sem valor, valor divergente das saídas ou nenhum marcador."""
    filled, errors = fill_markers(text, sources)
    if not MARKER.search(text):
        errors.append("o documento não tem nenhum marcador de métrica")
    old_values = [found.group("value") for found in MARKER.finditer(text)]
    new_values = [found.group("value") for found in MARKER.finditer(filled)]
    for old, new in zip(old_values, new_values):
        if old != new:
            errors.append(f"valor divergente das saídas: documento '{old[:40]}', saída '{new[:40]}'")
    return errors


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--check", action="store_true", help="só confere; não reescreve o documento")
    parser.add_argument("--documento", type=Path, default=REPORT_PATH)
    return parser.parse_args(argv)


def _report(errors: list[str]) -> None:
    for error in errors:
        print(f"ERRO: {error}", file=sys.stderr)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    sources = load_sources(OUTPUT_DIR, ALERTS_NOTEBOOK)
    text = args.documento.read_text(encoding="utf-8")
    if args.check:
        errors = check_document(text, sources)
        _report(errors)
        print(f"{len(MARKER.findall(text))} marcadores conferidos; {len(errors)} erro(s).")
        return 1 if errors else 0
    filled, errors = fill_markers(text, sources)
    _report(errors)
    if errors:
        return 1
    args.documento.write_text(filled, encoding="utf-8", newline="\n")
    print(f"{len(MARKER.findall(filled))} marcadores preenchidos em {args.documento.name}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
