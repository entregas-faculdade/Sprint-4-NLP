---
tipo: "plan"
familia: "02"
item: "R02.2"
titulo: "Construir o assistente de troubleshooting com citação, confiança calculada e abstenção"
dominio: "Sprint 4 — RAG e assistente"
status: "🟢 Aprovada"
prioridade: "Alta"
tags: ["plan", "sprint-4", "assistente", "F3", "F4", "F6"]
relacionados: ["[[00-contexto]]", "[[02.01-pipeline-rag]]"]
depende_de: ""
destino_sintese: "specs/02.02-assistente-de-troubleshooting.md + 00-contexto.md"
---

# 1. Objetivo

O assistente responde com base **apenas** nos chunks recuperados, **cita página e seção** de cada fonte, informa um **nível de
confiança calculado por código** (não autodeclarado pelo LLM), **se abstém sem chamar o LLM** quando a recuperação não sustenta a
resposta, mantém **memória de curto prazo** e recebe o **estado operacional** como dado confiável.

# 2. Contexto

- Entrega anterior: prompt dizia "Responda com confiança, assertividade"; o modelo citou "trechos do manual" que eram do próprio texto
  dele, declarou "Alto (95 %)" sem lastro e **contradisse o estado** (afirmou que 47 °C "não é crítico"). O juiz não penalizou
  conhecimento externo (F6 é atacado na plan 02.03; aqui se **previne** na geração).
- Princípio do dono: fatos por código, LLM só redige. Aqui: fontes, página, seção, confiança e abstenção são **calculadas**.
- Usa `Retriever` e `EstadoOperacional` (spec `02.01-pipeline-rag`) e `llm.py` (plan 01.01; `MODELO_GERADOR`).

# 3. Escopo

## 3.1 Dentro
- `src/pln/assistente.py` — `Assistente`, prompt de sistema, memória, citação, confiança, abstenção
- `src/pln/config.py` — acrescentar: `MEMORIA_TURNOS`, `LIMIAR_ABSTENCAO`, faixas de confiança, frase de abstenção, marcadores
- `src/pln/rag.py` — **só** expor o escore bruto do reranker: cada item de `Retriever.buscar` ganha o campo `score_rerank_bruto` (o valor que
  `reranker.predict` devolveu, sem normalizar). `score_rerank`, `score_final`, a ordenação e o restante do módulo não mudam.
- `tests/test_rag.py` — um teste do campo novo (valor bruto preservado; `score_rerank` continua min-máx)
- `tests/test_assistente.py`
- `notebooks/sprint4_pln_rag.ipynb` — acrescentar seções 7 e 8

## 3.2 Fora
- Métricas, gabarito, juiz e calibração final de `LIMIAR_ABSTENCAO` — plan 02.03 (aqui vale um valor **provisório** documentado)
- Cenários de demonstração — plan 02.04
- `rag.py` além do campo `score_rerank_bruto`, `estado.py`, `alertas.py`: só consumir

# 4. Referências obrigatórias

| Tipo | Referência | Por quê |
|---|---|---|
| Spec fixa | `specs/02.01-pipeline-rag.md` · `specs/01.01-alertas-deterministicos.md` | retriever, estado, cliente LLM |
| Contexto | `00-contexto.md` · `00-knowledge.md` | regras inegociáveis (§2, §7) |
| Requisito | `docs/feedback-professor.md` · `enunciado-4.txt` | persona, citar fonte, nível de confiança, histórico, estado |
| **Skill** | `padrao-escrita` + `padrao-python` · `test-unitario` · `code-auditoria-padrao` | escrita, testes, gate |
| Código | `src/pln/rag.py` · `src/pln/estado.py` · `src/pln/llm.py` · `src/pln/config.py` | reaproveitar |

# 5. Instruções de execução

1. [dirigido] **Prompt de sistema** (constante em `config.py`, em português): persona de assistente técnico especialista em motores
   elétricos WEG W22; responder **somente** com o conteúdo do bloco `CONTEXTO DO MANUAL`; citar cada afirmação no formato
   `[p. <página>, seç. <seção>]` usando só páginas/seções presentes no contexto; **não** usar conhecimento externo, **não** inventar
   números; tratar o bloco `ESTADO OPERACIONAL` como **dado confiável do sistema** (não reinterpretar nem contestar valores/severidades);
   se o contexto não cobrir, responder exatamente a frase de abstenção; terminar com a linha `Confiança: <Alta|Média|Baixa>`.
1a. [dirigido] **Escore bruto (pré-requisito).** `score_rerank` é normalizado min-máx dentro dos candidatos: o melhor chunk recebe sempre
   1,0, inclusive para pergunta fora do escopo, e não serve para abster nem para calcular confiança. Em `rag.py::_pontuar_candidatos`,
   guardar em cada candidato `score_rerank_bruto = float(valor)` antes da normalização, e garantir que ele sai em `Retriever.buscar`. Sem
   outra mudança de comportamento; teste em `test_rag.py` com reranker falso de valores conhecidos.
2. [dirigido] **Montagem do prompt** em `assistente.py`: mensagens `system` + histórico (`MEMORIA_TURNOS`, padrão 3, em papéis
   `user`/`assistant`) + `user` com os blocos `ESTADO OPERACIONAL` (de `EstadoOperacional.texto()`), `CONTEXTO DO MANUAL` (cada chunk
   rotulado com `[p. N, seç. X]`) e `PERGUNTA`.
3. [dirigido] **Consulta de recuperação com memória, sem LLM:** se a pergunta for curta (< 6 palavras) ou contiver anáfora
   (`desse`, `dessa`, `isso`, `ele`, `ela`, `nesse`, `neste`…), a consulta de busca = pergunta anterior do usuário + pergunta atual;
   caso contrário, só a atual. O estado vai ao retriever (`estado=`).
4. [dirigido] **Abstenção determinística:** se `score_rerank_bruto` do melhor chunk < `LIMIAR_ABSTENCAO`, devolver a frase de abstenção
   **sem chamar o LLM** (`abstencao=True`, `fontes=[]`). O limiar é parâmetro; valor provisório definido por inspeção de ≥ 6 consultas
   (3 dentro e 3 fora do escopo) e registrado no notebook; a plan 02.03 o calibra.
5. [dirigido] **Confiança calculada** (`Alta`/`Média`/`Baixa`) por faixas do `score_rerank_bruto` do melhor chunk e do nº de chunks acima do
   limiar, definidas em `config.py`. Após a resposta, **substituir** a linha `Confiança:` do LLM pela calculada (a do modelo é
   descartada). Abstenção → `Baixa`.
6. [dirigido] **Citações verificadas:** extrair `[p. N, seç. X]` da resposta; qualquer par que **não** esteja entre os chunks
   fornecidos é `citacao_invalida` (registrar; não corrigir em silêncio). `fontes` do retorno = pares citados válidos, resolvidos para
   (`pagina`, `secao`, `secao_titulo`, `chunk_id`); se o LLM não citar nada, `fontes` = os chunks usados e `citou=False`.
7. [dirigido] **Retorno** `Resposta`: `texto`, `fontes`, `confianca`, `abstencao`, `citacao_invalida`, `citou`, `modelo`, `consulta_usada`,
   `chunks` (os usados, com scores), `estado_texto`. Histórico guarda pergunta e resposta final. `Assistente.reiniciar()` limpa a memória.
8. [dirigido] Testes (skill `test-unitario`; retriever e LLM **falsos**): abstenção não chama o LLM; confiança calculada sobrescreve a do
   modelo; citação a página fora do contexto é marcada; consulta de seguimento ("E quais as causas desse problema?") incorpora a
   pergunta anterior; o estado aparece no prompt e o retriever recebe `estado`; histórico limitado a `MEMORIA_TURNOS`; prompt contém a
   instrução de dado confiável do estado. Pronto: `python -m pytest tests -q` verde.
9. [dirigido] Notebook (seções 7 e 8, sem saídas): **7** Assistente (o prompt de sistema exibido; fluxo; tabela dos parâmetros) ·
   **8** Smoke: 3 perguntas dentro do escopo, 2 de seguimento (memória) e 3 fora do escopo, mostrando `consulta_usada`, fontes,
   confiança e abstenção; registrar o `LIMIAR_ABSTENCAO` provisório e como foi escolhido. Rodar pytest, `nb_check`, `code-auditoria-padrao`.

# 6. Critérios de aceite

- [ ] `Retriever.buscar` expõe `score_rerank_bruto`, e abstenção e confiança usam só ele (nunca `score_rerank` normalizado).
- [ ] Perguntas fora do escopo recebem a frase de abstenção **sem chamada ao LLM** (teste).
- [ ] A linha `Confiança:` final é sempre a calculada; nunca a autodeclarada.
- [ ] Toda resposta traz fontes no formato `[p., seç.]` resolvidas; citação inexistente é sinalizada (`citacao_invalida`).
- [ ] A pergunta de seguimento recupera pelo assunto anterior (teste e demonstração).
- [ ] O estado operacional entra na recuperação **e** no prompt, marcado como dado confiável.
- [ ] Nenhum id de modelo, limiar ou frase fixa fora de `config.py`.
- [ ] **Fase B:** seção 8 executada localmente sem erro, com os 3 tipos de pergunta e `modelo` registrado em cada resposta.
- [ ] Ambiente e worktree limpos; testes do escopo verdes; `code-auditoria-padrao` sem violação nova.

# 7. Como verificar (uso do revisor)

- **Nível:** `ampla`, pelo motivo escrito: a plan altera `rag.py`, consumido pelo notebook e por `tests/test_rag.py`.
- `git diff --stat` → só os arquivos de §3.1.
- **Fase A:** `python -m pytest tests -q` (sem `test_rag_modelos`, se os pesos não estiverem em cache) · `python tools/nb_check.py notebooks/sprint4_pln_rag.ipynb` · `code-auditoria-padrao`.
- Leitura de `src/pln/assistente.py` → o caminho de abstenção retorna antes de qualquer chamada de rede; a linha `Confiança:` é reescrita.
- **Fase B:** `python tools/nb_check.py notebooks/sprint4_pln_rag.ipynb --executado` · leitura da saída da seção 8.
- **Gate:** `nenhum`.

# 8. Destino da síntese

**Destino:** `specs/02.02-assistente-de-troubleshooting.md` + `00-contexto.md`

Texto para transporte: o prompt de sistema e suas regras; contrato de `Resposta`; regras de abstenção, confiança (faixas) e citação;
política de memória (3 turnos, consulta de seguimento); tratamento do estado como dado confiável; o campo `score_rerank_bruto` do retriever (atualizar a spec `02.01-pipeline-rag` §2.6). Em `00-contexto.md`, trocar a linha da §4.

---

# 9. Resumo da execução

<!-- Preenchido pelo EXECUTOR. Append-only: cada rodada acrescenta um bloco novo; nada é removido. -->

## Resumo da execução — 2026-11-25

**Resultado:** Concluído com pendências

**O que foi feito**
- Implementei o contrato `Resposta` e o fluxo de recuperação, prompt, memória de três turnos, estado confiável, validação de citações, confiança calculada e abstenção determinística — `src/pln/assistente.py:53`.
- Acrescentei em `Retriever.buscar` somente `score_rerank_bruto`; scores normalizados, score final, ordenação e restante de `rag.py` permanecem como estavam — `src/pln/rag.py:956`.
- Centralizei no `config.py` o prompt, os limiares, as faixas e as frases do assistente — `src/pln/config.py:178`.
- Adicionei testes unitários para o assistente e para a preservação do score bruto — `tests/test_assistente.py:60` e `tests/test_rag.py:385`.
- Acrescentei as seções 7 e 8 sem outputs, incluindo a inspeção de seis consultas e o limiar provisório — `notebooks/sprint4_pln_rag.ipynb:230`.

**Arquivos alterados**
| Arquivo | Natureza | O que mudou |
|---|---|---|
| `src/pln/assistente.py` | criado | Assistente, contrato de resposta, memória, estado, citações, confiança e abstenção |
| `src/pln/config.py` | alterado | Parâmetros e prompt do assistente |
| `src/pln/rag.py` | alterado | Apenas o campo `score_rerank_bruto` |
| `tests/test_assistente.py` | criado | Testes do contrato e dos fluxos do assistente |
| `tests/test_rag.py` | alterado | Teste do score bruto e da normalização preservada |
| `notebooks/sprint4_pln_rag.ipynb` | alterado | Seções 7 e 8, sem execução nem outputs |
| `specs/plan/plan-02.02-assistente-de-troubleshooting.md` | alterado | Status de revisão e este resumo; a atualização de escopo já estava no estado inicial |

**Verificações executadas**
- `python -m pytest tests -q` — a primeira execução teve 83 aprovados e 13 erros porque o Windows negou acesso ao diretório temporário padrão do pytest. Reexecutei com `--basetemp` isolado e `HF_HUB_OFFLINE=1`, `TRANSFORMERS_OFFLINE=1`: **96 passaram, 2 avisos, 525,41 s**.
- `python tools/nb_check.py notebooks/sprint4_pln_rag.ipynb` — **Notebook válido**; as células offline passaram e o smoke da seção 8 não foi executado.
- Validador `padrao-python/scripts/validate.py` nos cinco arquivos Python alterados — exit code 0; sem achados nos quatro arquivos além de `config.py`, que reporta apenas o URL preexistente de `src/pln/config.py:167`, com confiança baixa.
- AST dos cinco arquivos Python e compilação das células — passaram; notebook JSON válido, 16 células, códigos sem outputs e `execution_count` nulo.
- `git diff --check` — passou; Git emitiu apenas avisos de conversão LF/CRLF.

**Estado inicial do worktree:** `M specs/plan/plan-02.02-assistente-de-troubleshooting.md` — atualização de escopo feita pelo usuário; nenhum outro arquivo modificado.

**Ambiente após a verificação:** o diff do ambiente apontou o diretório temporário isolado do pytest; removi esse diretório, o ambiente virtual temporário e o snapshot, e confirmei que os três alvos não existem. Inventário de processos indisponível por falha de consulta; Docker indisponível. Quatro entradas de `system_temp` foram apenas informativas e ficaram intocadas. Branch e worktrees não mudaram.

**Critérios de aceite**
- [x] `Retriever.buscar` expõe o score bruto, e confiança e abstenção usam esse campo — teste em `tests/test_rag.py:385` e implementação em `src/pln/assistente.py:141`.
- [x] Abstenção abaixo do limiar não chama o LLM — `tests/test_assistente.py:60`.
- [x] Confiança final é calculada e substitui a linha declarada pelo modelo — `tests/test_assistente.py:74`.
- [x] Citações são resolvidas contra os chunks e citações ausentes são sinalizadas — `tests/test_assistente.py:85`.
- [x] Seguimentos curtos e anafóricos reutilizam a pergunta anterior — testes em `tests/test_assistente.py:98` e `tests/test_assistente.py:113`.
- [x] Estado segue para o retriever e aparece como dado confiável no prompt — `tests/test_assistente.py:126`.
- [x] Parâmetros e frases fixas do assistente ficam em `config.py` — `src/pln/config.py:178`.
- [ ] **Fase B:** execução local da seção 8, incluindo o modelo em cada resposta — pendente para a execução local com a chave OpenRouter.
- [x] Testes, `nb_check`, auditoria e limpeza dos artefatos temporários concluídos; sem violação nova no validador.

**Decisões e suposições**
- Usei `LIMIAR_ABSTENCAO=-3.0` como provisório após inspecionar seis consultas reais offline. O maior score fora do escopo foi `-3.027231`; com esse limiar as três consultas externas abstêm. A consulta interna de ventilação (`-4.239105`) também abstém e o limiar deve ser recalibrado na plan 02.03.
- Trabalhei diretamente na `main`, conforme declarado no contexto e confirmado pelo usuário.

**Achados fora do escopo (não corrigidos)**
- `src/pln/config.py:167` — o auditor marca a URL do cliente como hardcoded com confiança baixa; a mesma linha já existia em `HEAD`, então não é uma violação introduzida nesta execução.
- O pytest não conseguiu criar o cache padrão em `.pytest_cache/` por uma condição de permissão/arquivo existente; não alterei esse caminho compartilhado.

**Pendências / riscos**
- A seção 8 ainda precisa ser executada localmente com OpenRouter; nenhuma chamada ao LLM foi feita nesta execução.
- A calibração é provisória e faz três consultas internas e três externas; a pergunta sobre ventilação mostra o trade-off de abstenção até a avaliação da plan 02.03.
- O primeiro uso do diretório temporário padrão do pytest falhou por permissão; a suíte completa passou no diretório isolado.

## Retificação do resumo da execução — 2026-11-25

As referências de linha dos testes no bloco anterior ficam retificadas para corresponder às declarações atuais: citação inválida em `tests/test_assistente.py:88`; seguimentos em `tests/test_assistente.py:100` e `tests/test_assistente.py:114`; estado no prompt e retriever em `tests/test_assistente.py:127`. O conteúdo e os resultados relatados no resumo anterior permanecem os mesmos.

## Resumo da execução (correção 1) — 2026-11-25

**Resultado:** Concluído com pendências

**Achados corrigidos**
1. Ampliei `ANAFORES_ASSISTENTE` com os demonstrativos e formas flexionadas apontados; um teste parametrizado verifica os seguimentos com “essa” e “esse” — `src/pln/config.py:193` e `tests/test_assistente.py:121`.
2. Medi 10 consultas dentro do escopo, incluindo duas compostas, e 6 fora; a tabela da seção 7 registra cada score bruto. O limiar provisório agora segue `ceil((maior_score_fora + margem) * 10) / 10`, com margem mínima `0.1` e `LIMIAR_ABSTENCAO=-2.9`. A amostra não tem limiar separador, e os dois casos de ventilação permanecem visíveis como casos abertos. O smoke imprime texto para respostas não abstidas; o par de proteção tem seguimento composto com score `8.729171` — `src/pln/config.py:180`, `notebooks/sprint4_pln_rag.ipynb:230` e `notebooks/sprint4_pln_rag.ipynb:297`.

**Verificações**
- `python -m pytest tests -q --basetemp <diretório temporário isolado>` — **98 passaram, 2 avisos, 495,63 s**.
- `python tools/nb_check.py notebooks/sprint4_pln_rag.ipynb` — notebook válido; a seção 8 permaneceu sem execução.
- Validador Python em `src/pln/config.py` e `tests/test_assistente.py` — exit code 0; nenhum achado novo. O URL em `config.py:167` é preexistente e de confiança baixa.
- AST, conteúdo/estrutura do notebook e `git diff --check` passaram; sem outputs no notebook.

**Estado inicial do worktree nesta correção:**
```text
M data/saida/cache_llm.jsonl
M notebooks/sprint4_pln_rag.ipynb
M specs/00-backlog.md
M specs/00-indice.md
M specs/panorama/00-resumo.md
M specs/plan/plan-02.02-assistente-de-troubleshooting.md
M src/pln/config.py
M src/pln/rag.py
M tests/test_rag.py
?? src/pln/assistente.py
?? tests/test_assistente.py
```

**Ambiente:** diff apontou o diretório de teste isolado, removido junto com a venv temporária e o snapshot; os alvos foram confirmados ausentes. Consulta de processos indisponível e Docker indisponível; uma entrada de `system_temp` ficou intocada por não ser atribuível.

**Pendente:** a Fase B não foi executada; o veredito determina que o revisor a repita no notebook corrigido.

---

# 10. Veredito

<!-- Preenchido pelo REVISOR. Append-only: um bloco por rodada, com o que foi verificado e como. -->

## Veredito — 2026-11-25 — 🔴 Reprovado

**Verificado.** `git status`/`git diff --stat`: só os arquivos de §3.1 (`assistente.py`, `config.py`, `rag.py` com **apenas** `score_rerank_bruto`, `test_assistente.py`, `test_rag.py`, notebook) e a plan; nada fora do escopo. Leitura de `assistente.py`: o caminho de abstenção retorna antes de qualquer chamada de rede (`_recuperacao_sustenta`); a linha `Confiança:` é reescrita (`_substituir_confianca`); citações resolvidas contra os chunks (`_extrair_fontes`); estado no prompt e no retriever; memória limitada a `MEMORIA_TURNOS`. Fase A na venv limpa (Python 3.11.9, pesos em cache): `python -m pytest tests -q -m "not modelos"` → **94 passed**; `nb_check` → válido. Fase B: `nbconvert --execute` sem `--allow-errors` terminou **sem erro** (a 1ª tentativa falhou só por `Kernel didn't respond in 60 seconds`, e passou com `startup_timeout=300`); `modelo` = `meta-llama/llama-3.3-70b-instruct` em todas as 8 respostas; nenhuma chave nas saídas.

**Saída da seção 8 (o que ela mostra).**

| Pergunta | `consulta_usada` | Resultado |
|---|---|---|
| Qual é o grau de proteção do motor WEG W22? | só a atual | responde, p. 18 seç. 7, Alta |
| E o que essa proteção significa? | **só a atual** (sem a anterior) | **abstém** |
| Qual é a classe de isolamento…? | só a atual | responde, p. 19 seç. 8, Média |
| Quais são as características do sistema de ventilação? | só a atual | **abstém** (dentro do escopo) |
| E quais são as características desse sistema? | ventilação + atual | **abstém** |
| 3 perguntas fora do escopo | — | abstêm (a de pão de queijo herdou a pergunta anterior por ter < 6 palavras, conforme o passo 3) |

**Achados.**

1. `src/pln/config.py` (`ANAFORES_ASSISTENTE`) — a lista só tem `desse, dessa, isso, ele, ela, nesse, neste`. "E o que **essa** proteção significa?" tem 6 palavras e não casa nenhuma anáfora, então a memória **não** é aplicada (`consulta_usada` = só a pergunta atual) e o seguimento abstém. O critério "a pergunta de seguimento recupera pelo assunto anterior (teste e demonstração)" falha nesse caso. Correção: cobrir os demonstrativos e pronomes do português (`esse`, `essa`, `esses`, `essas`, `este`, `esta`, `isto`, `aquele`, `aquela`, `desta`, `deste`, `nessa`, `nesta`…) e acrescentar teste de seguimento com "essa" e com "esse".
2. `notebooks/sprint4_pln_rag.ipynb` (seções 7 e 8) e `config.py` (`LIMIAR_ABSTENCAO = -3.0`) — o limiar foi posto 0,027 acima do único maior escore fora do escopo (`-3,027`), um ajuste a um ponto só, e a própria tabela mostra que uma pergunta dentro do escopo (ventilação, `-4,24`) pontua abaixo de perguntas fora dele. Resultado: das 5 perguntas dentro do escopo (3 + 2 seguimentos), só 2 são respondidas, e nenhum seguimento é respondido; a demonstração de memória acaba em abstenção e não prova nada. Correção: (a) ampliar a inspeção para ≥ 10 perguntas dentro do escopo (inclusive consultas de seguimento já compostas) e ≥ 6 fora, e registrar a tabela de escores brutos; (b) declarar no notebook a regra do limiar provisório e a margem, e dizer explicitamente, se for o caso, que nenhum limiar separa as duas populações (a ventilação fica registrada como caso aberto para a plan 02.03); (c) a seção 8 deve mostrar **pelo menos um par pergunta + seguimento em que o seguimento é respondido**, com `consulta_usada` composta, e imprimir o `texto` das respostas não abstidas (hoje não há como ver citação nem a linha `Confiança:`); (d) a ação (c) não pode esconder o caso da ventilação: ele permanece na tabela.

**Fora do escopo desta correção.** O escore bruto do reranker não separa bem as duas populações (pergunta de ventilação abaixo de perguntas fora do escopo): registrado no `00-backlog` (item 4); a plan 02.03 mede e recalibra. A heurística de URL em `config.py:167` continua preexistente.

Escopo da correção: exclusivamente os achados 1 e 2. Verificação: `python -m pytest tests -q` e `nb_check` na venv limpa; a Fase B (notebook executado) será repetida pelo revisor sobre o código corrigido.

## Veredito — 2026-11-25 — 🟢 Aprovado

**Verificado.** `git status`/`git diff --stat`: só os arquivos de §3.1, a plan e `data/saida/cache_llm.jsonl` (cache de chamadas ao LLM, gravado pelas execuções do notebook). Achados da rodada anterior atendidos: (1) `ANAFORES_ASSISTENTE` cobre demonstrativos e flexões (`esse/essa/este/esta/isto/aquele/…`, com `de-`/`em-`), com teste parametrizado para "essa" e "esse"; (2) a seção 7 traz a inspeção de 10 consultas dentro e 6 fora do escopo com os escores brutos, a regra do limiar (`ceil((maior_score_fora + margem) * 10) / 10`, margem 0,1, `LIMIAR_ABSTENCAO = -2.9`), a declaração de que nenhum limiar separa as populações e os dois casos de ventilação mantidos como abertos; a seção 8 imprime o texto das respostas não abstidas. Fase A na venv limpa (Python 3.11.9, pesos em cache): `python -m pytest tests -q` → **98 passed, 0 skipped**; `nb_check` → válido. Fase B (`nbconvert --execute`, sem `--allow-errors`): sem erro; modelo `meta-llama/llama-3.3-70b-instruct` registrado em todas as respostas; nenhuma chave nas saídas. Saída da seção 8: grau de proteção respondido (p. 18, seç. 7, Alta, com citação); "E o que essa proteção significa?" com `consulta_usada` composta com a pergunta anterior e respondido (fontes p. 18 seç. 7 e p. 14 seç. 4.4, citações no texto); classe de isolamento respondida (p. 19, seç. 8, Média); ventilação e o seguimento dela abstêm (casos abertos, declarados); as 3 perguntas fora do escopo abstêm sem chamada ao gerador.

**Resumo do executor × diff.** Confere (`rag.py` só com `score_rerank_bruto`; escopo respeitado).

**Observações para a plan 02.03 (não bloqueiam).** (a) A resposta ao seguimento afirma que a proteção IPW55 oferece "especificações adicionais para ambientes mais agressivos" e cita "jatos de água", o que o chunk citado talvez não diga: é o tipo de afirmação que o juiz por afirmação (F6) deve medir. (b) O seguimento de ventilação abstém por limiar: recalibração na 02.03 (backlog #4).

**Para a síntese (02.02-assistente-de-troubleshooting).** Transportar: prompt de sistema e regras; contrato `Resposta`; abstenção por `score_rerank_bruto` (sem LLM), faixas de confiança (Alta ≥ 8,0 com ≥ 3 chunks acima do limiar; Média ≥ 0,0 com ≥ 1; senão Baixa), citação verificada e `citacao_invalida`; memória de 3 turnos e consulta de seguimento (< 6 palavras ou anáfora); estado como dado confiável; campo `score_rerank_bruto` do retriever (atualizar a §2.6 da spec `02.01-pipeline-rag`); limiar provisório `-2.9` e a regra. Não transportar: rodadas e achados.
