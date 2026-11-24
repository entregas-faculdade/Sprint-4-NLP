---
tipo: "plan"
familia: "01"
item: "R01.2"
titulo: "Classificar eventos em 5 categorias e gerar relatório rastreável"
dominio: "Sprint 3 — Alertas e classificação"
status: "🟢 Aprovada"
prioridade: "Alta"
tags: ["plan", "sprint-3", "classificacao", "relatorio", "F1", "F2"]
relacionados: ["[[00-contexto]]", "[[01.01-alertas-deterministicos]]"]
depende_de: ""
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
   último dia do CSV com ao menos um alerta (o último dia com dados não tem alerta); **semanal** = 7 dias terminando nele.
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

## Execução — 2026-11-24

**Resultado:** Fase A implementada e aguardando revisão humana dos rótulos e das referências manuais. A Fase B permanece pendente conforme o gate definido pelo prompt executor.

### Entregue

- `data/eventos_rotulados.json`: 60 eventos, 12 em cada uma das cinco categorias, com 2 `dev` + 10 `teste` por categoria; 54 sintéticos e 6 derivados de alertas existentes. Os IDs derivados foram conferidos contra `data/alertas.json`.
- `src/pln/classificacao.py`: validação do contrato do conjunto de dados, baseline lexical derivada apenas do split `dev`, classificador zero-shot com rótulos fechados e avaliação das cinco classes (precisão, recall, F1, suporte, macro/ponderada, matriz de confusão e erros). A avaliação está restrita ao split `teste`.
- `data/relatorio_referencia.json` e `src/pln/relatorio.py`: referências diária e semanal, geração determinística, resolução das referências de alertas/leituras, validação dos números e termos proibidos, descrição numérica de tendências e checklist de avaliação.
- `notebooks/sprint3_pln_alertas.ipynb`: seções 9–14 adicionadas. As saídas e contagens de execução foram limpas; as células de Colab não foram executadas.
- `tests/test_classificacao.py` e `tests/test_relatorio.py`: 15 testes de escopo.

### Verificações

- `pytest tests/test_classificacao.py tests/test_relatorio.py -q`: **15 passaram**; permaneceu 1 `PytestCacheWarning` porque o acesso ao `.pytest_cache` foi negado pelo ambiente.
- `tools/nb_check.py notebooks/sprint3_pln_alertas.ipynb` com `MPLBACKEND=Agg`: **Notebook válido**.
- Auditoria estática Sarak: sem achados nos módulos e testes novos; em `src/pln/config.py`, o validador sinalizou com baixa confiança a constante preexistente `URL_OPENROUTER` (aprox. linha 90), mantida sem alteração por estar fora do escopo.
- Contrato do conjunto: 60 eventos; 12 por classe; 2 `dev` + 10 `teste` por classe; 54 sintéticos + 6 derivados.
- Relatório diário: ROUGE-1 **0,2333**, ROUGE-2 **0,1343**, ROUGE-L **0,2127**; checklist completo; 0 violações do verificador; rastreabilidade **100%**.
- Relatório semanal: ROUGE-1 **0,4505**, ROUGE-2 **0,2979**, ROUGE-L **0,3656**; checklist completo; 0 violações do verificador; rastreabilidade **100%**.

### Critérios ainda pendentes

- Os rótulos do conjunto e o relatório de referência ainda precisam de confirmação do usuário.
- A execução zero-shot não foi chamada antes dessa confirmação. Portanto, F1 por categoria para baseline e LLM ainda não foi produzido.
- A Fase B em Colab não foi executada; `data/saida/classificacao.json` e os relatórios exportados não foram gerados. `nb_check --executado` ainda está pendente.

### Notas da execução

- A spec 01.01 referenciada pelo plano existe no worktree em `specs/specs/01.01-alertas-deterministicos.md`; esse caminho foi usado como destino da referência.
- O léxico da baseline foi formado somente a partir dos exemplos `dev`. As tendências usam comparação numérica entre metades cronológicas das leituras da janela.
- O worktree começou limpo na branch `main`, permitida por `specs/00-contexto.md`. Não houve commit. O venv temporário, a janela Matplotlib aberta pelo verificador e o snapshot temporário foram removidos/fechados.
- O diff do ambiente mostrou variação de processos, containers e cache Docker sem autoria atribuível; nenhum desses recursos foi alterado. O acesso ao ignore global do Git e ao `.pytest_cache` também gerou avisos de permissão.

## Resumo da execução (correção 1) — 2026-11-24

**Resultado:** Concluído com pendências. Os três achados da Fase A foram corrigidos; revisão humana dos rótulos e referência, e Fase B, permanecem pendentes.

**O que foi feito**

1. Corrigi `_period_window` para selecionar no diário a data mais recente que tenha leituras e ao menos um alerta; o semanal continua terminando no último dia com leituras. No CSV, o diário usa 2026-08-22; 2026-08-23 tem 18 leituras e nenhum alerta. Atualizei a referência diária e a explicação nas seções 11 e 13 do notebook.
2. Restrinjo os números permitidos nas referências agregadas às contagens de severidade e tendências calculadas para as janelas diária e semanal. A sonda real `variação -8,17 °C com máxima de 78,29 °C` agora é reprovada com `Número não permitido: 78,29`.
3. Adicionei formas femininas de severidade para as frases com “severidade” nos alertas e sensores em risco: “leve”, “moderada” e “crítica”. Os textos de alerta da plan 01.01 não foram alterados.

**Arquivos alterados nesta correção**

| Arquivo | Natureza | O que mudou |
|---|---|---|
| `src/pln/relatorio.py` | alterado | Janela diária, allowlist numérica agregada e concordância de severidade. |
| `src/pln/config.py` | alterado | Mapa de adjetivos femininos de severidade. |
| `tests/test_relatorio.py` | alterado | Casos de janela diária/semanal, ausência de dia com alerta, número bruto adversarial e concordância. |
| `data/relatorio_referencia.json` | alterado | Apenas a referência diária, refeita sobre 2026-08-22; referência semanal preservada. |
| `notebooks/sprint3_pln_alertas.ipynb` | alterado | Explicação da data diária nas seções 11 e 13; sem saídas de execução. |
| `specs/plan/plan-01.02-classificacao-e-relatorio-rastreavel.md` | alterado | Apenas este bloco novo foi acrescentado à §9; os blocos anteriores e o veredito foram preservados. |

**Verificações executadas**

- Primeira execução de `python -m pytest tests -q`: 55 passaram, 4 erros de setup por acesso negado ao `%TEMP%\pytest-of-Igor` e 1 falha na asserção antiga que esperava o dia sem alertas. Após ajustar o teste à janela definida pelo veredito, `python -m pytest tests -q --basetemp <temporário da tarefa>` → **60 passaram**, 1 `PytestCacheWarning` por permissão no `.pytest_cache`.
- `python tools/nb_check.py notebooks/sprint3_pln_alertas.ipynb` → **Notebook válido**.
- `padrao-python/scripts/validate.py`: `src/pln/relatorio.py` e `tests/test_relatorio.py` sem achados; em `src/pln/config.py`, permaneceu somente o candidato de baixa confiança para a URL preexistente `URL_OPENROUTER` (linha 91).
- Relatórios reais: diário e semanal com 0 violações, checklist completo e 100% de rastreabilidade. Diário: ROUGE-1 **0,4493**, ROUGE-2 **0,2857**, ROUGE-L **0,3502**. Semanal: **0,4528**, **0,2979**, **0,3679**.
- Sonda adversarial sobre o relatório semanal → `Número não permitido: 78,29`.

**Estado inicial do worktree:** branch `main`, autorizada como branch direta por `00-contexto.md`. Já havia alterações dos artefatos da Fase A e do revisor antes desta rodada; preservei `specs/00-indice.md` e `specs/panorama/{00-planejamento,00-resumo}.md`. Não houve commit.

**Ambiente após a verificação:** venv temporário, diretório `--basetemp` e snapshot desta rodada removidos. O diff ambiental mostrou 24 processos surgidos e 19 encerrados, sem autoria atribuível; não alterei processos alheios. Containers e cache Docker não mudaram.

**Critérios de aceite**

- [x] Diário usa o último dia com leituras e alerta; semanal preserva a janela dos sete dias até o último dia com leituras — teste de regressão e relatórios reais.
- [x] Frases agregadas rejeitam valor bruto de outra data — sonda `78,29` reprovada; os dois relatórios gerados seguem sem violações.
- [x] Severidade concorda com o substantivo feminino nos alertas e sensores em risco — testes para os três níveis aplicáveis.
- [ ] Rótulos e referência manual confirmados pelo usuário; execução da Fase B no Colab — ainda aguardam as pendências já registradas.

**Decisões e suposições**

- A data candidata ao diário é a data de início de um alerta que também tenha leituras no CSV. Se nenhum dia satisfizer a condição, o gerador falha explicitamente com `ValueError`.
- Não executei LLM nem Colab nesta correção.

**Achados fora do escopo (não corrigidos)**

- `src/pln/config.py:91` — URL `URL_OPENROUTER` preexistente apontada pelo validador com baixa confiança; fora dos três achados desta rodada.

**Pendências / riscos**

- O primeiro uso do diretório temporário padrão do pytest foi negado pelo ambiente. A suíte passou ao definir um `--basetemp` próprio; permanece o aviso de permissão do `.pytest_cache`.
- A referência diária foi refeita, mas precisa da revisão humana junto com os rótulos antes da Fase B.

## Resumo da execução (correção 2) — 2026-11-24

**Resultado:** Concluído com pendências. As seções 9–14 foram reconstruídas no notebook; a revisão humana dos rótulos e da referência e a Fase B permanecem pendentes.

**O que foi feito**
- Recriei as seções 9–14 em 12 células, alerts-17 a alerts-28: conferência offline dos eventos e cinco exemplos; avaliação da linha de base e zero-shot somente no split teste, com RuntimeError quando openrouter_key_available é falso; relatórios diário e semanal; ROUGE e checklist; exportação dos três JSON solicitados.
- Marquei como offline apenas as células de lógica local e mantive as células zero-shot e de exportação fora dessa tag. Limpei saídas, contagens e metadados de execução das células de código para manter o notebook sem estado de execução da Fase A.
- Não executei o notebook completo, não chamei o zero-shot e não gerei os arquivos exportados.

**Arquivos alterados**
| Arquivo | Natureza | O que mudou |
|---|---|---|
| notebooks/sprint3_pln_alertas.ipynb | alterado | Seções 9–14 reconstruídas; saídas e contagens de execução removidas. |
| specs/plan/plan-01.02-classificacao-e-relatorio-rastreavel.md | alterado | Este bloco novo foi acrescentado ao fim da seção 9; os blocos anteriores e o veredito foram preservados. |

**Verificações executadas**
- python -m pytest tests -q com PYTEST_ADDOPTS apontando para o basetemp dedicado em TEMP: 60 passaram; 1 PytestCacheWarning no cache .pytest_cache (WinError 183: o caminho já existe).
- python tools/nb_check.py notebooks/sprint3_pln_alertas.ipynb, sem --executado: Notebook válido. O verificador processou as células offline; não executou as células zero-shot nem a exportação.
- JSON do notebook válido, 29 células; as 12 novas células passaram pela análise sintática e todas as células de código estão sem saída e sem contagem de execução.

**Estado inicial do worktree:** branch main; git status --short: M notebooks/sprint3_pln_alertas.ipynb; M specs/00-contexto.md; M specs/00-indice.md; M specs/panorama/00-planejamento.md; M specs/panorama/00-resumo.md; M specs/plan/plan-01.02-classificacao-e-relatorio-rastreavel.md; M specs/specs/01.01-alertas-deterministicos.md; M src/pln/config.py; ?? data/eventos_rotulados.json; ?? data/relatorio_referencia.json; ?? src/pln/classificacao.py; ?? src/pln/relatorio.py; ?? tests/test_classificacao.py; ?? tests/test_relatorio.py. As alterações preexistentes fora do notebook e desta plan foram preservadas.

**Ambiente após a verificação:** venv temporário removido; basetemp criado em caminho relativo no workspace foi removido; snapshots temporários removidos. O diff do ambiente não conseguiu consultar processos e indicou Docker indisponível. Quatro entradas temporárias apareceram no diff final sem autoria atribuível; não foram alteradas.

**Critérios de aceite**
- [x] Seções 9–14 restauradas com as funções previstas — células alerts-17 a alerts-28; nb_check válido.
- [x] Eventos, geração dos relatórios e avaliação ROUGE/checklist cobertos pelas células offline — execução offline aprovada por nb_check.
- [x] Zero-shot limitado ao split teste e protegido quando a chave não está disponível — código da célula alerts-20; a chamada não foi executada nesta Fase A.
- [x] Exportação de classificacao.json, relatorio_diario.json e relatorio_semanal.json preparada — célula alerts-28; arquivos não gerados porque a Fase B não foi executada.
- [x] Suíte solicitada aprovada — 60 testes passaram.
- [ ] Revisão humana dos rótulos e da referência e execução da Fase B — pendentes para o revisor conforme instrução.

**Decisões e suposições**
- Preservei as fontes das oito seções existentes; removi somente estado de execução antigo, necessário para o contrato do notebook sem saídas na Fase A.
- Usei a data diária 2026-08-22 porque 2026-08-23 tem 18 leituras e nenhum alerta; a janela semanal termina em 2026-08-23, conforme o plano e a correção anterior.
- O venv e o basetemp temporários foram usados apenas para as verificações solicitadas e removidos ao final.

**Pendências / riscos**
- Os rótulos e a referência manual ainda aguardam confirmação humana; o zero-shot, a execução Colab e os três JSON exportados aguardam a Fase B.
- A suíte passou com o aviso do cache pytest indicado acima. O diff de processos ficou indisponível; não atribuí nem alterei arquivos temporários de autoria incerta.

---

# 10. Veredito

<!-- Preenchido pelo REVISOR. Append-only: um bloco por rodada, com o que foi verificado e como. -->

## Veredito — 2026-11-24 — 🔴 Reprovado (rodada 1, Fase A)

**Escopo da rodada:** Fase A (local). A Fase B (execução do notebook) e a revisão humana dos rótulos e da referência manual continuam pendentes; ainda há defeitos de comportamento que mudariam a execução, então rodar antes gastaria uma passada do zero-shot.

**O que foi verificado e como**
- `git status`: arquivos de §3.1 (os 8 novos/alterados) e nada fora do escopo; sem commit do executor; `__pycache__` ignorado. Resumo × diff: coerente (15 testes novos, ROUGE diário 0,233 / 0,134 / 0,213 e semanal 0,450 / 0,298 / 0,366 reproduzidos por mim).
- `python -m pytest tests -q` → 53 passaram. `python tools/nb_check.py notebooks/sprint3_pln_alertas.ipynb` → válido (sem saídas, tags `offline` nas células de lógica pura).
- Conjunto de eventos: 60 eventos, 12 por categoria, 2 `dev` + 10 `teste` por categoria, 54 sintéticos + 6 derivados; os 6 ids (`A-4463`, `A-4468`, `A-4476`, `A-4470`, `A-4471`, `A-4474`) existem em `data/saida/alertas.json` com valor de pico e `n_leituras` iguais ao texto do evento.
- Léxico (`config.py`): 21 termos, todos presentes em textos `dev`; só "troca" e "lubrificação" aparecem também em um evento `teste`, como termos genéricos já presentes no `dev`; nenhum trecho copiado do `teste`. Protocolo respeitado: a avaliação roda uma vez sobre os 50 eventos `teste` (`avaliar_split_teste`), com o comentário exigido na célula da seção 10.
- Funções ≤ 40 linhas e ≤ 4 parâmetros (verificado por AST nos 4 arquivos novos); sem `TODO`, `skip` nem chave nos arquivos novos.
- Relatórios gerados sobre o CSV real: 0 violações do verificador, rastreabilidade 100 %, checklist verdadeiro nos dois períodos. Sondas adversariais: contagem errada, pico trocado e "provavelmente… desgaste" são reprovados.

**Achados**

1. **O relatório diário não tem conteúdo: o último dia do CSV (2026-08-23) tem 18 leituras e nenhum alerta.** `relatorio.py` (`_period_window`) segue o §5.5 da plan ("último dia com dados do CSV"); o diário sai com 5 sensores "0 leves, 0 moderados, 0 críticos", "Nenhum alerta" e "Ação padrão não indicada", e a velocidade do eixo mostra leituras de 3 a 4 rpm (motor parado) numa tendência de "-12,0 %". Com isso o diário não exercita Alertas emitidos, Sensores em risco nem Ações padrão, e o ROUGE e o checklist do diário (§6 "reportados para os dois relatórios") não provam nada. A lacuna é da instrução (do revisor); o executor a cumpriu à risca. Resultado esperado: **diário = o último dia com dados que tenha ao menos um alerta**; **semanal = 7 dias terminando no último dia com dados** (sem mudança). A referência manual diária é reescrita sobre os números do novo dia, o texto das seções 11 e 13 do notebook diz qual dia foi escolhido e por quê, e o teste de janelas cobre o novo critério (dia com alerta × último dia sem alerta). Os números do relatório semanal não mudam.
2. **O verificador deixa passar número inventado nas frases agregadas.** `_aggregate_number_tokens` (`relatorio.py`) inclui no conjunto permitido **todos os valores de todas as leituras** do sensor na série inteira. Reproduzido: no semanal, `variação -8,17 °C` → `variação -8,17 °C com máxima de 78,29 °C` (78,29 é um valor real de outra data) → `verificar_relatorio` devolve `[]`. Critério violado: §5.6 ("número fora do conjunto permitido") e §6 ("nenhum número fora do conjunto permitido"). Resultado esperado: numa frase com `[ref: período | sensor …]`, só são permitidos os números que o relatório calcula para aquele sensor (contagens por severidade e tendência, nos dois períodos); valores brutos de leitura saem do conjunto. Teste novo: a frase acima é reprovada; os dois relatórios gerados continuam sem violação.
3. **Concordância errada no texto entregue.** `relatorio.py` produz "Alerta de severidade crítico…" e "em risco, severidade crítico; severidade geral do ativo crítico" (feminino "severidade", adjetivo masculino), e o relatório é um dos entregáveis lidos pelo professor (critério de clareza). Resultado esperado: a severidade concorda com o substantivo em todas as frases do relatório ("severidade crítica", "moderada", "leve"), sem tocar nos textos de alerta da 01.01 (fora do escopo). Teste novo para a frase de alerta e a de sensor em risco.

**Pendências (não são achados)**
- **Revisão do usuário** (§5.3 e §5.7): `data/eventos_rotulados.json` (rótulos; conferir sobretudo os 6 derivados, em que sensor de corrente → anomalia elétrica e vibração → mecânica é convenção do executor, e os casos difíceis E-003, E-006, E-012, E-015, E-019, E-021, E-051 a E-060) e `data/relatorio_referencia.json` (o diário será reescrito pelo achado 1; o semanal confere com os números gerados).
- Fase B local (notebook executado em ambiente limpo, com a chave só no ambiente da sessão) depois da correção e da revisão dos rótulos; só então o zero-shot roda uma vez sobre o `teste`.
- Observação para o relatório final, não reprova: o verificador de relatório não confere que o texto de uma frase corresponde ao alerta citado além dos números; e a reescrita opcional por LLM do relatório (§5.6) não foi implementada, então o ROUGE é só do texto determinístico.

**Ao reentregar:** bloco novo na §9 com os 3 achados tratados; `python -m pytest tests -q` e `python tools/nb_check.py notebooks/sprint3_pln_alertas.ipynb`.

## Veredito — 2026-11-24 — 🟢 Aprovado (rodada 2, Fase A + Fase B)

**Escopo da rodada:** recriação das seções 9–14 do notebook (apagadas por um `git checkout` recomendado pelo revisor, erro do revisor, não do executor) e a Fase B completa: execução local em Python 3.11, venv limpo e chave só no ambiente da sessão. Fica pendente apenas a execução no Colab, que pertence à plan 02.05.

**O que foi verificado e como**
- `python -m pytest tests -q` → 60 passaram. `python tools/nb_check.py notebooks/sprint3_pln_alertas.ipynb --executado` → "Notebook válido" (exit 0), com 29 células e as 14 de código com `execution_count` 1 a 14, nenhuma com `output_type: error`. O `nbconvert` rodou sem `--allow-errors` e gravou o notebook (77 KB), o que só acontece sem falha de célula.
- Seções 1–8 idênticas à execução aprovada do 01.01: 43.123 leituras, 4.477 alertas (495 / 1.788 / 2.194), `alertas.json` sem diferença contra o commitado.
- Seção 9: 60 eventos, 12 por categoria, 2 `dev` + 10 `teste`.
- Seção 10: suporte 50 (10 por classe). **Zero-shot: F1 macro 0,800** (corretiva 0,824; preventiva 0,750; elétrica 0,909; mecânica 0,741; normal 0,778), 0 `indeterminado`. **Linha de base: F1 macro 0,070** (45 de 50 `indeterminado`). Matrizes de confusão com a coluna `indeterminado` e lista de 10 erros do zero-shot presentes e coerentes com o JSON exportado.
- Zero-shot rodou **uma vez** no `teste`: `cache_llm.jsonl` ganhou exatamente 50 registros do classificador (modelo `mistralai/mistral-small-3.2-24b-instruct`), mais os 21 do redator já existentes; `git diff --stat` mostra 50 inserções.
- Relatórios (seções 11–13): diário sobre 2026-08-22 e semanal com 5 seções, todas as frases com `[ref: …]`; ROUGE diário 0,449 / 0,286 / 0,350 e semanal 0,453 / 0,298 / 0,368; checklist verdadeiro, rastreabilidade 100 %, 0 violações nos dois. Os números das três correções da rodada 1 (dia com alerta, números só do que o relatório calcula, concordância "severidade crítica") aparecem corretos na saída.
- Exportação: `classificacao.json`, `relatorio_diario.json`, `relatorio_semanal.json` gerados e coerentes com as saídas do notebook.
- Chave: 0 ocorrências de `sk-or` ou `Bearer` no notebook, em `cache_llm.jsonl` e em `classificacao.json`; a chave só existiu no ambiente da sessão e foi removida.
- Confirmação do usuário (2026-11-24) do mapeamento canônico, dos rótulos dos eventos e da referência manual do relatório.

**Observações para o relatório final (não reprovam)**
- A linha de base por regras é fraca (F1 0,07): o léxico de 21 termos vem só do `dev`, como o protocolo exige, e quase nada do `teste` casa. É honesto, mas contrasta de forma extrema com o zero-shot; o relatório deve dizer que a diferença mede também o tamanho do léxico.
- O CSV tem só 10 dias distintos: a janela semanal cobre 22 e 23/08, então diário e semanal trazem os mesmos 54 alertas e diferem só nas tendências.
- O LLM não entra nos 4.477 alertas reais (todos `origem_texto="template"`); o verificador de relatório confere números, não que o texto de uma frase corresponda ao alerta citado; a reescrita opcional por LLM do relatório não foi implementada.
- Saída local imprime o caminho absoluto `C:\Users\Igor\...` nas células 16 e 28 e a nota "restart the kernel" do `pip` na célula 2; na execução do Colab (plan 02.05) isso não deve aparecer. Backlog nº 1 (1.412 templates reais acima de 60 palavras) segue em `specs/00-backlog.md`.
