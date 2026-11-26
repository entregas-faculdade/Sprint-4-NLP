# Assistente de troubleshooting para motores elétricos (PLN) — Sprints 3 e 4

Entrega do Challenge FIAP × Forzy (Processamento de Linguagem Natural) sobre um digital twin do motor elétrico WEG W22. O projeto:

1. transforma leituras de sensores em **alertas** e **relatórios** em português, sem afirmar nada além dos dados;
2. **classifica eventos** em cinco categorias (manutenção corretiva e preventiva, anomalia elétrica e mecânica, operação normal);
3. responde perguntas de troubleshooting por **RAG** sobre o catálogo técnico do W22, citando **página e seção**, com confiança calculada e
   abstenção quando o catálogo não sustenta a resposta.

A regra de fundo: todo fato (valor, limiar, página, seção) nasce de código; o LLM só redige, e todo texto de LLM passa por um verificador.

## Entregáveis

| Item | Onde |
|---|---|
| Notebook da Sprint 3 (alertas, classificação e relatório) | [`notebooks/sprint3_pln_alertas.ipynb`](notebooks/sprint3_pln_alertas.ipynb) |
| Notebook da Sprint 4 (RAG, assistente, avaliação e cenários) | [`notebooks/sprint4_pln_rag.ipynb`](notebooks/sprint4_pln_rag.ipynb) |
| Conjuntos de teste com referências | [`data/alertas_teste.json`](data/alertas_teste.json), [`data/eventos_rotulados.json`](data/eventos_rotulados.json), [`data/relatorio_referencia.json`](data/relatorio_referencia.json), [`data/avaliacao_rag.json`](data/avaliacao_rag.json), [`data/juiz_calibracao.json`](data/juiz_calibracao.json) |
| Documento final unificado | [`docs/relatorio-final.md`](docs/relatorio-final.md) |
| Matriz das críticas do professor (F1–F7) | [`docs/matriz-criticas.md`](docs/matriz-criticas.md) |
| Roteiro do vídeo | [`docs/roteiro-video.md`](docs/roteiro-video.md) |
| Vídeo (3 a 5 min, "não listado" no YouTube) | <!-- VIDEO_URL --> _link a ser colado aqui_ |
| Saídas das execuções | [`data/saida/`](data/saida/) |

## Estrutura

```
src/pln/        lógica: sensores, alertas, llm, classificacao, relatorio, estado, rag, assistente, avaliacao, cenarios, config
notebooks/      os dois notebooks (só orquestram e exibem; a lógica está em src/pln/)
tests/          testes (pytest)
tools/          nb_check.py (confere notebook) e gerar_relatorio_final.py (preenche os números do documento final)
data/           dados de origem, conjuntos de teste e, em data/saida/, as saídas das execuções
docs/           catálogo W22 (PDF), documento final, matriz, roteiro e feedback do professor
specs/          especificações do projeto
```

## Como rodar localmente

A execução é **100 % local** (sem Colab). Pré-requisito: Python 3.11 ou superior. Comandos em `bash`, a partir da raiz do repositório.

```bash
python -m venv .venv
source .venv/bin/activate          # no Windows (Git Bash): source .venv/Scripts/activate
pip install -r requirements.txt
cp .env.example .env
```

Abra o `.env` e preencha a chave do OpenRouter na variável `OPEN-ROUTER-API-KEY` (o código também aceita `OPENROUTER_API_KEY` no ambiente).
O `.env` está no `.gitignore`: **nunca versione a chave**, nem a imprima em saída de notebook. Sem chave, a execução falha citando só o
nome da variável e o caminho do arquivo. A primeira execução baixa os modelos de embedding e de reranking (alguns minutos).

Execute os notebooks **na ordem** (o da Sprint 4 usa os alertas exportados pelo da Sprint 3), sem `--allow-errors`:

```bash
jupyter nbconvert --to notebook --execute --inplace notebooks/sprint3_pln_alertas.ipynb
jupyter nbconvert --to notebook --execute --inplace notebooks/sprint4_pln_rag.ipynb \
  --ExecutePreprocessor.startup_timeout=300 --ExecutePreprocessor.iopub_timeout=120
```

As chamadas ao LLM ficam em cache (`data/saida/cache_llm.jsonl`), então repetir a execução é barato e as saídas saem iguais. Para conferir o resultado:

```bash
python tools/nb_check.py notebooks/sprint3_pln_alertas.ipynb --executado
python tools/nb_check.py notebooks/sprint4_pln_rag.ipynb --executado
python tools/gerar_relatorio_final.py --check
```

## Como rodar os testes

```bash
python -m pytest tests -q
```

Os testes rodam offline, com LLM falso. Os que usam o PDF real dependem da versão de `PyMuPDF` fixada em `requirements.txt` (com outra versão,
parte dos testes de extração falha); os marcados `modelos` são pulados quando os pesos dos modelos não estão em cache.

## Documento final e números

Os números de `docs/relatorio-final.md` não são digitados: vêm de `data/saida/*.json` por `python tools/gerar_relatorio_final.py`, e o
`--check` falha se o documento divergir das saídas.

## Licença e avisos

- **Licença do código:** ainda não definida pelo dono do repositório (pendente; não há arquivo `LICENSE`).
- **O PDF em `docs/` é material da WEG** (catálogo comercial do motor W22), usado aqui só para fins acadêmicos; seus direitos pertencem à WEG.
- Os dados de sensores e os eventos rotulados são de um ativo de teste e sintéticos, respectivamente.
