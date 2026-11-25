---
tipo: "plan"
familia: "02"
item: "R02.1"
titulo: "Construir RAG com página, seção e estado operacional na busca"
dominio: "Sprint 4 — RAG e assistente"
status: "🟢 Aprovada"
prioridade: "Alta"
tags: ["plan", "sprint-4", "rag", "F3", "F4"]
relacionados: ["[[00-contexto]]", "[[01.02-classificacao-e-relatorio]]"]
depende_de: ""
destino_sintese: "specs/02.01-pipeline-rag.md + 00-contexto.md"
---

# 1. Objetivo

O notebook `sprint4_pln_rag.ipynb` indexa o catálogo W22 em chunks que **preservam página e seção**, e o retriever **usa o estado
operacional do ativo na busca** (não só no prompt), com embeddings e reranker multilíngues (requisitos **F3** e **F4**).

# 2. Contexto

- Entrega anterior: chunking por parágrafo sem metadados; embeddings `all-MiniLM-L6-v2` e reranker `ms-marco-MiniLM` (**ingleses**) sobre
  PDF em português; estado injetado só no prompt; 7 de 20 perguntas com relevancy ≤ 2 por falha de recuperação. Feedback: "incluam o estado
  operacional na recuperação, preservem página e seção das fontes".
- O PDF (`docs/WEG-w22-motor-eletrico-trifasico-brochure.pdf`): 52 páginas, texto extraível. Cada página traz o cabeçalho
  `www.weg.net … Motor Elétrico Trifásico W22 … <nº>` (ruído a remover; dá o número da página impressa). Seções numeradas
  (`4.1 Sistema de Ventilação e Nível de Ruído`, na p. 13). Há tabelas (carcaça, dados elétricos, p. 25 e 37 em diante).
- A comparação honesta **antes × depois** exige manter a configuração antiga como preset (`LEGADO`) ao lado da nova (`NOVO`).
- Usa `src/pln/alertas.py` (plan 01.01) para obter os alertas que formam o estado.

# 3. Escopo

## 3.1 Dentro
- `requirements.txt` — acrescentar `pymupdf`, `chromadb`, `sentence-transformers` (versões fixadas)
- `src/pln/config.py` — constantes de RAG (modelos de embedding/reranker, tamanhos de chunk, `K_BUSCA`, `K_FINAL`, `PESO_ESTADO`)
- `src/pln/estado.py` — `EstadoOperacional` construído dos alertas
- `data/termos_estado.json` — **novo**: termos de consulta e seções-alvo por domínio de falha/sensor
- `src/pln/rag.py` — extração, chunking, índice, retriever, presets `LEGADO` e `NOVO`
- `tests/test_estado.py` · `tests/test_rag.py` (offline, com embedder/reranker falsos) · `tests/test_rag_modelos.py` (marcado `modelos`, roda só quando os modelos baixam)
- `notebooks/sprint4_pln_rag.ipynb` — **reconstruído** com as seções 0 a 6 abaixo (as antigas saem)

## 3.2 Fora
- Geração de resposta, persona, memória, confiança — plan 02.02
- Métricas, gabarito e juiz — plan 02.03
- Notebook da Sprint 3, `data/dados-w22.csv`, `docs/*.pdf`, `specs/`

# 4. Referências obrigatórias

| Tipo | Referência | Por quê |
|---|---|---|
| Spec fixa | `specs/01.01-alertas-deterministicos.md` · `specs/01.02-classificacao-e-relatorio.md` | alertas e janela que formam o estado |
| Contexto | `00-contexto.md` · `00-knowledge.md` | regras inegociáveis (§2, §7) |
| Requisito | `docs/feedback-professor.md` | F3, F4 |
| **Skill** | `padrao-escrita` + `padrao-python` · `test-unitario` · `code-auditoria-padrao` | escrita, testes, gate |
| Código | `src/pln/config.py` · `src/pln/alertas.py` · `tools/nb_check.py` | reaproveitar |
| Dados | `docs/WEG-w22-motor-eletrico-trifasico-brochure.pdf` | corpus; ler p. 3, 13, 25, 37 para ver cabeçalho, seção e tabelas |
| Legado (só leitura) | `notebooks/sprint4_pln_rag.ipynb` (versão antiga) | para reproduzir o preset `LEGADO` |

# 5. Instruções de execução

1. [dirigido] **Extração.** Em `rag.py`, ler o PDF por página (`pymupdf`), remover o cabeçalho `www.weg.net … <nº>` e capturar o número
   da página impressa; extrair tabelas com `page.find_tables()` e serializar cada linha como `Coluna: valor; …` (tabela não vira
   sopa de células). Detectar títulos de seção por padrão numérico (`^\d+(\.\d+)*[.\s]+\S`) e manter a **seção corrente** entre páginas.
2. [dirigido] **Chunking NOVO.** Chunk = trecho de **uma única seção** (nunca atravessa o título seguinte), até `CHUNK_MAX` caracteres
   (padrão 900), quebrando em fim de parágrafo/frase; sobreposição `CHUNK_OVERLAP` (padrão 100). Cada chunk guarda `id`, `pagina`,
   `pagina_fim`, `secao` (número, ex. `4.1`), `secao_titulo`, `texto`; o texto **embutido** é `"[Seção 4.1 — Sistema de Ventilação…
   | p. 13] <texto>"`. Chunks com < 40 caracteres úteis são descartados ou fundidos ao vizinho. **Chunking LEGADO** = o parágrafo antigo
   (1000 caracteres, sem metadados) para o preset de comparação.
3. [dirigido] **Índice.** ChromaDB em memória (`EphemeralClient`), distância cosseno, metadados `pagina`, `secao`, `secao_titulo`.
   Embeddings `intfloat/multilingual-e5-base` com prefixos `query: ` / `passage: ` (preset `NOVO`); `all-MiniLM-L6-v2` no `LEGADO`. Modelos
   de embedding e reranker injetáveis (protocolo mínimo) para teste offline; `sentence_transformers`/`chromadb` importados **dentro**
   das funções, para que `pytest` rode sem baixar nada.
4. [dirigido] **Estado operacional.** `EstadoOperacional` (em `estado.py`) reúne, de uma lista de `Alerta`s e do último instante:
   `ativo`, `alertas_ativos` (id, grandeza, severidade, valor_max, unidade, início), `dominio_falha` por alerta
   (`temperatura`→"térmica", `corrente`→"elétrica", `vibração` e `velocidade`→"mecânica"), `severidade_geral`, e `texto()` determinístico
   (frases só com campos dos alertas, com os ids). Sem alertas: `operacao_normal=True`.
5. [dirigido] **Termos do estado.** `data/termos_estado.json` mapeia cada grandeza/domínio para **termos de consulta em português
   presentes no catálogo** (ex.: corrente → "corrente nominal sobrecarga tensão frequência proteção térmica"; vibração → "vibração
   mancal rolamento balanceamento nível de vibração"; temperatura → "temperatura enrolamento classe de isolamento elevação de
   temperatura proteção térmica ventilação"; velocidade → "velocidade rotação escorregamento frequência inversor") e **trechos de título
   de seção alvo**. Montar a tabela lendo o PDF e conferindo cada termo por busca no texto (nenhum termo sem ocorrência). Sem estado
   ou `operacao_normal` → nenhum termo extra.
6. [dirigido] **Retriever.** `Retriever.buscar(pergunta, estado=None, k_busca=K_BUSCA, k_final=K_FINAL)`: (a) consulta expandida =
   pergunta + termos do estado; (b) busca densa top `K_BUSCA`; (c) reranker multilíngue (`cross-encoder/mmarco-mMiniLMv2-L12-H384-v1`;
   `LEGADO`: `cross-encoder/ms-marco-MiniLM-L-6-v2`) pontua `(pergunta, chunk)`; (d) normalizar min-máx dentro do conjunto e somar
   `PESO_ESTADO` quando o título da seção casa com as seções-alvo do estado; (e) devolver `k_final` itens com `texto`, `pagina`,
   `secao`, `secao_titulo`, `score_denso`, `score_rerank`, `score_final`. `estado=None` desliga (d) **e** os termos extras — é a
   ablação "sem estado". `PESO_ESTADO` padrão 0,15; a plan 02.03 pode recalibrar no `dev`.
7. [dirigido] Testes. **Offline** (skill `test-unitario`; embedder/reranker falsos determinísticos): cabeçalho removido; página correta
   em amostra conhecida; todo chunk com `pagina` ∈ [1, 52] e `secao` não vazia em ≥ 90 %; nenhum chunk > `CHUNK_MAX` + folga nem
   atravessa título; título `4.1` na p. 13; tabela serializada com `Coluna: valor`; estado → termos e `dominio_falha` corretos;
   `estado=None` ≡ sem boost; boost só quando a seção casa. **Com modelos** (`pytest -m modelos`): "classe de isolamento" e "grau de
   proteção" trazem chunk com a página esperada no top 4. Pronto: `python -m pytest tests -q` verde (os marcados `modelos` são pulados localmente).
8. [dirigido] Notebook `sprint4_pln_rag.ipynb` (sem saídas; lógica pura com tag `offline`): **0** título e tabela entregável→seção ·
   **1** Setup (raiz do repositório, chave lida do `.env` da raiz; sem clone, sem `%pip install`, como a seção 1 do notebook da Sprint 3) · **2** Extração e chunking (estatísticas, comparação `LEGADO` ×
   `NOVO`, 3 chunks exibidos com página e seção) · **3** Indexação (modelos, contagem, tempo) · **4** Estado operacional (construído
   dos alertas reais da plan 01.01 para um instante de alerta crítico e um de operação normal) · **5** Retriever com e sem estado
   (a mesma pergunta, top 4 de cada, mostrando página, seção e scores) · **6** Conclusão. Pronto: `nb_check` verde.
9. Rodar `python -m pytest tests -q`, `python tools/nb_check.py notebooks/sprint4_pln_rag.ipynb` e `code-auditoria-padrao`.

# 6. Critérios de aceite

- [ ] Todo chunk do preset `NOVO` tem `pagina`, `secao` e `secao_titulo`; nenhum atravessa o título da seção seguinte.
- [ ] Cabeçalho `www.weg.net …` ausente dos chunks; tabelas legíveis (`Coluna: valor`).
- [ ] `Retriever.buscar(..., estado=...)` altera a consulta e o ranking; `estado=None` reproduz a busca sem estado (teste).
- [ ] Todo termo de `termos_estado.json` ocorre no texto do PDF (teste).
- [ ] Presets `LEGADO` e `NOVO` disponíveis lado a lado para a plan 02.03.
- [ ] Notebook sem saídas passa em `nb_check` e contém as seções 0–6.
- [ ] **Fase B:** notebook executado localmente sem erro; seção 5 mostra o mesmo query com/sem estado, com página e seção por resultado;
      modelos carregados são os de `config.py`.
- [ ] Ambiente e worktree limpos; testes do escopo verdes; `code-auditoria-padrao` sem violação nova.

# 7. Como verificar (uso do revisor)

- **Nível:** `escopada`; sobe para `ampla` só se `config.py` ou `alertas.py` mudarem (diff provar).
- `git diff --stat` → só os arquivos de §3.1.
- **Fase A:** `python -m pytest tests -q` · `python tools/nb_check.py notebooks/sprint4_pln_rag.ipynb` · `code-auditoria-padrao`.
- Leitura de `src/pln/rag.py` → importação preguiçosa de `chromadb`/`sentence_transformers`; presets sem constantes soltas.
- **Fase B:** `python tools/nb_check.py notebooks/sprint4_pln_rag.ipynb --executado` · leitura das saídas das seções 2, 4 e 5.
- **Gate:** `nenhum`.

# 8. Destino da síntese

**Destino:** `specs/02.01-pipeline-rag.md` + `00-contexto.md`

Texto para transporte: formato do chunk e metadados; regras de chunking por seção; modelos de embedding e reranker (e por que
multilíngues); fluxo do retriever (consulta expandida → denso → rerank → boost de seção); definição de `EstadoOperacional` e do
mapeamento sensor → domínio; presets `LEGADO`/`NOVO`. Em `00-contexto.md`, atualizar a §3 (dependências) e a linha da §4.

---

# 9. Resumo da execução

<!-- Preenchido pelo EXECUTOR. Append-only: cada rodada acrescenta um bloco novo; nada é removido. -->

## Resumo da execu??o ? 2026-11-24

**Resultado:** Conclu?do com pend?ncias

**O que foi feito**
- `src/pln/config.py:32` ? adicionei constantes e presets `LEGADO`/`NOVO` para chunking, embeddings, rerankers e busca.
- `src/pln/estado.py:47` ? constru? snapshots determin?sticos de alertas ativos, com severidade e dom?nio da falha.
- `src/pln/rag.py:154` ? implementei extra??o por p?gina, tabelas rotuladas, chunking por se??o, ?ndice Chroma ef?mero e busca com expans?o/boost por estado.
- `data/termos_estado.json:2` ? registrei termos e se??es-alvo por grandeza operacional.
- `tests/test_estado.py:33` e `tests/test_rag.py:158` ? cobri estado, extra??o, pagina??o, se??es, limites, tabelas, termos e altera??o do ranking.
- `tests/test_rag_modelos.py:33` ? adicionei os casos condicionais aos modelos multil?ngues.
- `notebooks/sprint4_pln_rag.ipynb` ? reconstru? as se??es 0?6, sem outputs, com c?lulas offline para extra??o e estado.
- `requirements.txt:2` ? fixei `chromadb==1.5.9`, `PyMuPDF==2.1` e `sentence-transformers==6.3.0`.

**Arquivos alterados**
| Arquivo | Natureza | O que mudou |
|---|---|---|
| `requirements.txt` | alterado | Tr?s depend?ncias RAG com vers?es fixadas. |
| `src/pln/config.py` | alterado | Configura??o e presets do RAG. |
| `src/pln/estado.py` | criado | Estado operacional determin?stico derivado de alertas. |
| `data/termos_estado.json` | criado | Vocabul?rio de consulta e se??es-alvo por dom?nio. |
| `src/pln/rag.py` | criado | Extra??o PDF, tabelas, chunks rastre?veis, ?ndice e retriever. |
| `tests/test_estado.py` | criado | Testes offline de estado. |
| `tests/test_rag.py` | criado | Testes offline e contra o cat?logo real. |
| `tests/test_rag_modelos.py` | criado | Testes condicionais de recupera??o com modelos. |
| `notebooks/sprint4_pln_rag.ipynb` | alterado | Notebook reconstru?do, se??es 0?6, sem sa?das. |
| `specs/plan/plan-02.01-rag-com-pagina-secao-e-estado.md` | alterado | Status atualizado e resumo anexado. |

**Verifica??es executadas**
- `uv run --offline --with pytest==9.2.0 --with nbformat==5.11.1 --with requests==2.34.2 --with rouge-score==0.1.2 --with scikit-learn==1.9.1 --with pymupdf==2.1 --python 3.14 python -m pytest tests -q` (pytest sem cache, `--basetemp=.tmp-pytest-rag`) ? **78 passed, 2 skipped**, 1 aviso de marcador `modelos` n?o registrado.
- `python tools/nb_check.py notebooks/sprint4_pln_rag.ipynb` ? v?lido; c?lulas offline de extra??o e estado executadas.
- `MPLBACKEND=Agg python tools/nb_check.py notebooks/sprint3_pln_alertas.ipynb --executado` ? v?lido.
- `padrao-python/scripts/validate.py` nos seis arquivos Python tocados ? sem achados novos em `estado.py`, `rag.py` e testes; uma heur?stica de confian?a baixa aponta a URL OpenRouter preexistente em `config.py:164`.
- `ast.parse` nos seis arquivos Python tocados ? v?lido.
- `git diff --check` ? sem erros de whitespace.
- Extra??o real do cat?logo ? 52 p?ginas e 663 chunks NOVO; 663/663 com p?gina e se??o. As p?ginas f?sicas 1 e 52 n?o t?m rodap? numerado; as p?ginas internas mant?m a numera??o impressa.

**Estado inicial do worktree:**
```text
 M specs/00-contexto.md
 M specs/00-indice.md
 M specs/panorama/00-resumo.md
 M specs/plan/plan-02.01-rag-com-pagina-secao-e-estado.md
 M specs/specs/01.01-alertas-deterministicos.md
D  specs/plan/plan-01.03-chave-do-env-e-execucao-local.md
```

**Ambiente ap?s a verifica??o:** `.tmp-uv-cache-rag`, `.tmp-rag-pages` e `.tmp-pytest-rag` foram removidos. A fotografia de ambiente n?o conseguiu consultar processos (`query command failed`) e reportou 19 entradas novas no tempor?rio do sistema, sem atribui??o de autoria; elas n?o foram removidas. Docker indispon?vel. Nenhum commit foi criado.

**Crit?rios de aceite**
- [x] Chunks NOVO carregam p?gina e se??o, respeitam o limite e mant?m a se??o isolada ? teste do PDF real e teste sint?tico.
- [x] Cabe?alho removido e tabela serializada em pares coluna/valor ? teste de extra??o e inspe??o do PDF.
- [x] Estado ativo expande a busca e altera a ordena??o; `estado=None` n?o aplica expans?o/boost ? teste offline do retriever.
- [x] Todos os termos de estado ocorrem no texto/tabelas extra?dos do PDF ? teste com o cat?logo real.
- [x] Presets `LEGADO` e `NOVO` permanecem dispon?veis para compara??o ? `src/pln/config.py:71` e `src/pln/config.py:85`.
- [x] Notebook cont?m se??es 0?6, est? sem outputs e passa em `nb_check`.
- [ ] Fase B: execu??o local do notebook com modelos e verifica??o das p?ginas esperadas no top 4 ? os dois testes de modelos foram pulados porque os pesos n?o est?o no cache.
- [ ] Invent?rio completo do ambiente ? indispon?vel para processos e sem atribui??o segura das entradas no tempor?rio do sistema.

**Decis?es e suposi??es**
- Atribu? ?ndices f?sicos 1 e 52 apenas ? capa/contracapa sem n?mero impresso; aus?ncia de n?mero em p?gina interna continua sendo erro.
- Aceitei t?tulos num?ricos v?lidos que o sum?rio n?o lista, validando texto alfab?tico para evitar tratar linhas de dados como t?tulos; o cat?logo extra?do n?o exp?e todos os t?tulos do corpo no sum?rio.
- A execu??o com modelos ficou para a Fase B local, conforme o plano; n?o baixei pesos de modelo.

**Achados fora do escopo (n?o corrigidos)**
- `src/pln/config.py:164` ? o validador sinaliza heur?stica de URL em c?digo preexistente, com confian?a baixa; a linha n?o foi alterada por esta tarefa.
- `specs/00-contexto.md`, `specs/00-indice.md`, `specs/panorama/00-resumo.md`, `specs/specs/01.01-alertas-deterministicos.md` e a exclus?o staged de `specs/plan/plan-01.03-chave-do-env-e-execucao-local.md` j? estavam alterados no in?cio e foram preservados.

**Pend?ncias / riscos**
- Fase B depende da execu??o local do notebook com os modelos; os pesos n?o estavam dispon?veis neste ambiente.
- O pytest emitiu `PytestUnknownMarkWarning` para `modelos`, pois o reposit?rio n?o registra esse marcador; os dois casos foram pulados como previsto.
- A fotografia de ambiente n?o conseguiu inventariar processos, ent?o n?o ? poss?vel afirmar limpeza completa de itens fora do workspace.


## Resumo da execução — 2026-11-24

**Resultado:** Concluído com pendências

> Correção do bloco anterior: o pipeline substituiu acentos por `?`. O bloco anterior foi preservado por append-only; este resumo corrigido é a referência da execução.

**O que foi feito**
- `src/pln/config.py:32` — adicionei parâmetros e presets `LEGADO`/`NOVO` para chunking, modelos e busca.
- `src/pln/estado.py:47` — implementei snapshots determinísticos dos alertas ativos, com severidade e domínio da falha.
- `src/pln/rag.py:154` — implementei extração por página, tabelas rotuladas, chunks rastreáveis, índice Chroma efêmero e busca com estado.
- `data/termos_estado.json:2` — registrei termos de consulta e seções-alvo por grandeza.
- `tests/test_estado.py:33`, `tests/test_rag.py:158` e `tests/test_rag_modelos.py:33` — adicionei testes offline e condicionais aos modelos.
- `notebooks/sprint4_pln_rag.ipynb` — reconstruí as seções 0–6, sem outputs, com células offline de extração e estado.
- `requirements.txt:2` — fixei `chromadb==1.5.9`, `PyMuPDF==2.1` e `sentence-transformers==6.3.0`.

**Arquivos alterados**
| Arquivo | Natureza | O que mudou |
|---|---|---|
| `requirements.txt` | alterado | Dependências RAG com versões fixadas. |
| `src/pln/config.py` | alterado | Parâmetros e presets. |
| `src/pln/estado.py` | criado | Estado operacional determinístico. |
| `data/termos_estado.json` | criado | Vocabulário por domínio. |
| `src/pln/rag.py` | criado | Extração, chunking, índice e retriever. |
| `tests/test_estado.py` | criado | Testes de estado. |
| `tests/test_rag.py` | criado | Testes offline e contra o PDF real. |
| `tests/test_rag_modelos.py` | criado | Testes condicionais de modelos. |
| `notebooks/sprint4_pln_rag.ipynb` | alterado | Notebook 0–6 sem saídas. |
| `specs/plan/plan-02.01-rag-com-pagina-secao-e-estado.md` | alterado | Status e resumo anexado. |

**Verificações executadas**
- `python -m pytest tests -q` com dependências fixadas e diretório temporário local → **78 passed, 2 skipped**, 1 aviso de marcador `modelos` não registrado.
- `python tools/nb_check.py notebooks/sprint4_pln_rag.ipynb` → válido; células offline executadas.
- `MPLBACKEND=Agg python tools/nb_check.py notebooks/sprint3_pln_alertas.ipynb --executado` → válido.
- Validador `padrao-python` nos seis arquivos Python tocados → sem achados novos em estado, RAG e testes; uma heurística de baixa confiança aponta a URL OpenRouter preexistente em `config.py:164`.
- `ast.parse` nos seis arquivos Python e `git diff --check` → sem erros.
- Catálogo real → 52 páginas; os testes verificaram metadados de página/seção, a seção 4.1 na página 13 e a ocorrência dos termos configurados.

**Estado inicial do worktree:**
```text
 M specs/00-contexto.md
 M specs/00-indice.md
 M specs/panorama/00-resumo.md
 M specs/plan/plan-02.01-rag-com-pagina-secao-e-estado.md
 M specs/specs/01.01-alertas-deterministicos.md
D  specs/plan/plan-01.03-chave-do-env-e-execucao-local.md
```

**Ambiente após a verificação:** `.tmp-uv-cache-rag`, `.tmp-rag-pages` e `.tmp-pytest-rag` foram removidos. O diff do ambiente não conseguiu consultar processos e reportou 19 entradas novas no temporário do sistema, sem atribuição segura; não foram removidas. Docker indisponível. Nenhum commit foi criado.

**Critérios de aceite**
- [x] Chunks NOVO preservam página e seção, respeitam o limite e não cruzam seção — teste sintético e PDF real.
- [x] Cabeçalho removido e tabela serializada em pares coluna/valor — teste de extração.
- [x] Estado ativo expande a consulta e pode alterar a ordenação; `estado=None` desliga expansão/boost — teste offline.
- [x] Todos os termos configurados aparecem no texto/tabelas do PDF — teste com o catálogo real.
- [x] Presets `LEGADO`/`NOVO` disponíveis em `src/pln/config.py:71` e `src/pln/config.py:85`.
- [x] Notebook contém as seções 0–6, sem outputs, e passa em `nb_check`.
- [ ] Fase B: executar localmente com modelos e verificar páginas no top 4 — pesos ausentes no cache; dois casos foram pulados.
- [ ] Inventário integral do ambiente — processos indisponíveis e entradas temporárias sem autoria confirmada.

**Decisões e suposições**
- Nas páginas físicas 1 e 52, sem número impresso, usei o índice físico; páginas internas sem rodapé numerado continuam falhando.
- Se o sumário não listar uma seção numérica, o título é aceito após validação textual para não descartar seções presentes no corpo.
- A Fase B com modelos fica para a execução local prevista no plano.

**Achados fora do escopo (não corrigidos)**
- `src/pln/config.py:164` — URL OpenRouter preexistente sinalizada pela heurística de baixa confiança; linha não alterada.
- Alterações em `specs/00-contexto.md`, `specs/00-indice.md`, `specs/panorama/00-resumo.md`, `specs/specs/01.01-alertas-deterministicos.md` e a exclusão staged de `specs/plan/plan-01.03-chave-do-env-e-execucao-local.md` já existiam no início e foram preservadas.

**Pendências / riscos**
- A Fase B requer execução local do notebook com modelos; os dois testes marcados para modelos foram pulados porque os pesos não estavam no cache.
- O pytest emitiu `PytestUnknownMarkWarning` porque o repositório ainda não registra o marcador `modelos`.
- Sem inventário de processos, não é possível certificar limpeza completa fora do workspace.


## Resumo da execução (correção 1) — 2026-11-24

**Resultado:** Concluído com pendências

**O que foi feito**
- Achado 1 — `src/pln/rag.py:29-32,600-715`: seções validadas contra a hierarquia do sumário; linhas do sumário e fragmentos de notas não viram títulos nem chunks.
- Achado 2 — `src/pln/rag.py:347-507`: tabelas reconstruídas com palavras posicionadas e limites de células; rótulos e espaçamento preservados; tabelas ilegíveis descartadas.
- Achado 3 — `data/termos_estado.json`: alvos substituídos por títulos reais e seletivos; testes do PDF verificam ocorrência e cobertura.
- Achado 4 — `notebooks/sprint4_pln_rag.ipynb`: acentos restaurados, arquivo UTF-8, 12 células sem outputs.
- Achado 5 — `src/pln/config.py:37-42,81-96`: busca 20 no preset `NOVO`, busca 5 no `LEGADO`, com valores independentes.
- Achado 6 — `src/pln/rag.py` e `pytest.ini`: removida atribuição duplicada e registrado o marcador `modelos`.

**Arquivos alterados**
| Arquivo | Natureza | O que mudou |
|---|---|---|
| `src/pln/rag.py` | alterado | Validação de títulos, tabelas e metadados de seção. |
| `src/pln/config.py` | alterado | Valores de busca por preset. |
| `data/termos_estado.json` | alterado | Seções-alvo seletivas. |
| `tests/test_rag.py` | alterado | Testes com PDF real e presets. |
| `pytest.ini` | criado | Marcador `modelos`. |
| `notebooks/sprint4_pln_rag.ipynb` | alterado | Correção UTF-8 e acentuação. |
| `specs/plan/plan-02.01-rag-com-pagina-secao-e-estado.md` | alterado | Status e resumo desta correção. |

**Verificações executadas**
- `python -m pytest tests -q` → **82 passed, 2 skipped**; 1 aviso externo de `anyio`.
- `python tools/nb_check.py notebooks/sprint4_pln_rag.ipynb` → válido; células offline executadas.
- Sonda do PDF → 52 páginas, 699 chunks, zero títulos espúrios, zero linhas do sumário indexadas e zero rótulos `Coluna N`; todos os alvos presentes e abaixo de 25% de cobertura. `Dados Mecânicos`: 6,87%.
- Rótulos legíveis conferidos nas páginas 25 e 37. Validadores de Python, AST e `git diff --check` sem achados de escopo.
- Notebook e plan decodificam estritamente como UTF-8, sem BOM ou caractere de substituição. No notebook e neste bloco novo, não há letras acentuadas substituídas por `?`; a interrogação final da consulta do notebook é pontuação legítima.

**Estado inicial do worktree:** alterações em notebook, requirements, plan alvo, config, data, código e testes registradas no resumo anterior; as modificações preexistentes nos demais arquivos de specs e a exclusão staged foram preservadas.

**Ambiente após a verificação:** `.tmp-rag-correction` removido. Sem commit ou operação de branch/worktree/stash/reset/checkout. Fase B não executada: os pesos dos modelos não estavam no cache.

**Critérios de aceite**
- [x] Achado 1 — hierarquia e páginas de seção conferidas no PDF real.
- [x] Achado 2 — tabelas legíveis, sem rótulos genéricos.
- [x] Achado 3 — alvos reais, presentes e seletivos.
- [x] Achado 4 — notebook válido em UTF-8.
- [x] Achado 5 — busca NOVO 20 e LEGADO 5.
- [x] Achado 6 — duplicação removida e marcador registrado.

**Decisões e suposições**
- O sumário do catálogo é a fonte de autoridade para títulos de seção.
- Os testes com modelos ficam pendentes até que os pesos estejam disponíveis.
- O resumo histórico anterior contém acentos substituídos por `?`. Ele e o veredito foram preservados pela regra append-only; o bloco novo foi gravado em UTF-8 e conferido.

**Achados fora do escopo (não corrigidos)**
- `src/pln/config.py:167` — heurística de baixa confiança para URL OpenRouter preexistente; não alterada.

**Pendências / riscos**
- Dois testes de modelos permanecem pulados por falta dos pesos.
- O resumo histórico corrompido permanece intacto por append-only; notebook e bloco novo estão corretos.

## Resumo da execução (correção 2) — 2026-11-25

**Resultado:** Concluído com pendências

**O que foi feito**
- Achado 1a — `src/pln/rag.py:303`: `find_tables(use_layout=False)` deixa explícito o caminho sem análise de layout/ONNX, que variava conforme o ambiente. Para esta plan, o runtime de reprodução suportado foi declarado como Python 3.14.0.
- Achado 1b — `tests/test_rag.py`: páginas-fonte são obtidas do texto e das linhas de tabela do próprio PDF; asserções verificam que a faixa do chunk cobre a página real do rótulo.
- Achado 1c — `tests/test_rag_modelos.py`: os resultados precisam cobrir a p. 24, onde ambos os conceitos aparecem, sem exigir que o chunk comece na p. 25.

**Arquivos alterados**
| Arquivo | Natureza | O que mudou |
|---|---|---|
| `src/pln/rag.py` | alterado | Desativado o caminho de layout implícito na extração de tabelas. |
| `tests/test_rag.py` | alterado | Expectativas derivadas do PDF e verificadas contra `pagina` e `pagina_fim`. |
| `tests/test_rag_modelos.py` | alterado | Relevância verificada pela cobertura da p. 24. |
| `specs/plan/plan-02.01-rag-com-pagina-secao-e-estado.md` | alterado | Status e resumo da correção 2. |

**Verificações executadas**
- Python 3.14.0, dependências de `requirements.txt`: `python -m pytest -p no:cacheprovider --basetemp=.tmp-rag-r2-pytest tests -q` → **82 passed, 2 skipped** em 103,24 s. Dois testes com modelos foram pulados por falta dos pesos.
- `python tools/nb_check.py notebooks/sprint4_pln_rag.ipynb` → notebook válido.
- Sonda do PDF com PyMuPDF 2.1 e ONNX Runtime 1.32.0 → 52 páginas, 699 chunks, 44 seções, maior chunk com 898 caracteres e zero chunks sem metadados; rótulos reais em p. 24, 25 e 37.
- Contraprova na p. 24 com o mesmo PyMuPDF: `use_layout=True` retornou 0 tabelas; `use_layout=False` retornou 1 tabela com `Grau de proteção`. A documentação do PyMuPDF descreve o layout como habilitado por padrão e dependente do ONNX Runtime; a extração desta plan não depende mais desse caminho.
- Validador `padrao-python` em `src/pln/rag.py`, `tests/test_rag.py` e `tests/test_rag_modelos.py` → zero achados; `ast.parse` e `git diff --check` → sem erros.

**Estado inicial do worktree:**
```text
 M notebooks/sprint4_pln_rag.ipynb
 M requirements.txt
 M specs/00-backlog.md
 M specs/00-contexto.md
 M specs/00-indice.md
 M specs/panorama/00-resumo.md
D  specs/plan/plan-01.03-chave-do-env-e-execucao-local.md
 M specs/plan/plan-02.01-rag-com-pagina-secao-e-estado.md
 M specs/specs/01.01-alertas-deterministicos.md
 M src/pln/config.py
?? data/termos_estado.json
?? pytest.ini
?? src/pln/estado.py
?? src/pln/rag.py
?? tests/test_estado.py
?? tests/test_rag.py
?? tests/test_rag_modelos.py
```

**Ambiente após a verificação:** `.tmp-rag-r2-venv` e `.tmp-rag-r2-pytest` foram removidos. Não houve commit nem operação de branch, worktree, stash, reset ou checkout.

**Critérios de aceite**
- [x] Achado 1a — caminho sem layout explícito; reprodução declarada em Python 3.14.0.
- [x] Achado 1b — rótulos verificados na página real do PDF e dentro da faixa do chunk.
- [x] Achado 1c — teste de modelos verifica cobertura de página, não igualdade do início do chunk.

**Decisões e suposições**
- A chamada implícita a `find_tables()` usava o caminho de layout com ONNX por padrão; a sonda confirmou que a opção altera a detecção na página 24. A causa exata da diferença do wheel Python 3.11 não foi medida aqui. Como a rodada aceita uma versão suportada declarada, esta plan passa a declarar Python 3.14.0 como runtime de reprodução, e a suíte foi comprovada nessa versão.
- As páginas dos rótulos foram lidas do texto original e das tabelas extraídas do PDF; os testes também comprovam a página 24 para `Grau de proteção`, p. 25 para `Carcaça 200` e p. 37 para `Conjugado Nominal`.
- O veredito não reprova o achado 2; a melhoria de tabelas multinível fica encaminhada ao backlog/plan 02.03 e não foi alterada nesta correção.

**Achados fora do escopo (não corrigidos)**
- Achado 2 do veredito — cabeçalhos colados e rótulos repetidos em tabelas multinível; o revisor o destinou ao backlog, sem reprovação nesta rodada.

**Pendências / riscos**
- A execução Python 3.11 não foi repetida; esta plan declara Python 3.14.0 como ambiente suportado para reproduzir sua extração. Os testes da Fase B continuam pulados por falta dos pesos.

## Resumo da execução (correção 3) — 2026-11-25

**Resultado:** Concluído com pendências

**O que foi feito**
- Achado 1 — `src/pln/rag.py::_indexar_chunks`: as duas chamadas a `colecao.add` agora passam `ids=`, `documents=`, `embeddings=` e, no ramo com metadados, `metadatas=` por nome, conforme a API do ChromaDB.
- `tests/test_rag.py`: dois testes usam `chromadb.EphemeralClient()` real e embeddings/reranker determinísticos. O teste com metadados indexa e consulta três chunks e confere a associação entre id, documento e os quatro campos de metadados; o segundo exercita o ramo sem metadados. Cada teste usa nome de coleção exclusivo para não colidir com outras instâncias efêmeras da suíte.

**Arquivos alterados**
| Arquivo | Natureza | O que mudou |
|---|---|---|
| `src/pln/rag.py` | alterado | Argumentos nomeados nas duas chamadas a `Collection.add`. |
| `tests/test_rag.py` | alterado | Cobertura com ChromaDB real para os ramos com e sem metadados. |
| `specs/plan/plan-02.01-rag-com-pagina-secao-e-estado.md` | alterado | Status e resumo da correção 3. |

**Verificações executadas**
- Python 3.11.9, dependências de `requirements.txt` e cache Hugging Face isolado vazio: `python -m pytest -p no:cacheprovider --basetemp=.tmp-rag-r3-pytest tests -q` → **84 passed, 2 skipped** em 83,72 s. Os dois testes marcados `modelos` foram pulados por não haver pesos no cache isolado.
- Testes de integração com ChromaDB: `python -m pytest ... tests/test_rag.py -k chromadb_real -q` → **2 passed, 13 deselected**; ambos consultaram o cliente efêmero real.
- `padrao-python` em `src/pln/rag.py` e `tests/test_rag.py` → zero achados; `ast.parse` e `git diff --check` → sem erros.
- Notebook e plan decodificam estritamente como UTF-8; o notebook e este bloco não contêm padrão de letra acentuada substituída por `?`. O resumo histórico anterior foi preservado conforme append-only.

**Estado inicial do worktree:**
```text
 M notebooks/sprint4_pln_rag.ipynb
 M requirements.txt
 M specs/00-backlog.md
 M specs/00-contexto.md
 M specs/00-indice.md
 M specs/panorama/00-resumo.md
D  specs/plan/plan-01.03-chave-do-env-e-execucao-local.md
 M specs/plan/plan-02.01-rag-com-pagina-secao-e-estado.md
 M specs/specs/01.01-alertas-deterministicos.md
 M src/pln/config.py
?? data/termos_estado.json
?? pytest.ini
?? src/pln/estado.py
?? src/pln/rag.py
?? tests/test_estado.py
?? tests/test_rag.py
?? tests/test_rag_modelos.py
```

**Ambiente após a verificação:** `.tmp-rag-r3-python`, `.tmp-rag-r3-venv`, `.tmp-rag-r3-pytest` e `.tmp-rag-r3-uv-cache` foram removidos ao final da verificação. Nenhum commit ou operação de branch, worktree, stash, reset ou checkout foi feito.

**Critérios de aceite**
- [x] Os dois ramos de `_indexar_chunks` chamam `Collection.add` com argumentos nomeados.
- [x] ChromaDB real indexa e consulta três chunks com metadados e devolve cada documento emparelhado com os metadados do mesmo id.
- [x] ChromaDB real indexa e consulta três chunks sem metadados.

**Achados fora do escopo / pendências**
- Em uma execução completa usando o cache global de modelos, os dois casos de `test_modelos_multilingues_recuperam_faixa_que_contem_a_pagina_24` executaram e falharam por não trazerem a página 24 no top 4. O teste de integração com ChromaDB concluiu sem erro; não alterei a recuperação por modelos porque o veredito da rodada 3 limita esta correção à assinatura de `Collection.add`. A suíte com o cache isolado vazio passou com os dois testes de modelos pulados, conforme o comportamento opcional descrito na plan.
- A Fase B do notebook não foi executada nesta correção; o veredito direciona sua nova execução ao revisor sobre o código corrigido.

## Resumo da execução (correção 4) — 2026-11-25

**Resultado:** Concluído

**O que foi feito**
- Achado 1 — `tests/test_rag_modelos.py`: removida a exigência fixa da página 24. A relevância agora é derivada do catálogo extraído: normaliza o conceito sem acentos, localiza as páginas cujo texto ou linhas de tabela contém o conceito e exige ao menos um dos quatro resultados cujo texto contenha o conceito e cuja faixa de páginas cubra uma dessas páginas.
- A extração de páginas foi compartilhada entre o índice real e o oráculo do teste. O teste não pressupõe uma página nem exige que o resultado relevante esteja em primeiro lugar.

**Arquivos alterados**
| Arquivo | Natureza | O que mudou |
|---|---|---|
| `tests/test_rag_modelos.py` | alterado | Oráculo de relevância confirmado pelo texto do PDF, sem página fixa. |
| `specs/plan/plan-02.01-rag-com-pagina-secao-e-estado.md` | alterado | Status e resumo da correção 4. |

**Verificações executadas**
- Python 3.11.9, dependências fixadas de `requirements.txt`, pesos dos dois modelos em cache e modo offline: `python -m pytest -p no:cacheprovider --basetemp=.tmp-rag-r4-pytest tests/test_rag_modelos.py -q` → **2 passed** em 268,10 s.
- Suíte completa, mesmo ambiente com pesos em cache: `python -m pytest -p no:cacheprovider --basetemp=.tmp-rag-r4-pytest tests -q` → **86 passed, 0 skipped** em 343,52 s.
- `padrao-python` em `tests/test_rag_modelos.py` → zero achados; `ast.parse` → sem erro.
- Notebook e plan decodificam estritamente como UTF-8; notebook e este bloco não contêm padrão de acento substituído por `?`. O resumo histórico anterior permaneceu intacto por append-only.

**Estado inicial do worktree:**
```text
 M notebooks/sprint4_pln_rag.ipynb
 M requirements.txt
 M specs/00-backlog.md
 M specs/00-contexto.md
 M specs/00-indice.md
 M specs/panorama/00-resumo.md
D  specs/plan/plan-01.03-chave-do-env-e-execucao-local.md
 M specs/plan/plan-02.01-rag-com-pagina-secao-e-estado.md
 M specs/specs/01.01-alertas-deterministicos.md
 M src/pln/config.py
?? data/termos_estado.json
?? pytest.ini
?? src/pln/estado.py
?? src/pln/rag.py
?? tests/test_estado.py
?? tests/test_rag.py
?? tests/test_rag_modelos.py
```

**Ambiente após a verificação:** `.tmp-rag-r4-python`, `.tmp-rag-r4-venv`, `.tmp-rag-r4-pytest` e `.tmp-rag-r4-uv-cache` foram removidos; os pesos preexistentes no cache global foram preservados. Nenhum commit ou operação de branch, worktree, stash, reset ou checkout foi feito.

**Critérios de aceite**
- [x] As duas perguntas parametrizadas identificam o conceito no chunk e uma página-fonte do PDF que contém esse conceito, após normalização sem acentos.
- [x] Pelo menos um resultado relevante aparece entre os quatro primeiros para cada pergunta com modelos reais.
- [x] Suíte completa Python 3.11.9 com modelos presentes: 0 falhas e 0 skips.

**Achados fora do escopo**
- A observação não bloqueante sobre a influência do estado no ranking, destinada à plan 02.03, não foi alterada nesta correção.
- A Fase B do notebook não foi repetida: o veredito confirma sua execução sem erro e determina nova execução apenas se `src/` ou o notebook forem alterados.

---

# 10. Veredito

<!-- Preenchido pelo REVISOR. Append-only: um bloco por rodada, com o que foi verificado e como. -->

## Veredito — 2026-11-24 — 🔴 Reprovado

**Verificado.** `git status` e `git diff --stat` (só arquivos de §3.1 e os de specs já alterados antes da execução; nada fora do escopo). Fase A em venv limpo (Python 3.11, `pip install -r requirements.txt`; as três versões fixadas existem no PyPI): `python -m pytest tests -q` → 78 passed, 2 skipped, 1 aviso (marcador `modelos`); `nb_check` do notebook → válido. Sonda read-only sobre o catálogo real (`extrair_paginas()` + `chunk_novo()`): 52 páginas, 682 chunks, 0 ocorrências de `www.weg.net`, maior chunk 898 caracteres, `4.1` na p. 13. Importação preguiçosa de `chromadb` e `sentence_transformers` conferida em `src/pln/rag.py`. Fase B **não** foi rodada: o código muda, e ela só vale sobre o código corrigido.

Os testes passam porque só provam metadado **presente**, não **correto**. A sonda mostra que a recuperação com página e seção (F4) não está correta no catálogo real:

1. `src/pln/rag.py:468-479` (`_titulo_reconhecido`) e `rag.py:31` (`SECTION_PATTERN`) — 95 de 682 chunks (14 %) carregam seção espúria: linhas do sumário com pontilhado viram título (`1 — "Versões Disponíveis ........ 8"`, `22 — "Partes e Peças ......."`), itens de nota viram seção (`5 — "- Valores para esforços radiais"` com 28 chunks, `6 — "- Para aplicações…"`, `3 — "- Para motores verticais…"`) e fragmentos de frase viram seção (`90 — "não possuem olhal de"` com 24 chunks, `63 — "a 315S/M são fabricados…"`, `200`, `460`). Critério violado: §6 "todo chunk tem `secao` e `secao_titulo`" no sentido do objetivo (seção real do catálogo) e Instrução 1 (títulos por padrão numérico **da hierarquia do catálogo**). Resultado exigido: título só vale se o número pertence à hierarquia do sumário (número principal ≤ maior número do sumário, e subseções cujo pai existe) e o texto começa com maiúscula e não contém pontilhado; item de nota (`N - …`) nunca é título; nenhuma linha do sumário vira título nem chunk. Prova: teste com o PDF real em que nenhum `secao_titulo` contém `....`, começa com `-` ou minúscula, e todo `secao` principal ≤ 22; nenhum chunk de seção `1` fora da p. 8 em diante com título de nota.
2. `src/pln/rag.py:341-378` (serialização de tabelas) — 450 de 682 chunks contêm o marcador genérico `Coluna N` e as células saem sem espaço entre palavras (`PotênciaNominal: cvouHP; Coluna 2: kW`, `Materialdatampadefletora`, `Blindagem/FolgaDianteiro/Traseiro`, `Vedaçãodomancal`); a tabela de rendimento da p. 5 sai como lixo (`Coluna 2: 075 ,; Polos: 805% ,`) e cai na seção `0`. Critério violado: §6 "tabelas legíveis (`Coluna: valor`)" e Instrução 1 ("tabela não vira sopa de células"). Resultado exigido: células com espaçamento correto do texto original (extração por palavras/linhas, não concatenação de glifos); nome de coluna real do cabeçalho sempre que existir, `Coluna N` só quando não houver cabeçalho recuperável e nunca como padrão; tabela sem conteúdo legível é descartada, não indexada. Prova: teste com o PDF real em que as p. 25 e 37 contêm, em algum chunk, "Grau de proteção" e "Classe de isolamento" (ou os rótulos reais dessas linhas) com espaços, e a proporção de chunks com `Coluna N` fica abaixo de 10 %.
3. `data/termos_estado.json:13-17,28-33,44-48,59-63` — as seções-alvo não discriminam: `Influência do Inversor na Elevação de Temperatura do Motor`, `Eixo / Rolamentos` e `Operação com Inversor de Frequência` não casam com nenhum chunk (0), enquanto `Dados Elétricos` casa 417 de 682 chunks (61 %) e `Características Construtivas` 57. O boost de seção (Instrução 6d) fica sem efeito ou sem seletividade. Critério violado: §6 "`Retriever.buscar(..., estado=...)` altera a consulta e o ranking" no catálogo real e Instrução 5 ("conferindo cada termo por busca"; o critério de teste cobria só `termos_consulta`). Resultado exigido: depois de corrigir 1 e 2, reescrever `secoes_alvo` com títulos reais do catálogo; teste com o PDF real: todo item de `secoes_alvo` casa ≥ 1 chunk e nenhum casa mais de 25 % dos chunks.
4. `notebooks/sprint4_pln_rag.ipynb` (as 12 células) — todos os acentos foram gravados como `?` (`# Sprint 4 ? RAG com p?gina, se??o`, `reposit?rio`, `Chave OpenRouter dispon?vel`, f-strings de `mostrar_resultados`). Entregável visível ao professor. Critério violado: §6 notebook correto + `00-contexto` (entrega em português). Resultado exigido: o notebook regravado em UTF-8 com os acentos corretos. Prova: `grep` por letra, `?`, letra (`[A-Za-z]\?[A-Za-z]`) no arquivo sem ocorrência; `nb_check` verde.
5. `src/pln/config.py` (`K_BUSCA = 5`, `K_FINAL = 4`) — o denso recupera 5 candidatos e o reranker e o boost só reordenam 4 deles; recuperação mal posicionada no denso nunca é recuperada. Critério violado: Instrução 6 ("busca densa top `K_BUSCA`, depois rerank" pressupõe pool maior que o final). Resultado exigido: `K_BUSCA` do preset `NOVO` ≥ 20 (constante própria); `LEGADO` mantém os valores do notebook antigo (ler com `git show HEAD:notebooks/sprint4_pln_rag.ipynb`); teste confirma os dois presets com valores distintos.
6. Menores, mesma rodada: `src/pln/rag.py:422-423` — linha `pagina_impressa = pagina_fisica` duplicada (remover uma); o marcador `modelos` não está registrado (aviso do pytest) — registrar em `pytest.ini` na raiz (acrescentado ao escopo "Dentro" desta correção).

**Resumo do executor × diff.** O bloco 1 do resumo está com acentos trocados por `?` (falha do pipeline); o bloco 2 o corrige e foi aceito como referência. O resumo diz "663/663 com página e seção" e marca os critérios 1, 2 e 4 como atendidos: a contagem é verdadeira, mas o resultado exigido (seção e tabela corretas) não é. Critérios 3, 5 e 7 de §6 (presets, `estado=None`, notebook sem saídas) conferem. Ambiente: sem `.tmp-*` residual no worktree; a venv de verificação fica fora do repositório.

**Fora do escopo desta correção:** nenhum item novo para o backlog. A heurística de URL em `config.py:164` é preexistente e de baixa confiança.

Escopo da correção: exclusivamente os achados 1 a 6. Verificação da correção: `python -m pytest tests -q` (inclui os novos testes com o PDF real), `python tools/nb_check.py notebooks/sprint4_pln_rag.ipynb`, e a sonda do achado 1–3 repetida e colada no resumo (contagens de seção espúria, de `Coluna N` e de seções-alvo).

## Veredito — 2026-11-24 — 🔴 Reprovado (rodada 2, sobre a correção 1)

**Verificado.** `git status`/`git diff --stat`: só os arquivos de §3.1 mais `pytest.ini` (autorizado no veredito anterior); nada fora do escopo. Fase A na venv limpa de verificação (Python 3.11.9, `pip install -r requirements.txt`, `PyMuPDF` 2.1, `chromadb` 1.5.9): `python -m pytest tests -q` → **1 failed, 81 passed, 2 skipped**; `nb_check` → válido; notebook sem letra acentuada trocada por `?` (0 ocorrências). Sonda read-only no catálogo real: 52 páginas, 681 chunks, maior chunk 898, 0 linhas de sumário indexadas, 0 `Coluna N`, 44 seções todas com título real da hierarquia (`4.1 Sistema de Ventilação` na p. 13, `4.3 Níveis de Vibração`, `11 Proteção Térmica do Motor`, `12.2 Influência do Inversor na Elevação de Temperatura do Motor`), todos os `secoes_alvo` casam ≥ 1 chunk e nenhum passa de 25 %; `K_BUSCA_NOVO = 20` e `K_BUSCA_LEGADO = 5`; `pytest.ini` registra `modelos`. Os achados 1, 3, 4, 5 e 6 do veredito anterior estão atendidos, e o 2 parcialmente (ver abaixo).

1. `tests/test_rag.py:275` (`test_pdf_real_serializa_tabelas_legiveis_sem_colunas_genericas`) — **vermelho no ambiente de referência.** O resumo da correção declara "82 passed", mas na venv limpa criada como manda o `00-contexto` §5 (Python 3.11, `pip install -r requirements.txt`) o teste falha: nenhum chunk com `pagina == 25` contém "Grau de proteção" e "Carcaça 200". Na minha extração, a linha "Grau de proteção … IPW55" cai num chunk que **começa na p. 24** (seção 14, "Características Construtivas"); os chunks de `pagina == 25` são só mais tabela de rolamentos e material. O resultado é determinístico (mesmo valor com três `PYTHONHASHSEED`), então a extração difere entre o ambiente do executor (Python 3.14 via `uv`) e o de referência. O `PyMuPDF` 2.1 instala `pymupdf-layout`, `pymupdf4llm` e `onnxruntime` como dependências, e é o suspeito natural da divergência; não confirmei a causa e não a prescrevo. Critério violado: §6 "tabelas legíveis" e Instrução 7 (`python -m pytest tests -q` verde). Resultado exigido: (a) descobrir de onde vem a diferença entre os dois ambientes e deixar a extração do catálogo **reprodutível** no ambiente declarado do repositório (a mesma contagem de páginas, seções e chunks nas duas versões de Python que `requirements.txt` suporta, ou a plan declara a versão suportada e o resumo prova a execução nela); (b) a expectativa da página no teste vir do catálogo real e não de suposição: a asserção correta é que o chunk que contém o rótulo cubra a página onde ele **realmente** está (`pagina <= p <= pagina_fim`), com `p` conferida no PDF; (c) o mesmo para `tests/test_rag_modelos.py:39`, que assume a p. 25 para "classe de isolamento" e "grau de proteção": o catálogo traz "Classe de Isolamento" em várias páginas (12, 24, 32, 33…) e a linha de grau de proteção na p. 24, então a asserção atual reprovaria a Fase B por um motivo errado. Prova: `python -m pytest tests -q` verde na venv Python 3.11 com `pip install -r requirements.txt`, e o resumo cita a versão de Python e a de `PyMuPDF` usadas.
2. `src/pln/rag.py` (serialização de tabelas), parcial — o rótulo genérico sumiu (0 `Coluna N`), mas cabeçalhos de tabelas de vários níveis continuam colados e repetidos: `PotênciaNominal kW: 0,75` (p. 5, centenas de linhas) e, na seção 5.2.1, `Carga radial máxima - 60 Hz - 25 .000 horas - Fr em (kN) 2 polos: 0,3` repetido em cada par de colunas; 77 dos 681 chunks são dessa seção e quase todo o texto deles é rótulo repetido. Não reprovo por isso: o critério de §6 ("`Coluna: valor`" legível, sem sopa de células) ficou atendido nas tabelas do escopo dos testes (p. 24/25 e 37), e a qualidade do recuperador será medida na plan 02.03. **Vai para o `00-backlog`** (cabeçalho colado e rótulo repetido em tabelas multinível), com dono na plan 02.03 se a avaliação apontar falha de recuperação nelas.

**Resumo do executor × diff.** O bloco "correção 1" confere com o diff nos achados 1, 3, 4, 5 e 6 (sonda reproduzida: zero títulos espúrios, zero `Coluna N`, alvos seletivos, K 20/5, notebook em UTF-8). Diverge em um ponto: "82 passed, 2 skipped" não reproduz no ambiente de referência (1 failed). A divergência de ambiente é o achado 1. Ambiente: sem `.tmp-*` residual; sem processo ou arquivo criado fora do workspace por esta revisão (venv e `scratchpad` ficam fora do repositório).

Escopo da correção: exclusivamente o achado 1 (itens a, b e c). Verificação: `python -m pytest tests -q` na venv limpa Python 3.11 e `python tools/nb_check.py notebooks/sprint4_pln_rag.ipynb`.

## Veredito — 2026-11-25 — 🔴 Reprovado (rodada 3, sobre a correção 2)

**Verificado.** Fase A na venv limpa (Python 3.11.9, `PyMuPDF` 2.1, `onnxruntime` 1.32.0, `chromadb` 1.5.9, `sentence-transformers` 6.3.0): `python -m pytest tests -q` → **82 passed, 2 skipped** (o vermelho da rodada 2 sumiu; `find_tables(use_layout=False)` tornou a extração igual em Python 3.11 e 3.14: 52 páginas, 699 chunks, 44 seções, maior chunk 898, mesmo resultado do executor); `nb_check` → válido; achado 1 (a, b, c) atendido. Fase B (`jupyter nbconvert --to notebook --execute notebooks/sprint4_pln_rag.ipynb`, sem `--allow-errors`, saída fora do repositório) → **falhou** na seção de indexação (`criar_retriever`).

**Achado novo (bloqueante).**

1. `src/pln/rag.py:1015-1022` (`_indexar_chunks`) — as chamadas a `colecao.add` passam `ids`, `textos` e `vetores` por posição. Na API real do ChromaDB 1.5.9 a ordem posicional é `ids, embeddings, metadatas, documents, ...`; a segunda posição é `embeddings`, não `documents`. Resultado: `TypeError: Collection.add() got multiple values for argument 'metadatas'`. O ramo de `rag.py:1015` (sem metadados) tem o mesmo erro de ordem. Os testes passam porque usam um cliente vetorial falso que aceita a assinatura inventada; nenhum teste da Fase A exercita o `chromadb` real. Correção: passar `ids=`, `documents=`, `embeddings=` e `metadatas=` por nome nos dois ramos; adicionar um teste offline com `chromadb.EphemeralClient()` real e um modelo de embedding falso determinístico (vetores de dimensão fixa) que indexe e consulte pelo menos 3 chunks e confira que o `documents` e o `metadatas` devolvidos pertencem ao mesmo chunk.

**Fora do escopo.** Nada novo para o backlog.

Escopo da correção: exclusivamente o achado 1 desta rodada. Verificação: `python -m pytest tests -q` na venv limpa Python 3.11, mais o teste novo com `chromadb` real. A Fase B será rodada de novo pelo revisor sobre o código corrigido; as seções 2, 4 e 5 ainda não foram lidas.

## Veredito — 2026-11-25 — 🔴 Reprovado (rodada 4, sobre a correção 3)

**Verificado.** Achado da rodada 3 atendido: `_indexar_chunks` (`rag.py:1008-1028`) passa `ids=`, `documents=`, `embeddings=` e `metadatas=` por nome nos dois ramos, e os dois testes novos usam `chromadb.EphemeralClient()` real e conferem a associação id/documento/metadados. Fase A (venv Python 3.11.9): 84 passed, sem falha offline. Fase B: `jupyter nbconvert --execute` do notebook, sem `--allow-errors`, **terminou sem erro** (52 páginas, 699 chunks NOVO / 77 LEGADO, 699 com página e seção, 699 passagens indexadas em 179 s com `intfloat/multilingual-e5-base` e `cross-encoder/mmarco-mMiniLMv2-L12-H384-v1`, os modelos de `config.py`; estado crítico com alerta A-0001 e estado normal construídos de 4.477 episódios; seção 5 imprime página, seção e scores por resultado, com e sem estado). Com os pesos agora em cache, os dois testes marcados `modelos` deixaram de ser pulados.

**Achado (bloqueante).**

1. `tests/test_rag_modelos.py:36-48` — com os modelos reais, os dois testes **falham** (`2 failed, 84 passed` na suíte completa; reproduzido isolando o arquivo). O oráculo exige que algum dos 4 primeiros resultados cubra a **p. 24**, uma página escolhida pelo executor, não a resposta correta. A sonda no índice real mostra que a recuperação é razoável e devolve outras páginas válidas: "grau de proteção" → p. 27 (tabela "Grau de Proteção"), p. 18 (seção 7, texto do grau de proteção) e p. 26; "classe de isolamento" → p. 21 (seção 12.1, "isolação térmica da classe F") e p. 32 ("Classe de Isolamento"). O teste reprova recuperação correta. Correção: derivar a relevância do próprio PDF, sem página fixa, e. g. o resultado é relevante se o conceito (normalizado, sem acento) aparece no texto do chunk **e** o chunk cobre uma página cujo texto extraído do PDF contém o conceito; exigir pelo menos um resultado relevante nos 4 primeiros (e, se desejar, que o primeiro seja relevante). Os testes com modelos devem ficar **verdes** na venv com os pesos em cache, e o resumo deve citar o resultado de `python -m pytest tests -q` com os pesos presentes (sem skip).

**Observação (não bloqueia).** Seção 5 do notebook: com estado crítico os mesmos 4 chunks voltam na mesma ordem e só os scores mudam; a seção 10.1 "Resistências de Aquecimento" (aquecedor anticondensação) entra no top 4 para "aquecimento do motor". Registrado no `00-backlog` (item 3); a plan 02.03 mede e pode recalibrar `PESO_ESTADO`.

Escopo da correção: exclusivamente o achado 1. Verificação: `python -m pytest tests -q` com os pesos em cache (venv Python 3.11), esperando 0 skipped e 0 failed. Depois disso, a Fase B (notebook executado) já está comprovada e só será repetida se `src/` ou o notebook mudarem.

## Veredito — 2026-11-25 — 🟢 Aprovado

**Verificado.** Achado da rodada 4 atendido: `tests/test_rag_modelos.py` agora deriva a relevância do próprio PDF (o conceito, normalizado, aparece no texto do chunk **e** o chunk cobre uma página cujo texto extraído contém o conceito), sem página fixa. Fase A na venv limpa (Python 3.11.9, `PyMuPDF` 2.1, `chromadb` 1.5.9, `sentence-transformers` 6.3.0) com os pesos dos modelos em cache: `python -m pytest tests -q` → **86 passed, 0 skipped, 0 failed**, inclusive os testes `modelos` e os dois testes com `chromadb` real; `nb_check` → válido; `src/` e notebook inalterados desde a Fase B da rodada 4. Fase B (rodada 4, `nbconvert --execute` sem `--allow-errors`): notebook sem erro; 52 páginas, 699 chunks `NOVO` todos com página e seção, 77 `LEGADO`, 699 passagens indexadas com os modelos de `config.py`; estado crítico (A-0001) e normal construídos dos 4.477 episódios; seção 5 mostra o mesmo query com e sem estado, com página, seção e scores por resultado. Extração reproduzida igual em Python 3.11 e 3.14 (`find_tables(use_layout=False)`).

**Resumo do executor × diff.** Confere: a correção 4 alterou só `tests/test_rag_modelos.py` e a plan.

**Para a síntese (02.01-pipeline-rag).** Transportar: presets `LEGADO`/`NOVO`, extração por página sem cabeçalho e com tabelas `Coluna: valor`, hierarquia de seções do sumário, índice ChromaDB efêmero cosseno, query expansion por estado, boost de seção `PESO_ESTADO`, K 20/5, ambiente reproduzível (`use_layout=False`), receita da Fase B. Não transportar: rodadas e achados da revisão. Backlog #2 e #3 seguem abertos (alimentam a 02.03).

**Antes de commitar.** O notebook `sprint4_pln_rag.ipynb` está **sem saídas** no worktree; a versão executada é entrega da plan 02.05 (execução local final). Não há achado pendente.
