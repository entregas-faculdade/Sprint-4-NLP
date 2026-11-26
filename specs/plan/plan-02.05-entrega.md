---
tipo: "plan"
familia: "02"
item: "R02.5"
titulo: "Preparar a entrega: documento final, README, roteiro do vídeo e notebooks executados"
dominio: "Sprint 4 — RAG e assistente"
status: "🟢 Aprovada"
prioridade: "Alta"
tags: ["plan", "entrega"]
relacionados: ["[[00-contexto]]", "[[02.04-cenarios-e-limites]]"]
depende_de: ""
destino_sintese: "—"
---

# 1. Objetivo

O repositório público está **pronto para ser entregue**: os dois notebooks executados e limpos, o **documento final unificado** com
números extraídos das saídas (não digitados), um README que leva o avaliador do zero à execução local, e o **roteiro do vídeo** de 3 a 5 minutos,
com a matriz que mostra onde cada crítica F1–F7 foi tratada.

# 2. Contexto

- Formato exigido (`enunciado-4.txt`): pasta/repositório privado ou público com `sprint3_pln_alertas.ipynb`, `sprint4_pln_rag.ipynb`,
  conjuntos de teste com referências, **documento final unificado** (templates de narrativa, critérios de classificação, arquitetura do RAG,
  métricas obtidas, limites) e **vídeo** de 3 a 5 min, "não listado" no YouTube, com link no GitHub.
- Este plan não escreve regra nova: **consolida**. Fontes: specs sintetizadas `specs/01.*`, `specs/02.*`, saídas em `data/saida/`,
  notebooks executados.
- O vídeo é gravado pelo **usuário**; aqui só o roteiro e o espaço do link.

# 3. Escopo

## 3.1 Dentro
- `docs/relatorio-final.md` — documento final unificado
- `tools/gerar_relatorio_final.py` — preenche os números do documento a partir de `data/saida/*.json`
- `README.md` — novo
- `docs/roteiro-video.md` — novo
- `docs/matriz-criticas.md` — novo: F1–F7 → plan → seção do notebook → evidência
- `notebooks/sprint3_pln_alertas.ipynb` · `notebooks/sprint4_pln_rag.ipynb` — **só** `nb_check` e, se faltar, re-execução trazida pelo usuário (sem editar o conteúdo à mão)
- `.gitignore` — se necessário (saídas pesadas, cache)

## 3.2 Fora
- Qualquer mudança em `src/pln/`, nos dados ou na lógica dos notebooks — se a leitura final achar defeito, vira backlog ou plan nova, **não** edição aqui
- `specs/` (a síntese das plans é do revisor)
- O arquivo do vídeo (não entra no repositório)

# 4. Referências obrigatórias

| Tipo | Referência | Por quê |
|---|---|---|
| Spec fixa | `specs/01.01-*.md` · `specs/01.02-*.md` · `specs/02.01-*.md` … `specs/02.04-*.md` | verdade de cada parte, para o documento |
| Contexto | `00-contexto.md` · `00-knowledge.md` | regras (§2, §7) |
| Requisito | `enunciado-4.txt` · `docs/feedback-professor.md` | formato da entrega e rubrica de avaliação |
| **Skill** | `padrao-escrita` · `code-entrega` (fluxo de pré-entrega: assinatura, licença, documentação) · `code-limpeza-projeto` | pré-entrega |
| Dados | `data/saida/*.json` · notebooks executados | origem dos números |

# 5. Instruções de execução

1. [dirigido] **Higiene de pré-entrega** (skill `code-limpeza-projeto`, com Grep antes de apagar): sem arquivo órfão, sem `.ipynb_checkpoints`,
   sem cache pesado fora de `data/saida/`, `.env` ausente do Git; `grep` por chaves (`sk-or-`, `OPENROUTER_API_KEY=`) em todo o repositório e
   nas saídas dos notebooks → nada. Conferir que `data/dados_avaliacao.json` não existe mais.
2. [dirigido] **Documento final** `docs/relatorio-final.md`, com seções: 1 Visão geral e arquitetura (diagrama em texto: dados → alertas
   → estado → retriever → assistente → avaliação) · 2 **Templates de narrativa** (os três, com exemplo real de cada) e verificador ·
   3 **Critérios de classificação** (as 5 categorias, composição do conjunto, protocolo) · 4 Relatório operacional e rastreabilidade ·
   5 **Arquitetura do RAG** (chunking por seção, modelos, retriever com estado, presets `LEGADO`/`NOVO`) · 6 Assistente (prompt, citação,
   confiança, abstenção, memória) · 7 **Métricas obtidas** (F1 por categoria; ROUGE e checklist; hit@k, precision@k, MRR, context precision;
   faithfulness e relevancy; calibração do juiz; comparação `LEGADO`×`NOVO` e com/sem estado) · 8 **Cenários** (resumo dos três) ·
   9 **Limites e mitigações** (de `limites.json`) · 10 **Como as críticas foram tratadas** (a matriz). Todo número vem de
   `tools/gerar_relatorio_final.py` (marcadores `{{metrica.caminho}}` substituídos a partir de `data/saida/*.json`); número sem fonte não entra.
3. [dirigido] `docs/matriz-criticas.md`: uma linha por F1–F7 (texto do professor, plan, seção do notebook, arquivo de evidência,
   resultado em uma frase) — só afirmar o que as saídas executadas mostram. Se um critério ficou parcial, **dizer**.
4. [dirigido] `README.md`: o que é o projeto; estrutura de pastas; como rodar localmente (venv, `pip install -r requirements.txt`, `.env` com `OPEN-ROUTER-API-KEY`, `nbconvert --execute` dos dois notebooks do
   repositório; sem Colab); como rodar os testes localmente; link do vídeo
   (`<!-- VIDEO_URL -->` até o usuário colar); licença e aviso de que o PDF é material da WEG.
5. [dirigido] `docs/roteiro-video.md`: 3 a 5 minutos, por cenas com tempo: abertura e arquitetura (30 s), alerta fiel e verificador
   (40 s), **cenário elétrico** (50 s), **cenário mecânico** (50 s), **cenário preventivo** (50 s), avaliação e limites (40 s), fechamento (20 s);
   o que mostrar na tela (célula, saída) e o que dizer; lembrar de **não exibir a chave** e de postar "não listado".
6. [dirigido] **Conferência final** dos notebooks entregues: `python tools/nb_check.py … --executado` nos dois; as seções exigidas no
   enunciado existem (resumos de alertas, classificação com F1, relatório com ROUGE, RAG completo, avaliação, 3 cenários, limites); abrir
   cada notebook e conferir que **as saídas batem com `data/saida/`**.
7. Rodar `python -m pytest tests -q` e `python tools/gerar_relatorio_final.py --check` (falha se o documento tiver marcador sem valor ou número divergente das saídas).

# 6. Critérios de aceite

- [ ] Os dois notebooks passam em `nb_check --executado`, sem erro e sem chave, e a execução é a **última versão do código** (`src/` não mudou depois).
- [ ] `docs/relatorio-final.md` contém as 5 seções exigidas pelo enunciado (templates, critérios de classificação, arquitetura do RAG, métricas, limites).
- [ ] Todos os números do documento vêm de `data/saida/` (`gerar_relatorio_final.py --check` verde).
- [ ] `docs/matriz-criticas.md` cobre F1–F7 com evidência; nada afirmado sem saída executada; parciais assumidos.
- [ ] `README.md` leva à execução local e explica o `.env`; `docs/roteiro-video.md` soma 3–5 min com os 3 cenários.
- [ ] Nenhuma chave no repositório ou nas saídas; `.env` fora do Git; `dados_avaliacao.json` ausente.
- [ ] Ambiente e worktree limpos; `pytest` verde.

# 7. Como verificar (uso do revisor)

- **Nível:** `ampla` — motivo: fecha a entrega, lê os dois notebooks e a suíte inteira; **não** é verificação completa.
- `git diff --stat` → só os arquivos de §3.1.
- `python -m pytest tests -q` · `python tools/nb_check.py notebooks/sprint3_pln_alertas.ipynb --executado` ·
  `python tools/nb_check.py notebooks/sprint4_pln_rag.ipynb --executado` · `python tools/gerar_relatorio_final.py --check`.
- `grep -rn "sk-or-\|OPENROUTER_API_KEY *=" . --include=* ` → nada com valor.
- Leitura de `docs/relatorio-final.md` §7 e de `matriz-criticas.md` → 3 números conferidos contra `data/saida/*.json`.
- Conferir a lista do enunciado ("Formato da Entrega") item a item.
- **Gate:** `nenhum`.

# 8. Destino da síntese

**Destino:** `—`. A plan consolida e entrega material; não altera nenhuma verdade documentada nas specs fixas. Ao aprovar, o revisor
verifica se o `00-contexto.md` ainda descreve o repositório entregue (estado final do §8) e remove a plan.

---

# 9. Resumo da execução

<!-- Preenchido pelo EXECUTOR. Append-only: cada rodada acrescenta um bloco novo; nada é removido. -->

## Resumo da execução — 2026-11-25

**Resultado:** Concluído com pendências

**O que foi feito**
- Higiene de pré-entrega (passo 1): sem `.ipynb_checkpoints`, sem `data/dados_avaliacao.json`, `.env` ignorado (`.gitignore:2`); `grep` por `sk-or-` e `OPEN-ROUTER-API-KEY=<valor>` em todo o repositório (exceto o `.env` local, ignorado) → nada; nada foi apagado, pois não havia órfão.
- `tools/gerar_relatorio_final.py` criado: marcadores `<!--{caminho|formato}-->valor<!--/-->` preenchidos de `data/saida/*.json` e das saídas executadas do notebook da Sprint 3 (`nb3.*`); `--check` falha com marcador sem valor, valor divergente ou documento sem marcador; `--documento` aceita outro arquivo.
- `docs/relatorio-final.md` criado com as 10 seções da plan; 156 marcadores, todos preenchidos pelo gerador (nenhum número de resultado digitado).
- `docs/matriz-criticas.md` criado: uma linha por F1–F7; F3 declarada **parcial** (o estado não melhora a recuperação); 28 marcadores, conferidos com o mesmo gerador.
- `README.md` criado (projeto, estrutura, venv, `.env`, `nbconvert --execute --inplace` dos dois notebooks, testes, `<!-- VIDEO_URL -->`, licença e aviso do PDF da WEG).
- `docs/roteiro-video.md` criado: sete cenas somando 280 s (4 min 40 s), com os três cenários.
- Conferência final (passo 6): `nb_check --executado` e leitura das saídas do notebook da Sprint 3 (seções 5–14 batem com `data/saida/`); o da Sprint 4 **não** está executado (ver Pendências).

**Arquivos alterados**
| Arquivo | Natureza | O que mudou |
|---|---|---|
| `tools/gerar_relatorio_final.py` | criado | gerador e `--check` dos números do documento |
| `docs/relatorio-final.md` | criado | documento final unificado, números por marcador |
| `docs/matriz-criticas.md` | criado | matriz F1–F7 com evidência e situação |
| `README.md` | criado | do zero à execução local, `.env`, testes, vídeo, licença e aviso WEG |
| `docs/roteiro-video.md` | criado | roteiro de 4 min 40 s por cenas |
| `specs/plan/plan-02.05-entrega.md` | alterado | `status` e este resumo |

**Verificações executadas**
- `python tools/gerar_relatorio_final.py --check` → 156 marcadores conferidos; 0 erro(s). Com `--documento docs/matriz-criticas.md` → 28 marcadores; 0 erro(s).
- `python tools/nb_check.py notebooks/sprint3_pln_alertas.ipynb --executado` → "Notebook válido".
- `python tools/nb_check.py notebooks/sprint4_pln_rag.ipynb --executado` → **Falha: a célula 2 não tem execution_count** (0 de 23 células de código executadas, 0 saídas).
- `python -m pytest tests -q` → 173 passed, 12 errors. Os 12 são `TypeError: find_tables() got an unexpected keyword argument 'use_layout'`: o Python do ambiente (3.14.0) tem `pymupdf` 1.28.0, e `requirements.txt` fixa `PyMuPDF==2.1`. A spec `02.03` §4 já registra que, com `PyMuPDF` diferente do pin, parte dos testes de extração falha. Não reinstalei dependência no ambiente.
- `grep` de chaves (padrões `sk-or-[…]{8,}` e `OPEN-ROUTER-API-KEY *= *<valor>`) em todo o repositório, exceto `.env` → nenhuma ocorrência.
- Limiares de `tools/gerar_relatorio_final.py` (função ≤ 40 linhas, ≤ 4 parâmetros), conferidos por AST → nenhuma violação. `ruff` não está instalado; a checagem estática do hook não rodou.
- Conferência numérica manual: F1 macro zero-shot 0,800 e linha de base 0,070 (`classificacao.json`), ROUGE-1 do relatório diário 0,449 (`relatorio_diario.json`), faithfulness média 0,98 (`avaliacao_respostas.json`) — batem com o documento.

**Estado inicial do worktree:** `git status --short` vazio (limpo), na `main`, conforme a declaração de `00-contexto` §5.

**Ambiente após a verificação:** nada criado (só `python` e `pytest` em processo curto; nenhum servidor, contêiner ou navegador). `snapshot` da `code-limpeza-ambiente` não rodado: indisponível, pois nada de longa duração foi iniciado.

**Critérios de aceite**
- [ ] Os dois notebooks passam em `nb_check --executado` — motivo: o `sprint4_pln_rag.ipynb` entregue no repositório **não tem saídas** (as saídas de `data/saida/` foram regeneradas em 2026-11-25 17:08–17:10, depois do arquivo do notebook, 15:55, mas o notebook executado não foi salvo). A plan proíbe editar o notebook à mão: a re-execução (`README.md`) é do usuário. O da Sprint 3 passa e o `src/` que ele usa não mudou depois do commit dele (`3717513`).
- [x] `docs/relatorio-final.md` contém as 5 seções exigidas (templates §2, critérios §3, arquitetura do RAG §5, métricas §7, limites §9) — evidência: títulos das seções.
- [x] Todos os números do documento vêm de `data/saida/` — evidência: `--check` verde (156 marcadores); número de resultado fora de marcador: nenhum que eu tenha escrito.
- [x] `docs/matriz-criticas.md` cobre F1–F7, parciais assumidos (F3) — evidência: tabela.
- [x] `README.md` leva à execução local e explica o `.env`; `docs/roteiro-video.md` soma 280 s, com os 3 cenários — evidência: tabela de cenas.
- [x] Nenhuma chave no repositório ou nas saídas; `.env` fora do Git; `dados_avaliacao.json` ausente — evidência: `grep` e `git check-ignore`.
- [ ] Ambiente e worktree limpos; `pytest` verde — motivo: worktree contém só os 5 arquivos novos do escopo; `pytest` tem 12 erros de ambiente (acima).

**Decisões e suposições**
- Os marcadores ficam no próprio `relatorio-final.md` (comentários HTML invisíveis) em vez de um arquivo de modelo separado: um arquivo só, regerável e conferível; o `--check` compara o valor gravado com o da saída.
- As métricas de alertas-teste (ROUGE de template e LLM, fidelidade, taxa de aceitação, contagens) só existem nas saídas executadas do notebook da Sprint 3, não em `data/saida/`; o gerador as lê dali por expressão regular (`nb3.*`).
- O `sprint4` tem 0 saídas, então não há contagem de chunks nem outro número só presente na saída desse notebook; o documento não os cita (número sem fonte não entra).
- O gerador está em inglês (como `tools/nb_check.py` e a norma `padrao-escrita`), com comentários e mensagens ao usuário em português.
- `--check` não detecta número de resultado digitado fora de marcador; só o revisor, por leitura.
- Licença: não existe `LICENSE` e criá-lo está fora do escopo (§3.1); o README diz que está pendente.
- A `code-entrega` (assinatura, licença, documentação) não foi percorrida como fluxo: assinatura conferida por `grep` (nenhuma marca de agente ou colaborador nos arquivos do projeto), licença e CONTRIBUTING/CHANGELOG/CODEOWNERS fora do escopo da plan.

**Achados fora do escopo (não corrigidos)**
- `.env.example:2` — lista `GROQ-API-KEY`, variável que o código não usa (só `OPEN-ROUTER-API-KEY`/`OPENROUTER_API_KEY`).
- Ausência de `LICENSE` no repositório (a escolha é do dono; skill `code-licenca`).
- `requirements.txt` fixa `PyMuPDF==2.1` e o ambiente local tem 1.28.0: o `pytest` local falha em 12 testes enquanto o venv limpo não for criado.

**Pendências / riscos**
- **Executar o `sprint4_pln_rag.ipynb` localmente** (comando no README) e só então rodar `nb_check --executado`; a conferência "saídas do notebook × `data/saida/`" do passo 6 não pôde ser feita para ele. Como `data/saida/` já foi gerado por uma execução de 2026-11-25, o documento reflete essas saídas; se a re-execução mudar um número, rode `python tools/gerar_relatorio_final.py` (e com `--documento docs/matriz-criticas.md`) e confira o diff.
- Rodar `pytest` num venv com `requirements.txt` (PyMuPDF fixado) para confirmar os 12 testes que falham aqui por versão.
- Colar o link do vídeo no `README.md` (`<!-- VIDEO_URL -->`).
- Sugiro ao revisor que esta entrega peça também licença e `.env.example` limpo, mas isso é decisão dele.

---

# 10. Veredito

<!-- Preenchido pelo REVISOR. Append-only: um bloco por rodada, com o que foi verificado e como. -->

---

## Veredito — 2026-11-25 — 🟢 Aprovado

**Verificado (venv Python 3.11, PyMuPDF 2.1, `MPLBACKEND=Agg`, nível ampla):**
- `git status`/`diff`: só os arquivos de §3.1 (`README.md`, `docs/relatorio-final.md`, `docs/matriz-criticas.md`, `docs/roteiro-video.md`, `tools/gerar_relatorio_final.py`) e os dois notebooks executados no lugar; nada em `src/` nem em `data/` (as saídas regeneradas na execução local saíram idênticas às versionadas, graças ao cache de LLM).
- `python -m pytest tests -q` → **185 passed**.
- Fase B (feita pelo dono, `nbconvert --execute --inplace`, sem `--allow-errors`): `sprint3` 14/14 e `sprint4` 23/23 células executadas, **nenhuma saída de erro**; `nb_check --executado` → válido nos dois. O `stderr` do `sprint4` é só carga de pesos/aviso do HF e o aviso documentado de citação ausente (seção 13).
- `gerar_relatorio_final.py --check` → 156 marcadores, 0 erro (documento final); `--documento docs/matriz-criticas.md` → 28 marcadores, 0 erro. A execução recente do `sprint3` não mudou nenhum número.
- Saídas do `sprint4` × `data/saida/cenarios.json`: A-4468 (172.01 A), A-4471 (4.87 mm/s), leitura calma `6c6a1a25-…` e adversarial A-1800 (1850 rpm) presentes.
- Enunciado ("Formato da Entrega"): 2 notebooks executados, documento final com templates, critérios, arquitetura do RAG, métricas e limites, matriz F1–F7 (F3 assumida como parcial) e roteiro de 280 s com os 3 cenários presentes; o vídeo em si é do dono.
- Sem chave nas saídas dos notebooks nem no repositório (`sk-or-` só aparece como padrão de detecção em `tools/nb_check.py` e na plan); `.env` ignorado.

**Registrado no backlog (não reprova):** `.env.example:2` lista `GROQ-API-KEY` (não usada) e o README manda copiá-lo; falta `LICENSE` (decisão do dono, skill `code-licenca`); o aviso `tqdm` da seção 2 do `sprint4` imprime um caminho local do usuário na saída versionada; o link do vídeo em `README.md` (`<!-- VIDEO_URL -->`) só o dono cola, depois de gravar e publicar como "não listado".
