---
tipo: "plan"
familia: "02"
item: "R02.4"
titulo: "Demonstrar os três cenários em separado e documentar os limites observados"
dominio: "Sprint 4 — RAG e assistente"
status: "🟢 Aprovada"
prioridade: "Alta"
tags: ["plan", "sprint-4", "cenarios", "limites", "F7"]
relacionados: ["[[00-contexto]]", "[[02.03-avaliacao-rag]]"]
depende_de: ""
destino_sintese: "specs/02.04-cenarios-e-limites.md + 00-contexto.md"
---

# 1. Objetivo

O notebook demonstra, **em três seções separadas**, o assistente diante de (1) **anomalia elétrica**, (2) **anomalia mecânica** e (3)
**consulta de manutenção preventiva**, cada uma com estado vindo dos **alertas reais** da Sprint 3, diálogo com memória, fontes por
página/seção, confiança calculada e avaliação; e documenta os **limites observados** com casos reais da execução (requisito **F7**).

# 2. Contexto

- Feedback: "demonstrem separadamente anomalia elétrica, mecânica e manutenção preventiva". Antes, houve só um cenário térmico e um teste
  de memória; o estado era um texto escrito à mão (`"Temperatura crítica registrada (47°C)…"`), não vinha da Sprint 3.
- O enunciado pede ainda "documentar os limites: perguntas fora do escopo, situações de alucinação identificadas e estratégias de mitigação".
- Já existem (plans anteriores): alertas determinísticos, `EstadoOperacional`, retriever com estado, assistente com abstenção, métricas e juiz.
- O catálogo não é manual de troubleshooting: os cenários devem usar perguntas que o corpus **consegue** responder (consultar a seção
  do PDF antes) e, **de propósito**, uma pergunta que ele não responde (para mostrar a abstenção).

# 3. Escopo

## 3.1 Dentro
- `data/cenarios.json` — **novo**: 3 cenários (+ 1 adversarial) com a escolha do episódio/alerta e as perguntas
- `src/pln/cenarios.py` — selecionar o alerta do cenário nos dados, montar o estado, rodar o diálogo e avaliar
- `tests/test_cenarios.py`
- `notebooks/sprint4_pln_rag.ipynb` — acrescentar seções 14 a 18
- `data/saida/` — `cenarios.json`, `limites.json`

## 3.2 Fora
- Qualquer mudança em `rag.py`, `assistente.py`, `avaliacao.py`, `alertas.py` (achado → backlog)
- Documento final, README, vídeo — plan 02.05
- Dados de origem, PDF

# 4. Referências obrigatórias

| Tipo | Referência | Por quê |
|---|---|---|
| Spec fixa | `specs/01.01-alertas-deterministicos.md` · `specs/02.01-pipeline-rag.md` · `specs/02.02-assistente-de-troubleshooting.md` · `specs/02.03-avaliacao-rag.md` | peças que os cenários usam |
| Contexto | `00-contexto.md` · `00-knowledge.md` | regras inegociáveis (§2, §7, §8) |
| Requisito | `docs/feedback-professor.md` · `enunciado-4.txt` | F7 e a seção de limites |
| **Skill** | `padrao-escrita` + `padrao-python` · `test-unitario` · `code-auditoria-padrao` | escrita, testes, gate |
| Código | `src/pln/alertas.py` · `src/pln/estado.py` · `src/pln/assistente.py` · `src/pln/avaliacao.py` · `data/saida/*.json` | reaproveitar |
| Dados | `docs/WEG-w22-motor-eletrico-trifasico-brochure.pdf` | confirmar que cada pergunta de cenário tem resposta na seção prevista |

# 5. Instruções de execução

1. [dirigido] **Escolha dos episódios** em `cenarios.py` (por regra, não à mão): (a) **elétrica** — o alerta de maior severidade da grandeza
   *corrente elétrica*; (b) **mecânica** — o de maior severidade de *vibração no mancal* (ou *velocidade*, se vibração não tiver crítico);
   (c) **preventiva** — um instante de **operação normal ou só alerta leve** (sem moderado/crítico nas 24 h anteriores). Empates: o mais
   recente. Gravar em `data/cenarios.json` o `alerta_id`/janela escolhidos e **por quê** (regra aplicada), para reprodutibilidade.
2. [dirigido] **Perguntas por cenário** em `data/cenarios.json`: 3 turnos cada — (1) a pergunta natural do operador diante do estado
   ("O que a corrente alta indica e o que o catálogo diz sobre proteção?"), (2) um **seguimento anafórico** ("E como isso se relaciona
   com a temperatura?") para exercitar memória, (3) uma pergunta que **o corpus não responde** (para mostrar abstenção). Antes de
   fixar cada pergunta (1) e (2), **confirmar no PDF** a página/seção que a sustenta e registrá-la como `fonte_esperada`. Preventiva: perguntas
   de procedimento (lubrificação/relubrificação, intervalos, inspeções) **que o PDF cobre**; se não cobrir, usar o que o catálogo traz
   (ex.: instruções de armazenamento/manutenção) e dizer isso.
3. [dirigido] **Cenário adversarial** (para a seção de limites): estado **contraditório** com a intuição do modelo (reproduzir o caso antigo:
   alerta crítico com valor que o modelo "acha baixo") e uma pergunta que **induz conhecimento externo** (ex.: "qual a causa raiz mais
   comum de vibração em motores?"). O objetivo é observar se o assistente respeita o estado e se abstém.
4. [dirigido] **Execução** em `cenarios.py`: para cada cenário, construir o `EstadoOperacional` do alerta real, rodar o diálogo (`Assistente`
   novo por cenário, memória própria), e registrar por turno: pergunta, consulta usada, fontes (página, seção), `confianca`, `abstencao`,
   `citacao_invalida`, resposta e `modelo`. Avaliar cada resposta com as funções de `avaliacao.py` (faithfulness por afirmação; relevancy
   quando houver `fonte_esperada`/referência curta) e verificar **fonte esperada ⊂ fontes recuperadas** (hit por cenário).
5. [dirigido] **Limites reais** (`data/saida/limites.json`, gerado do que **aconteceu** na execução e nas seções 10–13): tabela com
   (a) **fora do escopo** — perguntas que abstiveram e perguntas que **não** abstiveram (alucinação), (b) **alucinações observadas** —
   afirmações rotuladas `EXTERNA`/`CONTRADIZ` pelo juiz, com a frase real, (c) **limites do corpus** (catálogo comercial, sem
   troubleshooting), (d) **limites do método** (juiz LLM, 20 perguntas, gabarito por página), (e) **limites dos dados** (4 de 6 variáveis
   com limiar; nomes de variável inconsistentes; sem baseline histórico por motor), cada um com a **mitigação adotada** (abstenção
   determinística, verificador numérico, citação obrigatória, estado como dado confiável, juiz ≠ gerador) e o **risco que resta**.
   Nada genérico: cada linha cita um caso ou número da execução.
6. [dirigido] Testes (skill `test-unitario`; assistente e LLM falsos): a regra de escolha devolve o alerta esperado nos dados reais; os
   três estados têm domínios distintos (`elétrica`, `mecânica`, nenhum/leve); o cenário preventivo não usa alerta moderado/crítico; o
   diálogo reinicia a memória entre cenários; `limites.json` só cita ids/afirmações existentes na execução.
7. [dirigido] Notebook (sem saídas): **14** Como os cenários são escolhidos (regra, tabela dos 3 alertas com ids de leitura) · **15**
   Cenário 1 — anomalia elétrica · **16** Cenário 2 — anomalia mecânica · **17** Cenário 3 — manutenção preventiva · **18** Limites
   e mitigações (cenário adversarial + tabela de limites). Cada cenário em seção própria: estado (texto e ids), diálogo, fontes
   `[p., seç.]`, confiança, avaliação do cenário. Rodar pytest, `nb_check`, `code-auditoria-padrao`.

# 6. Critérios de aceite

- [ ] Três seções separadas e identificáveis (elétrica, mecânica, preventiva), cada uma com estado construído de um alerta real (id de alerta e de leitura citados).
- [ ] A escolha do episódio de cada cenário é determinística e registrada (`data/cenarios.json`).
- [ ] Cada cenário tem 3 turnos; o 2º usa memória (consulta de seguimento visível) e o 3º mostra abstenção.
- [ ] Cada resposta lista fonte por página/seção, confiança calculada e modelo; a avaliação do cenário usa o juiz por afirmação.
- [ ] `fonte_esperada` conferida no PDF e comparada com as fontes recuperadas em cada cenário.
- [ ] Seção de limites com ≥ 1 caso real por categoria (a)–(e) e mitigação + risco residual por linha; zero linhas genéricas.
- [ ] **Fase B:** notebook executado localmente sem erro, seções 14–18 com saídas e `data/saida/cenarios.json` e `limites.json`; `nb_check --executado` verde.
- [ ] Ambiente e worktree limpos; testes do escopo verdes; `code-auditoria-padrao` sem violação nova.

# 7. Como verificar (uso do revisor)

- **Nível:** `escopada`.
- `git diff --stat` → só os arquivos de §3.1.
- **Fase A:** `python -m pytest tests/test_cenarios.py -q` · `python tools/nb_check.py notebooks/sprint4_pln_rag.ipynb` · `code-auditoria-padrao`.
- Para cada cenário, abrir no PDF a página de `fonte_esperada` e confirmar a pergunta de procedimento.
- **Fase B:** `python tools/nb_check.py notebooks/sprint4_pln_rag.ipynb --executado` · leitura das seções 15–18; conferir 2 frases de `limites.json`
  contra a execução (afirmação citada existe na saída).
- **Gate:** `nenhum`.

# 8. Destino da síntese

**Destino:** `specs/02.04-cenarios-e-limites.md` + `00-contexto.md`

Texto para transporte: regra de escolha dos episódios e dos três cenários; estrutura do diálogo (3 turnos); critério de aceite do cenário;
tabela de limites com mitigações. Em `00-contexto.md`, trocar a linha da §4 e atualizar o §8 com limites que continuam valendo.

---

# 9. Resumo da execução

<!-- Preenchido pelo EXECUTOR. Append-only: cada rodada acrescenta um bloco novo; nada é removido. -->

## Resumo da execução — 2026-11-25

**Resultado:** Concluído com pendências (Fase A concluída; a Fase B é a execução local do notebook, do usuário)

**O que foi feito**
- `src/pln/cenarios.py` (novo): carga validada de `data/cenarios.json`; três regras de escolha de episódio (`maior_severidade`, `menor_valor`, `janela_calma`) sobre os alertas reais, com desempate pelo mais recente; execução por cenário (assistente novo por cenário, estado do alerta real, avaliação por `avaliar_resposta`, conferência de `fonte_esperada` por página/seção/âncora); `consolidar_cenarios`; `formatar_cenario`/`linhas_turnos`; `coletar_fatos_dados`; `montar_limites` + `validar_limites` (recusa id/afirmação que a execução não produziu e linha sem evidência).
- `data/cenarios.json` (novo): 3 cenários + 1 adversarial, episódio escolhido pela regra e registrado (A-4468 corrente 172,01 A; A-4471 vibração 4,87 mm/s; instante calmo 2026-08-23T09:46:39Z com 34 leituras candidatas; adversarial A-1800, velocidade 1850,47 rpm sozinha no estado), 3 turnos por cenário com `fonte_esperada` e referência curta, e os 10 modelos de limite (texto de limite, mitigação e risco residual).
- `tests/test_cenarios.py` (novo, 47 testes); `notebooks/sprint4_pln_rag.ipynb`: seções 14–18 sem saídas (a 14 é `offline`), tabela do índice e nota final atualizadas.
- `src/pln/config.py`: só constantes novas (caminhos de saída, tipos de regra/turno, categorias e origens de evidência).

**Arquivos alterados**
| Arquivo | Natureza | O que mudou |
|---|---|---|
| `src/pln/cenarios.py` | criado | escolha de episódio, execução, exibição, limites |
| `data/cenarios.json` | criado | cenários, episódios registrados, perguntas, modelos de limite |
| `tests/test_cenarios.py` | criado | 47 testes |
| `notebooks/sprint4_pln_rag.ipynb` | alterado | +12 células (seções 14–18), índice e nota final |
| `src/pln/config.py` | alterado | +19 linhas de constantes |

**Verificações executadas**
- `python -m pytest tests/test_cenarios.py -q` (com `PyMuPDF==2.1` fixado via PYTHONPATH) → 47 passed.
- `python tools/nb_check.py notebooks/sprint4_pln_rag.ipynb` (idem) → "Notebook válido".
- `validate.py` do `padrao-python` em `cenarios.py` e `test_cenarios.py` → 0 achados; em `config.py` → 1 achado já existente (URL do OpenRouter, linha 168).
- Sonda de recuperação com o retriever real (modelos locais, sem LLM) sobre as perguntas: todas as 1ª/2ª perguntas respondem acima do limiar (menor escore 3,46) com a página esperada entre os 4 chunks, e as 3ª perguntas abstêm (escores −1,9 a −4,2). Sonda descartável, fora do repositório.

**Estado inicial do worktree:** `git status --short` vazio (branch `main`, conforme `00-contexto` §5).

**Ambiente após a verificação:** sondas e pytest encerrados; instalei `PyMuPDF==2.1` em pasta do scratchpad (fora do repositório) só para rodar os testes com o pin; nada criado no repositório além do escopo.

**Critérios de aceite**
- [x] Três seções separadas, estado de alerta real — notebook §15–17; ids em `data/cenarios.json` e no `formatar_cenario`.
- [x] Escolha determinística e registrada — `test_episodio_registrado_e_o_que_a_regra_devolve_nos_dados_reais`.
- [x] 3 turnos, 2º com memória, 3º com abstenção — `test_segundo_turno_usa_a_memoria...`, `test_terceiro_turno_abstem...`.
- [x] Fonte, confiança, modelo e juiz por afirmação por resposta — registro de `avaliar_resposta` + `formatar_cenario`.
- [x] `fonte_esperada` conferida no PDF — `test_fonte_esperada_ocorre_na_pagina_indicada_do_pdf_real`; comparação com as recuperadas no registro (`hit_pagina/secao/ancora`).
- [x] Limites com as 5 categorias, mitigação e risco por linha, sem linha genérica — testes de `montar_limites`/`validar_limites`. A parte "caso real" só se materializa na Fase B.
- [ ] Fase B (notebook executado, `cenarios.json`/`limites.json`, `nb_check --executado`) — pendente: depende da execução local com a chave.
- [x] Testes do escopo verdes; auditoria sem violação nova.

**Decisões e suposições**
- Toquei `config.py` (fora da lista §3.1) só para constantes, pois a regra do projeto manda constantes em `config.py`.
- Regra adversarial ganhou o parâmetro `isolado` (alerta sozinho no estado), pois sem ele o estado do menor valor misturava três alertas críticos.
- Cenário 3 cai em "operação normal" (a leitura mais recente do CSV é calma), não "só leve".
- Perguntas escolhidas pela sonda de recuperação (a 1ª versão do seguimento elétrico abstinha por diluição da consulta composta); o 2º turno preventivo usa a seção 5.2.2 e o chunk correspondente vem rotulado 5.2.1: `hit_secao` pode sair falso com `hit_pagina` verdadeiro.
- O juiz só vê os chunks, não o estado: afirmações vindas do estado podem sair `EXTERNA`; registrado como risco no limite `alucinacao_afirmacoes`.
- Os hooks avisam "identificadores em português (ADR-023)"; segui o código vizinho do repositório, todo em português.

**Achados fora do escopo (não corrigidos)**
- `src/pln/config.py:168` — URL do OpenRouter literal (achado do validador, preexistente).
- Sem o `PyMuPDF` do pin, `extrair_paginas` falha neste ambiente (`use_layout`); afeta testes antigos e a célula 4 do `nb_check`.

**Pendências / riscos**
- Fase B. O gerador pode divergir do esperado (por exemplo, não abster no 3º turno se o escore mudar), o que a tabela de limites registra como observado.

---

# 10. Veredito

<!-- Preenchido pelo REVISOR. Append-only: um bloco por rodada, com o que foi verificado e como. -->

## Veredito — 2026-11-25 — 🟢 Aprovado

**Verificado (venv Python 3.11, PyMuPDF 2.1, `MPLBACKEND=Agg`, nível escopado):**
- `git status`/`diff --stat`: só os arquivos de §3.1, mais `src/pln/config.py` (constantes, justificado no resumo) e `data/saida/cache_llm.jsonl`; nenhum arquivo de `rag.py`, `assistente.py`, `avaliacao.py`, `alertas.py` tocado; nenhuma chave nas saídas; nenhum comentário citando plan.
- `python -m pytest tests/test_cenarios.py -q` → **47 passed**. `nb_check` → válido. `padrao-python/validate.py` em `cenarios.py` e `test_cenarios.py` → 0 achados.
- `fonte_esperada` conferida direto no PDF (leitura independente, normalizada): as 6 âncoras ocorrem nas páginas indicadas (19, 20, 14, 14, 14, 16); os 5 `termo_ausente` fora do escopo e os 2 adversariais não ocorrem no PDF.
- Fase B (execução local, `nbconvert --execute`, sem `--allow-errors`, código 0): seções 14–18 com saídas e sem erro; `nb_check --executado` sobre cópia → válido; `data/saida/cenarios.json` e `limites.json` gerados e idênticos entre as duas execuções. Três cenários com alerta real (A-4468 corrente 172,01 A; A-4471 vibração 4,87 mm/s; instante calmo de 23/08 com 34 candidatos), 3 turnos, seguimento com consulta composta, 3º turno abstém nos três; modelo gerador/juiz únicos. Limites: 10 linhas, ≥ 1 caso real por categoria; duas frases conferidas na execução (`eletrica-t2` "…não há informações suficientes no manual para determinar…" rotulada EXTERNA; `c10` esperado CONTRADIZ, final EXTERNA).
- Ambiente: processos do nbconvert encerrados; a regeneração do notebook alterou só o ruído numérico (`score_denso`) de `avaliacao_recuperacao.json` e `avaliacao_respostas.json` (fora do escopo desta plan) — restaurei esses dois ao `HEAD` com `git checkout --` (artefato da minha própria execução); cópia temporária do notebook removida.

**Registrado no backlog (não reprova):** em `mecanica-t2` o gerador respondeu a frase de abstenção com o escore bruto (3,39) acima do limiar e a página esperada recuperada; `PyMuPDF` fora do pin quebra testes de extração; URL do OpenRouter literal em `config.py:168`.

