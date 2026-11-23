---
tipo: "plan"
familia: "02"
item: "R02.2"
titulo: "Construir o assistente de troubleshooting com citação, confiança calculada e abstenção"
dominio: "Sprint 4 — RAG e assistente"
status: "🔴 A executar"
prioridade: "Alta"
tags: ["plan", "sprint-4", "assistente", "F3", "F4", "F6"]
relacionados: ["[[00-contexto]]", "[[plan-02.01-rag-com-pagina-secao-e-estado]]"]
depende_de: "plan-02.01-rag-com-pagina-secao-e-estado"
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
- Usa `Retriever` e `EstadoOperacional` (plan 02.01) e `llm.py` (plan 01.01; `MODELO_GERADOR`).

# 3. Escopo

## 3.1 Dentro
- `src/pln/assistente.py` — `Assistente`, prompt de sistema, memória, citação, confiança, abstenção
- `src/pln/config.py` — acrescentar: `MEMORIA_TURNOS`, `LIMIAR_ABSTENCAO`, faixas de confiança, frase de abstenção, marcadores
- `tests/test_assistente.py`
- `notebooks/sprint4_pln_rag.ipynb` — acrescentar seções 7 e 8

## 3.2 Fora
- Métricas, gabarito, juiz e calibração final de `LIMIAR_ABSTENCAO` — plan 02.03 (aqui vale um valor **provisório** documentado)
- Cenários de demonstração — plan 02.04
- `rag.py`, `estado.py`, `alertas.py`: só consumir

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
2. [dirigido] **Montagem do prompt** em `assistente.py`: mensagens `system` + histórico (`MEMORIA_TURNOS`, padrão 3, em papéis
   `user`/`assistant`) + `user` com os blocos `ESTADO OPERACIONAL` (de `EstadoOperacional.texto()`), `CONTEXTO DO MANUAL` (cada chunk
   rotulado com `[p. N, seç. X]`) e `PERGUNTA`.
3. [dirigido] **Consulta de recuperação com memória, sem LLM:** se a pergunta for curta (< 6 palavras) ou contiver anáfora
   (`desse`, `dessa`, `isso`, `ele`, `ela`, `nesse`, `neste`…), a consulta de busca = pergunta anterior do usuário + pergunta atual;
   caso contrário, só a atual. O estado vai ao retriever (`estado=`).
4. [dirigido] **Abstenção determinística:** se `score_rerank` do melhor chunk < `LIMIAR_ABSTENCAO`, devolver a frase de abstenção
   **sem chamar o LLM** (`abstencao=True`, `fontes=[]`). O limiar é parâmetro; valor provisório definido por inspeção de ≥ 6 consultas
   (3 dentro e 3 fora do escopo) e registrado no notebook; a plan 02.03 o calibra.
5. [dirigido] **Confiança calculada** (`Alta`/`Média`/`Baixa`) por faixas do `score_rerank` do melhor chunk e do nº de chunks acima do
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

- [ ] Perguntas fora do escopo recebem a frase de abstenção **sem chamada ao LLM** (teste).
- [ ] A linha `Confiança:` final é sempre a calculada; nunca a autodeclarada.
- [ ] Toda resposta traz fontes no formato `[p., seç.]` resolvidas; citação inexistente é sinalizada (`citacao_invalida`).
- [ ] A pergunta de seguimento recupera pelo assunto anterior (teste e demonstração).
- [ ] O estado operacional entra na recuperação **e** no prompt, marcado como dado confiável.
- [ ] Nenhum id de modelo, limiar ou frase fixa fora de `config.py`.
- [ ] **Fase B:** seção 8 executada no Colab sem erro, com os 3 tipos de pergunta e `modelo` registrado em cada resposta.
- [ ] Ambiente e worktree limpos; testes do escopo verdes; `code-auditoria-padrao` sem violação nova.

# 7. Como verificar (uso do revisor)

- **Nível:** `escopada`.
- `git diff --stat` → só os arquivos de §3.1.
- **Fase A:** `python -m pytest tests/test_assistente.py -q` · `python tools/nb_check.py notebooks/sprint4_pln_rag.ipynb` · `code-auditoria-padrao`.
- Leitura de `src/pln/assistente.py` → o caminho de abstenção retorna antes de qualquer chamada de rede; a linha `Confiança:` é reescrita.
- **Fase B:** `python tools/nb_check.py notebooks/sprint4_pln_rag.ipynb --executado` · leitura da saída da seção 8.
- **Gate:** `nenhum`.

# 8. Destino da síntese

**Destino:** `specs/02.02-assistente-de-troubleshooting.md` + `00-contexto.md`

Texto para transporte: o prompt de sistema e suas regras; contrato de `Resposta`; regras de abstenção, confiança (faixas) e citação;
política de memória (3 turnos, consulta de seguimento); tratamento do estado como dado confiável. Em `00-contexto.md`, trocar a linha da §4.

---

# 9. Resumo da execução

<!-- Preenchido pelo EXECUTOR. Append-only: cada rodada acrescenta um bloco novo; nada é removido. -->

---

# 10. Veredito

<!-- Preenchido pelo REVISOR. Append-only: um bloco por rodada, com o que foi verificado e como. -->
