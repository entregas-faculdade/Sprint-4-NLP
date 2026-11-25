---
tipo: "plan"
familia: "02"
item: "R02.3"
titulo: "Avaliar o RAG com gabarito de página e juiz por afirmação"
dominio: "Sprint 4 — RAG e assistente"
status: "🟢 Aprovada"
prioridade: "Alta"
tags: ["plan", "sprint-4", "avaliacao", "F5", "F6"]
relacionados: ["[[00-contexto]]", "[[02.02-assistente-de-troubleshooting]]"]
depende_de: ""
destino_sintese: "specs/02.03-avaliacao-rag.md + 00-contexto.md"
---

# 1. Objetivo

Medir, em 20 perguntas com gabarito de **página/seção** e em 5 perguntas fora do escopo, a **precisão da recuperação**
(hit@k, precision@k, MRR, context precision) e a **qualidade das respostas** (faithfulness por afirmação, answer relevancy),
comparando `LEGADO` × `NOVO` sem estado × `NOVO` com estado, com um **juiz validado** que não aceita conhecimento externo
(requisitos **F5** e **F6**).

# 2. Contexto

- Feedback: "avaliem a precisão dos chunks" e "revisem o juiz automático, que atribuiu alta fidelidade mesmo reconhecendo uso de
  conhecimento externo". Antes: nota 1–5 por resposta inteira, juiz do mesmo tipo do gerador, sem context precision, e
  `data/dados_avaliacao.json` com perguntas sobre Siemens/ABB que **não existem** no PDF indexado.
- Exemplo do defeito do juiz: "Qual a função do anel V-ring?" — a resposta admitiu que a informação não estava no contexto e
  respondeu com conhecimento geral; o juiz deu faithfulness 5/5. O termo "V-ring" tem **0 ocorrências** no PDF.
- O catálogo é comercial: parte das perguntas práticas **não tem resposta no corpus**. Isso entra como perguntas fora do escopo
  (a abstenção correta é o resultado esperado).
- `MODELO_JUIZ` ≠ `MODELO_GERADOR` (família diferente), sem fallback (`config.py`).

# 3. Escopo

## 3.1 Dentro
- `data/avaliacao_rag.json` — **novo**: 20 perguntas + 5 fora do escopo, com gabarito
- `data/juiz_calibracao.json` — **novo**: ≥ 12 casos rotulados à mão para validar o juiz
- `src/pln/avaliacao.py` — métricas de recuperação, juiz por afirmação, guardas determinísticas
- `src/pln/config.py` — acrescentar parâmetros de avaliação; **único** ajuste permitido em valor existente: `LIMIAR_ABSTENCAO` e `PESO_ESTADO`, com justificativa
- `tests/test_avaliacao.py`
- `notebooks/sprint4_pln_rag.ipynb` — acrescentar seções 9 a 13
- `data/saida/` — `avaliacao_recuperacao.json`, `avaliacao_respostas.json`, `juiz_calibracao.json`
- `data/dados_avaliacao.json` — **remover** (substituído por `alertas_teste.json` da plan 01.01 e `avaliacao_rag.json`)

## 3.2 Fora
- `rag.py`, `assistente.py`, `estado.py`, `alertas.py`, `classificacao.py`, `relatorio.py` — só consumir (um achado vira backlog)
- Cenários de demonstração — plan 02.04
- `docs/*.pdf`, dados de origem

# 4. Referências obrigatórias

| Tipo | Referência | Por quê |
|---|---|---|
| Spec fixa | `specs/02.01-pipeline-rag.md` · `specs/02.02-assistente-de-troubleshooting.md` | retriever, presets, assistente, abstenção |
| Contexto | `00-contexto.md` · `00-knowledge.md` | regras inegociáveis (§2, §7) |
| Requisito | `docs/feedback-professor.md` · `enunciado-4.txt` | F5, F6; faithfulness, answer relevancy, context precision |
| **Skill** | `padrao-escrita` + `padrao-python` · `test-unitario` · `code-auditoria-padrao` | escrita, testes, gate |
| Código | `src/pln/rag.py` · `src/pln/assistente.py` · `src/pln/llm.py` · `src/pln/config.py` | reaproveitar |
| Dados | `docs/WEG-w22-motor-eletrico-trifasico-brochure.pdf` | origem dos gabaritos (ler cada página citada) |
| Legado (só leitura) | `notebooks/sprint4_pln_rag.ipynb` (versão antiga, 20 perguntas) | reaproveitar perguntas válidas |

# 5. Instruções de execução

1. [dirigido] **Gabarito.** Criar `data/avaliacao_rag.json`: 20 perguntas (`escopo: "dentro"`) e 5 (`escopo: "fora"`). Cada pergunta de
   dentro traz: `id`, `pergunta`, `resposta_referencia` (curta, **só com o que o PDF diz**), `paginas_gabarito` (lista), `secoes_gabarito`,
   `trecho_ancora` (**frase literal** copiada do PDF que sustenta a resposta), `categoria` (`elétrica`, `mecânica`, `preventiva`,
   `especificação`), `split` (5 `dev`, 15 `teste`) e `estado` (opcional: um dos cenários sintéticos que o estado deve ativar, p. ex. "vibração
   crítica"; em ≥ 8 perguntas). Cobrir as categorias (≥ 4 de cada das três primeiras). **Cada pergunta deve ser respondível pelo PDF**
   (verificar lendo a página). Reaproveitar do legado só perguntas com resposta no PDF; descartar as que não têm (ex.: V-ring, cores de
   pintura se ausentes). As 5 `fora`: assuntos que o catálogo não cobre (outro fabricante, procedimento de bobinagem, preço…), com
   `esperado: "abstencao"`.
2. [dirigido] **Teste do gabarito:** para toda pergunta de dentro, `trecho_ancora` normalizado (espaços, hifenização) deve
   ocorrer no texto de alguma página de `paginas_gabarito`. Falhou = gabarito inventado. O usuário revisa o arquivo (resumo do executor aponta o caminho).
3. [dirigido] **Métricas de recuperação** em `avaliacao.py`, por configuração (`LEGADO`, `NOVO` sem estado, `NOVO` com estado) e por `k` ∈ {1, 4}:
   - chunk **relevante** = `pagina` ∈ `paginas_gabarito` (**relevância por página**) e, separadamente, `trecho_ancora` ⊂ chunk (**relevância estrita**);
   - `hit@k`, `precision@k`, `MRR@k` e **context precision@k** (fração de chunks relevantes entre os `k` entregues, ponderada pela posição);
   - relatório em tabela e por categoria; reportar o `teste` (15) separadamente do `dev` (5). Se `NOVO` não superar `LEGADO`, **dizer**.
4. [dirigido] **Juiz por afirmação** (`MODELO_JUIZ`, temperatura 0, cache): (a) dividir a resposta em afirmações **por frase**
   (código, sem LLM), ignorando a linha `Confiança:`, as citações e frases de abstenção; (b) para cada afirmação, o juiz recebe os chunks
   usados e devolve **um** rótulo: `SUSTENTADA` (decorre do contexto), `EXTERNA` (verdadeira ou não, mas **não está no contexto**),
   `CONTRADIZ` (contraria o contexto) ou `META` (não factual); (c) **faithfulness = SUSTENTADA / (SUSTENTADA + EXTERNA + CONTRADIZ)**;
   (d) **guardas determinísticas que prevalecem sobre o juiz:** todo número da afirmação ausente do contexto → `EXTERNA`; frase com marcador
   de conhecimento externo (`conhecimento geral`, `não consta`, `fora do contexto`, `em geral`, `normalmente`… lista em `config.py`) →
   `EXTERNA`; resposta de abstenção sem conteúdo factual → faithfulness 1,0 e `abstencao_correta` avaliada à parte.
5. [dirigido] **Answer relevancy:** o juiz classifica a resposta contra a `resposta_referencia` em `COBRE`, `PARCIAL` ou `NAO_COBRE` (pontos
   1, 0,5, 0), e registra a similaridade de cosseno entre embeddings (resposta × referência) como segundo sinal. **Abstenção em pergunta de
   dentro** conta como `NAO_COBRE`; **resposta factual em pergunta `fora`** conta como erro de abstenção (`alucinacao_fora_escopo`).
6. [dirigido] **Calibração do juiz.** `data/juiz_calibracao.json` com ≥ 12 casos `(contexto, afirmação, rótulo_esperado)` escritos à mão,
   ≥ 4 `EXTERNA` (incluir o V-ring e a "classe de isolamento F" quando o contexto não a traz), ≥ 3 `CONTRADIZ`, ≥ 3 `SUSTENTADA`. Medir
   acurácia, revocação de `EXTERNA` e matriz de confusão do juiz. Pode ajustar o prompt do juiz até 3 vezes **só com o `dev` da calibração**
   (6 casos); os demais ficam como teste. Reportar o resultado final, qualquer que seja.
7. [dirigido] **Calibrar `LIMIAR_ABSTENCAO` e `PESO_ESTADO`** no `dev` (5 perguntas de dentro + as 5 `fora`): varrer uma grade pequena e
   registrar a tabela; escolher o par que maximiza hit@4 mantendo abstenção correta nas 5 `fora`; atualizar `config.py`; o `teste` roda
   **depois**, uma vez.
8. [dirigido] **Execução e registro.** Rodar o assistente nas 25 perguntas com `MODELO_GERADOR`; gravar por pergunta: `modelo`, `consulta`,
   chunks (página, seção, scores), resposta, afirmações com rótulo, métricas. Nunca misturar modelos: erro de API → retentativa no mesmo modelo,
   persistindo falha → pergunta marcada `erro` e contada (não trocada).
9. [dirigido] Testes (skill `test-unitario`; juiz e LLM falsos): divisão em afirmações; guarda numérica reprova número ausente; guarda de
   marcador externo; faithfulness `S/(S+E+C)`; métricas de recuperação com listas conhecidas (hit, precision, MRR, context precision);
   gabarito (âncora no PDF; contagens 20+5; split 5/15; categorias); calibração calcula acurácia/recall; asserção `MODELO_JUIZ`≠`MODELO_GERADOR`.
10. [dirigido] Notebook (sem saídas): **9** Gabarito (contagens, 3 exemplos, teste da âncora) · **10** Recuperação: tabela `LEGADO` ×
    `NOVO` sem × com estado (hit@k, precision@k, MRR, context precision; dev e teste; por categoria) · **11** Juiz: protocolo,
    calibração e matriz de confusão · **12** Respostas: faithfulness e relevancy por pergunta, médias, abstenções, `alucinacao_fora_escopo`,
    **comparação com a entrega anterior** (4,75/5 e 3,50/5, ressalvando que o método mudou e os números não são comparáveis em escala) ·
    **13** Análise de erros (as 5 piores respostas, causa provável: recuperação, gabarito ou geração). Exportar `data/saida/`.
    Remover `data/dados_avaliacao.json`. Rodar pytest, `nb_check`, `code-auditoria-padrao`.

# 6. Critérios de aceite

- [ ] `avaliacao_rag.json`: 20 + 5 perguntas, split 5/15, categorias cobertas, `trecho_ancora` presente no PDF (teste automático).
- [ ] Recuperação reportada para as 3 configurações, k ∈ {1, 4}, hit@k, precision@k, MRR e context precision, em `teste` e `dev`.
- [ ] Faithfulness calculada **por afirmação**, com as guardas determinísticas; `EXTERNA` nunca conta como sustentada.
- [ ] Juiz validado em ≥ 12 casos com acurácia e revocação de `EXTERNA` reportadas; ajuste de prompt só com o `dev` da calibração.
- [ ] `MODELO_JUIZ` ≠ `MODELO_GERADOR`; todo registro traz o `modelo`; nenhuma pergunta mistura modelos.
- [ ] `LIMIAR_ABSTENCAO` e `PESO_ESTADO` calibrados no `dev`; `teste` rodado uma vez depois.
- [ ] Resposta factual a pergunta `fora` aparece como `alucinacao_fora_escopo`, não como acerto.
- [ ] `data/dados_avaliacao.json` removido; nenhum arquivo referencia perguntas de Siemens/ABB.
- [ ] **Fase B:** notebook executado localmente sem erro, seções 9–13 com saídas e `data/saida/avaliacao_*.json` presentes; `nb_check --executado` verde.
- [ ] Ambiente e worktree limpos; testes do escopo verdes; `code-auditoria-padrao` sem violação nova.

# 7. Como verificar (uso do revisor)

- **Nível:** `escopada`; `ampla` (motivo: altera `config.py`) com `python -m pytest tests -q` completo.
- `git diff --stat` → só os arquivos de §3.1 (e `data/dados_avaliacao.json` removido).
- **Fase A:** `python -m pytest tests -q` · `python tools/nb_check.py notebooks/sprint4_pln_rag.ipynb` · `code-auditoria-padrao`.
- Sorteio de 3 perguntas de `avaliacao_rag.json` → o revisor abre a página citada no PDF e confirma resposta e âncora.
- **Fase B:** `python tools/nb_check.py notebooks/sprint4_pln_rag.ipynb --executado` · leitura das saídas das seções 10–13 e conferência de
  3 afirmações rotuladas `SUSTENTADA` e 3 `EXTERNA` contra o contexto.
- **Gate:** `nenhum`.

# 8. Destino da síntese

**Destino:** `specs/02.03-avaliacao-rag.md` + `00-contexto.md`

Texto para transporte: composição do gabarito (20 + 5, split, âncora); definição de relevância (página e estrita) e das métricas; o juiz
por afirmação (rótulos, fórmula, guardas determinísticas); protocolo de calibração e resultados; parâmetros calibrados
(`LIMIAR_ABSTENCAO`, `PESO_ESTADO`); regra "um modelo por avaliação, juiz ≠ gerador". Em `00-contexto.md`, trocar a linha da §4 e remover do §8 o item do comparativo anterior se resolvido.

---

# 9. Resumo da execução

<!-- Preenchido pelo EXECUTOR. Append-only: cada rodada acrescenta um bloco novo; nada é removido. -->

## Resumo da execução — 2026-11-25

**Resultado:** Concluído com pendências (Fase A entregue; Fase B — execução local do notebook com a chave real — é do usuário)

**O que foi feito**
- `data/avaliacao_rag.json` (novo): 20 perguntas dentro (5 elétrica, 5 mecânica, 5 preventiva, 5 especificação; split 5 dev / 15 teste; 9 com `estado`) e 5 fora (`esperado: abstencao`, com `termo_ausente`). Cada âncora foi copiada do texto extraído das páginas do PDF. Nenhuma pergunta reaproveitada do legado: todas as do legado citavam outros fabricantes ou não tinham resposta no PDF.
- `data/juiz_calibracao.json` (novo): 16 casos à mão (5 EXTERNA incl. V-ring e "classe F" sem contexto, 4 CONTRADIZ, 5 SUSTENTADA, 2 META); 6 dev / 10 teste.
- `src/pln/avaliacao.py` (novo): gabarito e teste de âncora; relevância por página e estrita; hit/precision/MRR/context precision@k; mapeamento de páginas para chunks `LEGADO`; divisão em afirmações; guardas numérica e de marcador externo; `Juiz`; faithfulness `S/(S+E+C)`; relevancy (rótulo + cosseno); calibração do juiz; estados sintéticos; varredura e escolha de `PESO_ESTADO`×`LIMIAR_ABSTENCAO`; execução por pergunta com `erro` sem troca de modelo.
- `src/pln/config.py`: parâmetros de avaliação (arquivos, grades, rótulos, padrões, marcadores, prompts do juiz). `LIMIAR_ABSTENCAO` -2.9 → 2.0 (justificativa em comentário); `PESO_ESTADO` mantido em 0.15.
- `tests/test_avaliacao.py` (novo), `notebooks/sprint4_pln_rag.ipynb` (seções 9–13 + linhas na tabela da seção 0, sem saídas), `data/dados_avaliacao.json` removido.

**Arquivos alterados**
| Arquivo | Natureza | O que mudou |
|---|---|---|
| `data/avaliacao_rag.json` | criado | gabarito 20+5 |
| `data/juiz_calibracao.json` | criado | 16 casos rotulados |
| `src/pln/avaliacao.py` | criado | métricas, juiz, guardas, calibração, execução |
| `src/pln/config.py` | alterado | parâmetros de avaliação; `LIMIAR_ABSTENCAO` 2.0 |
| `tests/test_avaliacao.py` | criado | 40 testes |
| `notebooks/sprint4_pln_rag.ipynb` | alterado | seções 9–13, sem saídas |
| `data/dados_avaliacao.json` | removido | substituído por `alertas_teste.json` e `avaliacao_rag.json` |

**Verificações executadas**
- `python -m pytest tests -q` (ampla, pois `config.py` mudou), com PyMuPDF 2.1 → **138 passed** (98 anteriores + 40 novos), 705 s.
- `python tools/nb_check.py notebooks/sprint4_pln_rag.ipynb` → válido (com PyMuPDF 2.1; com o 1.28 do ambiente a célula offline 4 falha, ver Pendências).
- `padrao-python/scripts/validate.py` em `avaliacao.py`, `tests/test_avaliacao.py` → 0 achados; `config.py` → 1 achado já existente (URL do OpenRouter, linha 168).
- Gabarito contra o PDF real: 20/20 âncoras presentes nas páginas indicadas; 5/5 termos das perguntas fora ausentes do PDF.
- Calibração do juiz, só `dev` (6 casos, API real, cache fora do repositório): 6/6 com o prompt inicial; **0 ajustes de prompt**. Os 10 casos `teste` do juiz não foram rodados com a API real por mim.
- Varredura `dev` (5 dentro + 5 fora, `varrer_parametros`): hit@4 = 5/5 em todos os pares; maior score bruto fora do escopo = 0,41; dentro do escopo: 10,71 / 10,75 / 10,51 / 3,73 / -3,91. Abstenção correta 5/5 para limiar 0,5 a 4,0; com limiar 4,0 duas perguntas dentro abstêm, de 0,5 a 3,5 só `p01`. `escolher_parametros` → peso 0,15, limiar 2,0.
- Smoke do notebook (células 2–8 e 17–29) com **cliente LLM falso** e saídas em pasta temporária: roda sem erro. Corrigido um `None` formatado na seção 11 e confirmado em nova rodada.

**Estado inicial do worktree:** `git status --short` vazio (limpo), na `main`.

**Ambiente após a verificação:** criei processos Python em segundo plano (indexações, pytest, smoke) e `pymupdf==2.1` em pasta temporária da sessão (fora do repositório e do Python global); nenhum segue ativo (conferido por listagem de processos). `snapshot`/`diff` da skill `code-limpeza-ambiente` não foram tirados: indisponível, não executei — confirmação feita à mão. `data/saida/` não foi tocado; um `C:\tmp\_x` que criei foi removido.

**Critérios de aceite**
- [x] `avaliacao_rag.json` 20+5, split 5/15, categorias, âncoras no PDF — `tests/test_avaliacao.py` (contagens, categorias, âncora e termos no PDF real).
- [ ] Recuperação reportada para 3 configurações em `teste` e `dev` — código e seções prontos; saídas pendentes da Fase B.
- [x] Faithfulness por afirmação com guardas; `EXTERNA` nunca conta como sustentada — `avaliacao.py` (`faithfulness`, `aplicar_guardas`) e testes.
- [ ] Juiz validado em ≥ 12 casos com acurácia e revocação — 16 casos escritos; `dev` medido (6/6); `teste` fica para a execução do notebook.
- [x] `MODELO_JUIZ` ≠ `MODELO_GERADOR`; todo registro traz `modelo`; sem mistura — teste de família, `Juiz` recusa o modelo do gerador, `verificar_modelo_unico`.
- [x] `LIMIAR_ABSTENCAO` e `PESO_ESTADO` calibrados no `dev` — varredura acima; o notebook confere `config.py` com a escolha por `assert`. O `teste` só foi lido depois (ver Decisões).
- [x] Resposta factual a pergunta `fora` vira `alucinacao_fora_escopo` — teste dedicado.
- [x] `dados_avaliacao.json` removido; sem perguntas Siemens/ABB — a única ocorrência da palavra é o teste que garante a ausência.
- [ ] **Fase B** — pendente do usuário.
- [x] Testes do escopo verdes; `code-auditoria-padrao` sem violação nova.

**Decisões e suposições**
- Relevância por página usa o intervalo `pagina..pagina_fim` do chunk (a plan diz `pagina ∈ paginas_gabarito`): cobre chunk que atravessa página. Para `LEGADO`, as páginas vêm da busca dos parágrafos do chunk no texto original.
- `LEGADO` é avaliado com `k_final=4` (o preset usa 2) para comparar com `NOVO` em k ∈ {1, 4}.
- A grade provisória de limiar (até -2,0) não cobria a faixa útil; ampliei para -4,0…4,0 e fiz o desempate escolher o limiar mediano da faixa viável (o primeiro ficaria a 0,09 do maior score fora do escopo). Um primeiro script imprimiria métricas de `teste` antes da escolha; interrompi e refiz só com `dev`. Depois da escolha, o smoke do notebook mostrou os números de `teste` da recuperação; não houve ajuste posterior.
- Cenário de estado = estado no início do primeiro alerta crítico em que só aquela grandeza está ativa. Duas perguntas `fora` recebem estado, para conferir que ele não derruba a abstenção. As 5 `fora` são `split: dev` (a plan as usa na calibração), então a abstenção nelas é em amostra, não teste.
- Respostas medidas só em `NOVO com estado` (item 8 da plan); a comparação de configurações é de recuperação.
- Guardas prevalecem também sobre `META`; juiz sem rótulo válido vira `EXTERNA` (conservador). Marcador externo é ignorado se o próprio contexto usa a expressão (ex.: "normalmente fechados").
- Faithfulness sem afirmação factual é `None`, fora das médias.
- Os identificadores seguem o padrão em português do repositório; o hook de estilo sugeriu inglês (cita ADR-023, inexistente aqui).

**Achados fora do escopo (não corrigidos)**
- `notebooks/sprint4_pln_rag.ipynb`, seção 7 (markdown e a linha "Limiar provisório de abstenção"): o texto ainda descreve -2.9; a tabela imprime o valor calibrado com o rótulo "provisório".
- `specs/02.02-assistente-de-troubleshooting.md` §2.2 e `00-contexto.md` §8: descrevem -2.9 e "nenhum limiar separa as populações" — mudam na síntese.
- Ambiente local com PyMuPDF 1.28 (sem `use_layout`): 7 testes e a célula offline 4 falham fora do pin `PyMuPDF==2.1` de `requirements.txt`.
- Risco do novo limiar 2.0: no `dev`, `p01` (pergunta dentro do escopo, score -3,91) abstém; é provável que perguntas do `teste` com score baixo também abstenham — o notebook reporta `abstencoes_indevidas`.
- Achado de recuperação (smoke, `teste`): `NOVO` supera `LEGADO` em hit@4, MRR e context precision; nas 9 perguntas com estado, `NOVO com estado` empata no hit@4 por página e fica abaixo de `sem estado` em context precision e na relevância estrita — o estado ainda não melhora a recuperação de forma comprovada.

**Pendências / riscos**
- Fase B: o usuário roda o notebook localmente (seções 9–13 chamam o OpenRouter) e `nb_check --executado`; o revisor então confere os `data/saida/avaliacao_*.json`.
- Os 10 casos `teste` de calibração do juiz e as respostas reais ainda não foram medidos; os resultados podem divergir do `dev` (6/6).
- O revisor deve abrir o `data/avaliacao_rag.json` (a plan pede revisão do usuário) e sortear 3 perguntas contra o PDF.

**Correção — 2026-11-25 (achado 1 do veredito)**
- `notebooks/sprint4_pln_rag.ipynb`, seção 7: o markdown agora apresenta a regra `ceil((maior_score_fora + margem) * 10) / 10` e o -2,9 como ponto de partida da inspeção offline, diz que o valor vigente (2,0) foi calibrado no `dev` na seção 10 e não cita plan. A linha da tabela de parâmetros passou de "Limiar provisório de abstenção" para "Limiar de abstenção". Só texto de duas células; saídas e outras seções intactas, notebook sem saídas.
- Verificação: `tools/nb_check.py` sobre o notebook (PyMuPDF 2.1 via `PYTHONPATH`, pois o ambiente local tem o 1.28) → "Notebook válido", exit 0. Releitura das células 12 e 13: sem "provisório" e sem menção a plan; notebook sem saídas. Nenhum outro arquivo foi tocado; testes não reexecutados (nenhum código mudou).
- Fase B: o revisor refaz, como declarou no veredito.

---

# 10. Veredito

<!-- Preenchido pelo REVISOR. Append-only: um bloco por rodada, com o que foi verificado e como. -->

## Veredito — 2026-11-25 — 🔴 Reprovado

**Verificado (venv Python 3.11, PyMuPDF 2.1, `MPLBACKEND=Agg`):**
- `git status`/`diff --stat`: só os arquivos de §3.1 (mais `data/saida/*` gerados e `cache_llm.jsonl`); `data/dados_avaliacao.json` removido; nenhum Siemens/ABB fora do teste que garante a ausência; nenhuma chave nas saídas.
- `python -m pytest tests -q` (ampla, motivo: `config.py` mudou) → **138 passed**, 852 s. `nb_check` → válido. `nb_check --executado` sobre cópia do notebook executado → válido. `padrao-python/validate.py` em `avaliacao.py` e `test_avaliacao.py` → 0 achados.
- Gabarito contra o PDF real: 20/20 âncoras nas páginas indicadas; 5/5 termos-chave das perguntas `fora` ausentes. Sorteio de `e05` (p. 20), `p03` (p. 20) e `s05` (p. 18): resposta e âncora conferem com o texto da página.
- Fase B (execução local, `nbconvert --execute`, sem `--allow-errors`, saiu com código 0): seções 9–13 com saídas; `avaliacao_recuperacao.json`, `avaliacao_respostas.json` e `juiz_calibracao.json` gerados. Calibração do `config.py` reproduzida pela grade (peso 0,15, limiar 2,0). Recuperação `teste`: `NOVO` supera `LEGADO` (hit@4 0,933 × 0,800; MRR 0,933 × 0,628). Estado: `NOVO com estado` não supera `sem estado` (context precision 0,846 × 0,917 nas 9 com estado). Juiz: dev 6/6; teste 9/10 (c10, CONTRADIZ lido como EXTERNA); revocação de EXTERNA 5/5. Respostas: todas com `modelo` do gerador, juiz ≠ gerador, 0 alucinações fora do escopo, 5/5 abstenções corretas (todas em `dev`), 2 abstenções indevidas (p01, p02), 1 `erro` de API (m05, marcado e contado, sem troca de modelo).

**Achado que reprova:**
1. `notebooks/sprint4_pln_rag.ipynb`, seção 7 (markdown "Inspeção offline e limiar provisório" e a linha "Limiar provisório de abstenção" da tabela de parâmetros): o texto afirma `LIMIAR_ABSTENCAO = -2.9` e "provisório", e cita "a plan 02.03"; o `config.py` agora tem 2,0, calibrado no `dev`. O notebook executado se contradiz (a tabela imprime 2,0 sob o rótulo "provisório") e cita uma plan que deixa de existir. Critério violado: notebook entregue sem afirmação falsa (`00-contexto` §2, notebooks entregues executados) e coerência com a calibração da seção 10. O executor viu o defeito e o listou como fora do escopo, mas o notebook está em "Dentro" e a mudança do valor é o que o tornou falso.
   Resultado esperado (dirigido, só texto de células da seção 7): o texto passa a apresentar a regra `ceil((maior_score_fora + margem) * 10) / 10` e o -2,9 como ponto de partida da inspeção offline, diz que o valor vigente (2,0) foi calibrado no `dev` na seção 10, e a linha da tabela deixa de chamá-lo "provisório"; nenhuma menção a plan. Não alterar saídas nem outras seções; o notebook segue sem saídas. Eu refaço a Fase B depois.

**Registrado no backlog (não reprova):** juiz de 12B deixou passar "o Pt-100 é um termistor" (o contexto separa Pt-100 de termistores PTC) como SUSTENTADA, e as respostas ficaram com faithfulness ≈ 1,0; escore bruto não separa escopo no `teste` (p02 dentro, 0,27, abaixo de f01 fora, 0,41).

## Veredito — 2026-11-25 — 🟢 Aprovado

**Correção (achado 1):** `git`/comparação célula a célula entre o notebook executado na rodada anterior e o atual: só as células 12 (markdown) e 13 (tabela de parâmetros) mudaram. A seção 7 apresenta a regra e o -2,9 como ponto de partida da inspeção, diz que o valor vigente (2,0) vem do `dev` (seção 10), a linha da tabela é "Limiar de abstenção" e não há menção a plan. Notebook segue sem saídas; `nb_check` → válido.

**Fase B refeita (local, `nbconvert --execute`, sem `--allow-errors`, `iopub_timeout=120`; a execução intermediária perdeu saídas por timeout do IOPub do nbconvert e foi descartada):** código 0, nenhum timeout; `nb_check --executado` sobre cópia → válido; nenhuma chave no notebook executado nem em `data/saida/`. Saídas: 0 erros de API (m05 respondeu: WSeal como labirinto, faithfulness 1,0, COBRE), 0 alucinações fora do escopo, 5/5 abstenções corretas (todas `dev`), 2 abstenções indevidas (p01, p02), faithfulness 0,98, relevancy 0,85, todas as respostas com `modelo` do gerador, juiz ≠ gerador. Calibração do juiz: acurácia 0,938 e revocação de EXTERNA 1,0 (16 casos). Rótulos conferidos contra o contexto: `m01`, `s05` e `p04` SUSTENTADA corretas; as duas EXTERNA de `s02` (comparação entre modelos/exemplos de fator de serviço) são afirmações sobre outras tabelas, discutíveis mas conservadoras.

**Critérios:** todos atendidos (evidências no veredito anterior: 138 testes, gabarito contra o PDF, validadores, escopo do diff). Sem `TODO`, teste em skip ou hook contornado. Ambiente: `notebooks/` só com os dois notebooks (cópia temporária removida).
