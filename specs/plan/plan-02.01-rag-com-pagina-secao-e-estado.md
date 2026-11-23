---
tipo: "plan"
familia: "02"
item: "R02.1"
titulo: "Construir RAG com página, seção e estado operacional na busca"
dominio: "Sprint 4 — RAG e assistente"
status: "🔴 A executar"
prioridade: "Alta"
tags: ["plan", "sprint-4", "rag", "F3", "F4"]
relacionados: ["[[00-contexto]]", "[[plan-01.02-classificacao-e-relatorio-rastreavel]]"]
depende_de: "plan-01.02-classificacao-e-relatorio-rastreavel"
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
   **1** Setup (clone, `pip install -r requirements.txt`, Secrets) · **2** Extração e chunking (estatísticas, comparação `LEGADO` ×
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
- [ ] **Fase B:** notebook executado no Colab sem erro; seção 5 mostra o mesmo query com/sem estado, com página e seção por resultado;
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

---

# 10. Veredito

<!-- Preenchido pelo REVISOR. Append-only: um bloco por rodada, com o que foi verificado e como. -->
