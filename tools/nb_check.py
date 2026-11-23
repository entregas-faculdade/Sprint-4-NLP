"""Validate notebook structure, secret exposure, outputs, and tagged offline cells.

Lei dona: specs/plan/plan-01.01-alertas-deterministicos-e-fieis.md.
Como se roda: python tools/nb_check.py <notebook> [--executado].
"""

from __future__ import annotations

import argparse
import contextlib
import io
import os
import re
import sys
from pathlib import Path
from typing import Any

import nbformat
from nbformat.validator import NotebookValidationError

ROOT_DIR = Path(__file__).resolve().parents[1]
SECRET_PATTERNS = (
    re.compile(r"sk-or-[A-Za-z0-9_-]+"),
    re.compile(r"OPENROUTER_API_KEY\s*=\s*(?:['\"][^'\"]+['\"]|[^\s,;#]+)"),
)


def _source_has_secret(content: str) -> bool:
    return any(pattern.search(content) for pattern in SECRET_PATTERNS)


def _cell_outputs(cell: dict[str, Any]) -> list[dict[str, Any]]:
    return cell.get("outputs", []) if cell.get("cell_type") == "code" else []


def _validate_secrets(notebook: dict[str, Any]) -> None:
    for cell_index, cell in enumerate(notebook.cells):
        content = "".join(cell.get("source", []))
        output_text = "".join(str(output.get("text", "")) for output in _cell_outputs(cell))
        output_data = " ".join(
            str(value)
            for output in _cell_outputs(cell)
            for value in output.get("data", {}).values()
        )
        if _source_has_secret("\n".join((content, output_text, output_data))):
            raise ValueError(f"Possível chave de API na célula {cell_index}.")


def _validate_outputs(notebook: dict[str, Any], executed: bool) -> None:
    for cell_index, cell in enumerate(notebook.cells):
        if cell.cell_type != "code":
            continue
        outputs = _cell_outputs(cell)
        if not executed and (outputs or cell.execution_count is not None):
            raise ValueError(f"A célula {cell_index} precisa estar sem execução e sem saídas.")
        if executed and cell.execution_count is None:
            raise ValueError(f"A célula {cell_index} não tem execution_count.")
        if any(output.output_type == "error" for output in outputs):
            raise ValueError(f"A célula {cell_index} contém saída de erro.")


def _execute_offline_cells(notebook: dict[str, Any]) -> None:
    namespace: dict[str, Any] = {"__name__": "__main__"}
    previous_directory = Path.cwd()
    previous_path = sys.path.copy()
    try:
        os.chdir(ROOT_DIR)
        sys.path.insert(0, str(ROOT_DIR))
        for cell_index, cell in enumerate(notebook.cells):
            if cell.cell_type != "code" or "offline" not in cell.metadata.get("tags", []):
                continue
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                exec(compile(cell.source, f"{cell_index}", "exec"), namespace)
    except Exception as error:
        raise RuntimeError(f"Falha na execução offline da célula {cell_index}.") from error
    finally:
        os.chdir(previous_directory)
        sys.path[:] = previous_path


def check_notebook(path: Path, executed: bool) -> None:
    notebook = nbformat.read(path, as_version=4)
    nbformat.validate(notebook)
    if not notebook.cells:
        raise ValueError("O notebook não contém células.")
    _validate_secrets(notebook)
    _validate_outputs(notebook, executed)
    _execute_offline_cells(notebook)


def _parse_arguments(arguments: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Valida estrutura e células offline de um notebook.")
    parser.add_argument("notebook", type=Path)
    parser.add_argument("--executado", action="store_true")
    return parser.parse_args(arguments)


def main(arguments: list[str] | None = None) -> int:
    options = _parse_arguments(arguments)
    notebook_path = options.notebook if options.notebook.is_absolute() else ROOT_DIR / options.notebook
    try:
        check_notebook(notebook_path, options.executado)
    except (OSError, ValueError, RuntimeError, NotebookValidationError) as error:
        sys.stderr.write(f"Falha: {error}\n")
        return 1
    sys.stdout.write(f"Notebook válido: {notebook_path.relative_to(ROOT_DIR)}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
