---
tipo: "plan"
familia: "02"
item: "R02.3"
titulo: "Avaliar o RAG com gabarito de página e juiz por afirmação"
dominio: "Sprint 4 — RAG e assistente"
status: "🔴 A executar"
prioridade: "Alta"
tags: ["plan", "sprint-4", "avaliacao", "F5", "F6"]
relacionados: ["[[00-contexto]]", "[[plan-02.02-assistente-de-troubleshooting]]"]
depende_de: "plan-02.02-assistente-de-troubleshooting"
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
- [ ] **Fase B:** notebook executado no Colab sem erro, seções 9–13 com saídas e `data/saida/avaliacao_*.json` presentes; `nb_check --executado` verde.
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

---

# 10. Veredito

<!-- Preenchido pelo REVISOR. Append-only: um bloco por rodada, com o que foi verificado e como. -->
