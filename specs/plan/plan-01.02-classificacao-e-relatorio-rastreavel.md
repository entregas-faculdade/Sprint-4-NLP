---
tipo: "plan"
familia: "01"
item: "R01.2"
titulo: "Classificar eventos em 5 categorias e gerar relatório rastreável"
dominio: "Sprint 3 — Alertas e classificação"
status: "🔴 A executar"
prioridade: "Alta"
tags: ["plan", "sprint-3", "classificacao", "relatorio", "F1", "F2"]
relacionados: ["[[00-contexto]]", "[[plan-01.01-alertas-deterministicos-e-fieis]]"]
depende_de: "plan-01.01-alertas-deterministicos-e-fieis"
destino_sintese: "specs/01.02-classificacao-e-relatorio.md + 00-contexto.md"
---

# 1. Objetivo

O notebook da Sprint 3 classifica **60 eventos** nas **5 categorias** com F1 por categoria (zero-shot por LLM comparado a uma linha de
base por regras) e gera relatórios diário e semanal em que **cada frase aponta o alerta e as leituras de origem**, sem acrescentar
informação (requisitos **F1** e **F2**).

# 2. Contexto

- Feedback: "a avaliação do classificador precisa abranger as cinco categorias, com exemplos além dos três alertas atuais" e o
  relatório "acrescenta limites, diagnósticos e prognósticos que não estão nos dados". Antes, só 3 alertas foram classificados, então
  categorias ficaram sem suporte no F1.
- Categorias (enunciado): `manutenção corretiva`, `manutenção preventiva`, `anomalia elétrica`, `anomalia mecânica`, `operação normal`.
- Esta plan usa o que a plan 01.01 sintetizou em `specs/01.01-alertas-deterministicos.md`: contrato `Alerta`, `config.py`, `llm.py`
  (cliente com cache e sem fallback), `verificar_texto`, `tools/nb_check.py`. **Ler a spec antes de editar.**
- Decisão do dono: o conjunto de eventos é **sintético, derivado dos dados**, e **o usuário revisa os rótulos** (passo 3).

# 3. Escopo

## 3.1 Dentro
- `data/eventos_rotulados.json` — **novo**: 60 eventos (12 por categoria)
- `data/relatorio_referencia.json` — **novo**: relatório de referência manual, diário e semanal
- `src/pln/classificacao.py` — classificador zero-shot, linha de base por regras, métricas
- `src/pln/relatorio.py` — agregação determinística, texto, referências, verificador de relatório
- `src/pln/config.py` — acrescentar constantes novas (categorias, janelas de relatório, termos); sem mudar as existentes
- `tests/test_classificacao.py` · `tests/test_relatorio.py`
- `notebooks/sprint3_pln_alertas.ipynb` — acrescentar seções 9 a 14
- `data/saida/` — `classificacao.json`, `relatorio_diario.json`, `relatorio_semanal.json`

## 3.2 Fora
- Regras de severidade, templates de alerta, `verificar_texto` (da plan 01.01): só consumir; achado vira backlog
- `notebooks/sprint4_pln_rag.ipynb`, `docs/` (PDF), `specs/`, os 3 JSON de dados de origem

# 4. Referências obrigatórias

| Tipo | Referência | Por quê |
|---|---|---|
| Spec fixa | `specs/01.01-alertas-deterministicos.md` | contrato `Alerta`, verificador, LLM sob verificador |
| Contexto | `00-contexto.md` · `00-knowledge.md` | regras inegociáveis |
| Requisito | `docs/feedback-professor.md` · `enunciado-4.txt` | F1, F2 e a descrição do relatório |
| **Skill** | `padrao-escrita` + `padrao-python` · `test-unitario` · `code-auditoria-padrao` | escrita, testes, gate |
| Código | `src/pln/alertas.py` · `src/pln/llm.py` · `src/pln/config.py` · `tools/nb_check.py` | reaproveitar, não reescrever |
| Dados | `data/saida/alertas.json` (se existir) · `data/dados-w22.csv` | origem dos eventos e do relatório |

# 5. Instruções de execução

1. [dirigido] **Eventos rotulados.** Gerar `data/eventos_rotulados.json` com 60 eventos: `id`, `timestamp`, `ativo`, `texto` (registro
   em português livre, como uma ocorrência de operador, ordem de serviço ou log), `rotulo` (uma das 5), `split` (`dev` ou `teste`),
   `origem` (`derivado_de_alerta` ou `sintetico`). 12 por categoria; em cada categoria 2 `dev` e 10 `teste`. Regras: (a) ≥ 6 eventos
   vêm de alertas reais da plan 01.01 (ex.: episódio crítico de vibração → anomalia mecânica; de corrente → anomalia elétrica);
   (b) variar a redação (não repetir a mesma moldura); (c) ≥ 20 % **casos difíceis** — texto de manutenção preventiva que cita
   vibração/temperatura, corretiva posterior a anomalia, operação normal com leitura próxima do nominal; (d) nenhuma palavra-rótulo
   óbvia em todos os exemplos de uma classe. Sem dados pessoais.
2. [dirigido] **Linha de base por regras** em `classificacao.py`: léxico por categoria em `config.py`, escrito **olhando só o `dev`**.
   **Classificador zero-shot**: prompt com as 5 categorias e a definição de cada uma (critérios em `config.py`), resposta restrita a um
   rótulo, validada por correspondência exata; resposta inválida → 1 retentativa → `indeterminado` (conta como erro). `MODELO_CLASSIFICADOR`,
   temperatura 0, cache. Prompt ajustado **só com o `dev`**; o `teste` roda uma vez no fim.
3. [dirigido] **Revisão pelo usuário.** O executor para e **lista no resumo** o caminho de `eventos_rotulados.json` e pede a revisão dos
   rótulos. Sem confirmação do usuário a plan não segue para a Fase B (nada a bloquear no código).
4. [dirigido] **Métricas** em `classificacao.py`: `classification_report` por categoria (precisão, revocação, F1, suporte) e macro/ponderado,
   matriz de confusão, para linha de base e zero-shot, sobre os 50 eventos `teste` (`labels` explícitos das 5 categorias, `zero_division=0`);
   os dois lado a lado; listar os erros do zero-shot (texto, esperado, obtido).
5. [dirigido] **Relatório determinístico** em `relatorio.py`: `gerar_relatorio(alertas, periodo, leituras)` produz seções fixas —
   **Resumo** (n de alertas por severidade), **Alertas emitidos** (os mais severos, com id), **Sensores em risco** (sensor cujo pior
   alerta no período é moderado/crítico; severidade geral do ativo = a maior), **Tendências** (por sensor: média da 1ª metade vs 2ª do
   período; só variação numérica `+X unid (Y %)` ou "estável" se |Y| < limiar em `config.py`; **proibido** extrapolar), **Ações padrão**
   (a mesma tabela da plan 01.01, rotulada "ação padrão; não é diagnóstico"). **Toda frase termina com referência** no formato
   `[ref: A-0012 | ids: <id1>,<id2>… ]` (alerta e leituras CSV) ou `[ref: período | sensor <id>]` para agregados. Janelas: **diário** =
   último dia com dados do CSV; **semanal** = 7 dias terminando nele.
6. [dirigido] **Verificador de relatório** `verificar_relatorio(texto, alertas, leituras)`: reprova frase sem `[ref:]`, referência que
   não resolve (alerta ou `id` de leitura inexistente), número fora do conjunto permitido, termo de `TERMOS_PROIBIDOS` (da plan 01.01).
   Opcional: reescrita por LLM por seção (`MODELO_REDATOR`) com as mesmas garantias da plan 01.01 (reprovou → texto determinístico).
7. [dirigido] **Referência manual** `data/relatorio_referencia.json`: um relatório diário e um semanal escritos à mão (por você, executor,
   a partir dos **números calculados**), em português fluido, mesma estrutura de seções, **sem os marcadores `[ref:]`** (para o ROUGE
   medir conteúdo). O usuário revisa junto com os rótulos.
8. [dirigido] **Avaliação do relatório:** ROUGE-1/2/L (tokenizador `\w+` da plan 01.01) do relatório determinístico e do reescrito contra
   a referência, para diário e semanal; **checklist** binário por relatório: **precisão** (`verificar_relatorio` vazio), **clareza** (seções
   presentes, frases ≤ 30 palavras), **utilidade** (cada sensor em risco tem ação padrão) e **rastreabilidade** (100 % das frases com
   `[ref:]` resolvida).
9. [dirigido] Testes (skill `test-unitario`): eventos — 12 por classe, split 2/10, rótulos válidos, ≥ 6 derivados de alerta; métricas
   com predições fabricadas (F1 conhecido); classificador com LLM falso (rótulo inválido → retry → `indeterminado`); relatório —
   frase sem referência reprovada, referência inexistente reprovada, número inventado reprovado, tendência só numérica, janelas
   diária/semanal corretas; texto determinístico passa no próprio verificador.
10. [dirigido] Acrescentar ao notebook (sem saídas; tag `offline` na lógica pura): **9** Conjunto de eventos (contagem por classe e
    split, 5 exemplos) · **10** Classificação: linha de base × zero-shot, F1 por categoria (tabela + matriz de confusão) e análise
    dos erros · **11** Relatório diário (texto com referências) · **12** Relatório semanal · **13** Avaliação: ROUGE e checklist ·
    **14** Exportar `data/saida/` e Conclusão com os números. Rodar pytest, `nb_check` e `code-auditoria-padrao`.

# 6. Critérios de aceite

- [ ] `eventos_rotulados.json` tem 60 eventos, 12 por categoria, split 2 `dev` + 10 `teste` por categoria, ≥ 6 `derivado_de_alerta`.
- [ ] F1 reportado **por categoria, nas 5**, com suporte 10 cada, para linha de base e zero-shot; matriz de confusão e lista de erros.
- [ ] Ajuste de léxico/prompt usou só o `dev` (verificável pela ordem das células e pelo comentário na seção 10).
- [ ] Relatório diário e semanal: 100 % das frases com referência que resolve; nenhum número fora do conjunto permitido; nenhum termo proibido.
- [ ] Tendências só descrevem variação numérica; nenhuma frase prevê ou explica causa.
- [ ] ROUGE-1/2/L e checklist (precisão, clareza, utilidade, rastreabilidade) reportados para os dois relatórios.
- [ ] **Fase B:** notebook executado no Colab sem erro, com as seções 9–14 e `data/saida/classificacao.json` e relatórios presentes;
      `nb_check --executado` verde.
- [ ] Rótulos e referência manual **confirmados pelo usuário**.
- [ ] Ambiente e worktree limpos; testes do escopo verdes; `code-auditoria-padrao` sem violação nova.

# 7. Como verificar (uso do revisor)

- **Nível:** `escopada`.
- `git diff --stat` → só os arquivos de §3.1.
- **Fase A:** `python -m pytest tests/test_classificacao.py tests/test_relatorio.py -q` · `python tools/nb_check.py notebooks/sprint3_pln_alertas.ipynb`
  · `code-auditoria-padrao`.
- `python -X utf8 - <<'E'` contando por `rotulo` e `split` em `data/eventos_rotulados.json` → 12/classe, 2+10.
- Leitura de `src/pln/classificacao.py` → o léxico não contém trechos copiados de eventos `teste`.
- **Fase B:** `python tools/nb_check.py notebooks/sprint3_pln_alertas.ipynb --executado` · leitura das saídas das seções 10, 11, 12 e 13.
- **Gate:** `nenhum`.

# 8. Destino da síntese

**Destino:** `specs/01.02-classificacao-e-relatorio.md` + `00-contexto.md`

Texto para transporte: critérios de cada categoria; composição do conjunto de eventos (60, 12/classe, 2 dev/10 teste, casos difíceis);
protocolo (ajuste só no `dev`); resultados de F1 por categoria (linha de base × zero-shot); estrutura do relatório, formato de
referência `[ref: ...]` e regras do verificador; critérios do checklist; janelas diária e semanal. Em `00-contexto.md`, trocar a linha da §4.

---

# 9. Resumo da execução

<!-- Preenchido pelo EXECUTOR. Append-only: cada rodada acrescenta um bloco novo; nada é removido. -->

---

# 10. Veredito

<!-- Preenchido pelo REVISOR. Append-only: um bloco por rodada, com o que foi verificado e como. -->
