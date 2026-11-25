---
tipo: "plan"
familia: "02"
item: "R02.5"
titulo: "Preparar a entrega: documento final, README, roteiro do vídeo e notebooks executados"
dominio: "Sprint 4 — RAG e assistente"
status: "🟡 Em execução"
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

---

# 10. Veredito

<!-- Preenchido pelo REVISOR. Append-only: um bloco por rodada, com o que foi verificado e como. -->
