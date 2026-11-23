---
tipo: "plan"
familia: "01"
item: "R01.1"
titulo: "Gerar alertas determinísticos e fiéis aos dados"
dominio: "Sprint 3 — Alertas e classificação"
status: "🟡 Em execução"
prioridade: "Alta"
tags: ["plan", "sprint-3", "alertas", "F1"]
relacionados: ["[[00-contexto]]", "[[plan-01.02-classificacao-e-relatorio-rastreavel]]"]
depende_de: ""
destino_sintese: "specs/01.01-alertas-deterministicos.md + 00-contexto.md"
---

# 1. Objetivo

O notebook `sprint3_pln_alertas.ipynb` gera, a partir de `data/dados-w22.csv` e dos limiares de `data/active_assets.json`, alertas
leve, moderado e crítico cujo texto contém **apenas fatos calculados** (valor, limiar, horário, duração, ação padrão), com um
verificador que rejeita qualquer número, limite, diagnóstico ou prognóstico fora dos dados (requisito **F1**).

# 2. Contexto

- A entrega anterior pedia ao LLM que escrevesse o alerta a partir de 2 números e o professor apontou que os textos
  "acrescentam limites, diagnósticos e prognósticos que não estão nos dados" (`docs/feedback-professor.md`). Só havia 3 alertas.
- Decisão do dono: **fluxo determinístico**; o LLM só transcreve/redige fatos já calculados, sob verificador.
- Os dados: 1 ativo (`Teste`, Sorocaba), 6 variáveis, ~7,2 mil leituras cada, 2026-05-05 → 2026-08-23. Só 4 variáveis têm limiar
  (`nominal`, `warning`, `critical`) em `active_assets.json`.
- **`data_variables.json` é inconsistente**: nome/unidade contradizem a descrição e a magnitude. Mapeamento canônico adotado
  (descrição + magnitude; **premissa a confirmar pelo usuário** no veredito):

| variable_id (prefixo) | Grandeza canônica | Unidade | Limiares (nominal / warning / critical) | Evidência |
|---|---|---|---|---|
| `9c611f84` | Temperatura do enrolamento (estator) | °C | 75 / 90 / 110 | descrição "monitoramento térmico das bobinas"; média 82,8; máx 150 |
| `8addd89b` | Corrente elétrica por fase | A | 125 / 140 / 160 | descrição "consumo elétrico por fase"; média 133; máx 185 |
| `3f809255` | Vibração no mancal lado acoplado | mm/s | 1,5 / 2,8 / 4,5 | descrição "velocidade de vibração no mancal"; média 2,07; máx 5,2 |
| `156b96a1` | Velocidade do eixo | rpm | 1750 / 1800 / 1850 | descrição "rotação por minuto"; média 1786 |
| `aa09b4cd` | Temperatura interna das bobinas | °C | — (sem limiar) | descrição; média 70,1 |
| `472e04da` | Vibração global | mm/s | — (sem limiar) | descrição; média 1,29 |

- Severidade por faixa de **desvio acima do nominal**: `< nominal` normal · `nominal ≤ v < warning` leve ·
  `warning ≤ v < critical` moderado · `v ≥ critical` crítico. Leituras abaixo do nominal são normais (partidas/paradas), limitação
  a documentar. Variáveis sem limiar não geram alerta (entram só como contexto).
- Cadência irregular (~22 min por variável). Alerta = **episódio**, não leitura.

# 3. Escopo

## 3.1 Dentro (o que pode ser tocado)
- `requirements.txt` — novo, versões fixadas (pandas, numpy, rouge-score, scikit-learn, requests, pytest, nbformat; as de RAG entram na plan 02.01)
- `src/pln/__init__.py` · `src/pln/config.py` — constantes, caminhos, ids de modelo (ver passo 2)
- `src/pln/sensores.py` — carrega os 3 JSON e expõe o mapeamento canônico (tabela do §2) como dados em `data/sensores.json`
- `data/sensores.json` — **novo**: mapeamento canônico + limiares + ação padrão por (grandeza, severidade)
- `src/pln/alertas.py` — severidade, episódios, contrato `Alerta`, templates, verificador
- `src/pln/llm.py` — cliente OpenRouter (cache em arquivo, sem fallback) e redação verificada
- `data/alertas_teste.json` — **novo**: ≥ 9 casos de teste com resumo de referência (substitui a parte de alertas de `data/dados_avaliacao.json`)
- `tests/test_alertas.py` · `tests/test_llm.py` — testes unitários
- `tools/nb_check.py` — verificador de notebook (estrutura, chaves, execução offline de células `offline`; modo `--executado`)
- `notebooks/sprint3_pln_alertas.ipynb` — **reconstruído** (seções 0 a 8 abaixo); as células antigas de classificação/relatório saem (voltam na plan 01.02)
- `data/saida/` — pasta de saídas (criada com `.gitkeep`)

## 3.2 Fora (o que NÃO pode ser tocado)
- `data/dados-w22.csv`, `data/active_assets.json`, `data/data_variables.json` — dados de origem, somente leitura
- `data/dados_avaliacao.json` — só é lido para aproveitar os 3 alertas antigos; **não** apagar nesta plan (removido na plan 02.03)
- `notebooks/sprint4_pln_rag.ipynb`, `docs/` (PDF), `specs/` — outras plans
- Classificação de eventos e relatório operacional — plan 01.02
- Qualquer refactor fora da lista acima

# 4. Referências obrigatórias

| Tipo | Referência | Por quê |
|---|---|---|
| Contexto | `00-contexto.md` · `00-knowledge.md` | regras inegociáveis (§2 e §7) |
| Requisito | `docs/feedback-professor.md` · `enunciado-4.txt` | F1 e o exemplo de saída esperado do alerta |
| **Skill** | `padrao-escrita` + `padrao-python` | limiares de código, zero hardcoded |
| **Skill** | `test-unitario` | testes das regras de severidade e do verificador |
| **Skill** | `code-auditoria-padrao` | gate ao final da escrita |
| Dados | `data/active_assets.json` · `data/data_variables.json` · `data/dados-w22.csv` (cabeçalho: `id,asset_id,variable_id,value,timestamp`) | origem dos fatos |
| Código legado (só leitura) | `notebooks/sprint3_pln_alertas.ipynb` | o que existia (3 alertas, LLM livre) |

# 5. Instruções de execução

1. [dirigido] Criar `requirements.txt`, `src/pln/__init__.py` e `tests/` com `conftest.py` que põe a raiz do repositório no `sys.path`.
   Pronto: `python -m pytest tests -q` roda (0 testes ok).
2. [dirigido] Criar `src/pln/config.py` com **todas** as constantes: caminhos (`data/`, `data/saida/`), `GAP_MAX_MIN = 60`
   (separação máxima entre leituras do mesmo episódio), `MIN_LEITURAS_LEVE = 3` (episódio só de severidade leve exige ≥ 3
   leituras; moderado/crítico emitem sempre), o ativo (`nome` e `local` lidos de `active_assets.json`), e quatro ids de modelo do
   OpenRouter: `MODELO_REDATOR`, `MODELO_CLASSIFICADOR`, `MODELO_GERADOR`, `MODELO_JUIZ`. Escolha os ids listando
   `GET https://openrouter.ai/api/v1/models` (público, sem chave): modelos com bom português, gratuitos ou baratos, e
   `MODELO_JUIZ` de **família diferente** de `MODELO_GERADOR` (asserção na importação). Registrar no código o motivo de cada escolha
   em uma linha. Sem lista de fallback.
3. [dirigido] Criar `data/sensores.json` e `src/pln/sensores.py`: o mapeamento canônico do §2 (id completo da variável, grandeza,
   unidade, limiares lidos de `active_assets.json` — **nunca copiados à mão**), mais a **ação padrão** por (grandeza, severidade):
   frase curta, imperativa, **sem causa nem previsão** (ex.: temperatura/moderado → "Recomenda-se verificar o sistema de
   refrigeração e programar inspeção."). `sensores.py` valida na carga que os limiares do JSON batem com `active_assets.json`.
4. [dirigido] Em `src/pln/alertas.py`: (a) `classificar_severidade(valor, limiares)` conforme o §2, fronteiras inclusivas no limite
   inferior da faixa; (b) `detectar_episodios(leituras, ...)` agrupa leituras consecutivas de um sensor com severidade ≥ leve
   separadas por ≤ `GAP_MAX_MIN`, severidade do episódio = máxima, descarta leve com < `MIN_LEITURAS_LEVE`; (c) dataclass `Alerta`
   com: `id` (`A-0001` sequencial por ordem de início), `ativo`, `sensor_id`, `grandeza`, `unidade`, `severidade`, `inicio`, `fim`,
   `duracao_min`, `n_leituras`, `valor_max`, `valor_medio`, `limiar_nominal`, `limiar_alerta`, `limiar_critico`, `desvio_abs`
   (`valor_max − nominal`), `desvio_pct`, `ids_leitura` (os `id` do CSV que sustentam o episódio — rastreabilidade) e `origem_texto`;
   (d) **três templates** (`leve`, `moderado`, `critico`) com vocabulário e tom distintos (leve: observação/monitoramento;
   moderado: atenção/inspeção programada; crítico: urgência/ação imediata) que usam **somente** campos do `Alerta` e a ação padrão;
   formato de números fixo (vírgula decimal, unidade). O texto cita o ativo, a grandeza, o desvio (`+18 °C acima do nominal`) e a janela
   (`nas últimas 3 horas` = `duracao_min`), como no exemplo do `enunciado-4.txt`.
5. [dirigido] Em `src/pln/alertas.py`: `verificar_texto(texto, alerta) -> list[Violacao]` que reprova: (a) qualquer **número** do texto
   que não esteja no conjunto permitido (campos do alerta formatados, limiares do ativo, ano/data do início/fim); (b) menção a grandeza,
   ativo ou unidade ausentes do alerta; (c) termos de **diagnóstico/causa/prognóstico** de uma lista `TERMOS_PROIBIDOS` em `config.py`
   (ex.: "devido a", "causado por", "provavelmente", "poderá falhar", "irá", "tende a", "em breve", "falha iminente", "vida útil");
   (d) ação diferente da ação padrão da (grandeza, severidade). Retorna a lista (vazia = fiel).
6. [dirigido] Em `src/pln/llm.py`: cliente OpenRouter (`requests`, temperatura 0, `seed` fixa quando suportada, timeout, retry com
   backoff **no mesmo modelo**, sem trocar de modelo), cache em `data/saida/cache_llm.jsonl` chaveado por hash(modelo, mensagens),
   leitura da chave por `google.colab.userdata.get("OPENROUTER_API_KEY")` com fallback para `os.environ` (nunca imprimir a chave).
   `redigir_alerta(alerta, cliente)`: pede ao `MODELO_REDATOR` que **reescreva** o texto do template em português fluido **sem acrescentar,
   remover ou alterar nenhuma informação**; passa por `verificar_texto`; até 2 tentativas; se reprovar, devolve o texto do template com
   `origem_texto="template"`; se aprovar, `origem_texto="llm"`. O cliente é injetável (testes usam um falso).
7. [dirigido] `data/alertas_teste.json`: ≥ 9 casos — 3 por severidade — como **episódios sintéticos de entrada** (lista de leituras) +
   `severidade_esperada` + `resumo_referencia` escrito à mão no tom do exemplo do enunciado e **só com fatos do caso**; incluir
   2 casos de fronteira (`valor == warning`, `valor == critical`) e 1 episódio leve que deve ser descartado (2 leituras). Aproveitar os
   3 alertas antigos de `data/dados_avaliacao.json` apenas se reescritos nos novos campos.
8. [dirigido] `tests/test_alertas.py` e `tests/test_llm.py` (skill `test-unitario`): fronteiras de severidade; agrupamento e quebra de
   episódio por gap; descarte de leve curto; rastreabilidade (`ids_leitura` ⊂ CSV); cada template exercita seu tom; verificador pega
   número inventado (`+30 °C`), limite falso (`limite de 100 °C`), "provavelmente", causa ("devido a rolamento") e ação trocada;
   `redigir_alerta` com LLM falso que **inventa um número** cai no template; com LLM falso fiel mantém `origem_texto="llm"`; cache
   evita 2ª chamada; chave nunca aparece em log/saída. Pronto: `python -m pytest tests -q` verde.
9. [dirigido] `tools/nb_check.py`: valida o `.ipynb` com `nbformat`; falha se houver **chave de API** (`sk-or-`, `OPENROUTER_API_KEY=`
   com valor) em qualquer célula/saída; sem `--executado` exige **nenhuma saída**; com `--executado` exige `execution_count` em todas as
   células de código e nenhuma saída de erro; executa localmente, em namespace isolado com `cwd` na raiz, as células marcadas com a tag
   `offline` (lógica sem rede nem LLM) e falha se alguma levantar exceção.
10. [dirigido] Reconstruir `notebooks/sprint3_pln_alertas.ipynb` (sem saídas) com as seções: **0** título, objetivo e tabela
    entregável→seção · **1** Setup (clonar `https://github.com/entregas-faculdade/Sprint-4-NLP.git` se `src/` não existir, `pip install -r
    requirements.txt`, ler `OPENROUTER_API_KEY` dos Secrets, imprimir só `chave carregada: True/False`) · **2** Dados e mapeamento
    canônico (tabela do §2 e **aviso explícito** da inconsistência de `data_variables.json`) · **3** Severidade e limiares
    (distribuição de leituras por faixa, gráfico) · **4** Episódios → alertas (contagem por severidade, 3 exemplos reais, um por nível,
    com `ids_leitura`) · **5** Templates (os três, lado a lado) · **6** Redação por LLM sob verificador (taxa de aceitação, exemplos
    aceito/rejeitado, `origem_texto`) · **7** Avaliação: ROUGE-1/2/L e BLEU opcional contra `alertas_teste.json` para template e para
    LLM, **com tokenizador próprio** (`re.findall(r"\w+", texto.lower())` — o padrão do `rouge-score` apaga letras acentuadas) +
    checklist binário por alerta: **precisão** (`verificar_texto` vazio), **clareza** (cita ativo, grandeza, valor/unidade e horário;
    ≤ 60 palavras), **utilidade** (contém a ação padrão) · **8** Exportar `data/saida/alertas.json` · Conclusão com os números.
    Células de lógica pura recebem a tag `offline`. Usar `src.pln`; o notebook não reimplementa regras.
11. Rodar `python -m pytest tests -q` e `python tools/nb_check.py notebooks/sprint3_pln_alertas.ipynb` (verdes) e a skill
    `code-auditoria-padrao` sobre `src/` e `tools/`.

# 6. Critérios de aceite

- [ ] `data/sensores.json` reproduz o mapeamento do §2 e os limiares batem com `active_assets.json` (teste automático).
- [ ] Fronteiras de severidade testadas (`==warning` → moderado, `==critical` → crítico, `==nominal` → leve).
- [ ] Cada alerta traz `ids_leitura` existentes no CSV e todos os campos do contrato.
- [ ] Os 3 templates existem e diferem em vocabulário e tom; nenhum usa dado fora de `Alerta`.
- [ ] `verificar_texto` rejeita os 5 casos de violação do passo 8 e aceita os 9 textos de template de `alertas_teste.json`.
- [ ] `redigir_alerta` nunca devolve texto reprovado pelo verificador (teste com LLM falso adversarial).
- [ ] Nenhuma constante de modelo, limiar ou caminho fora de `config.py`/`sensores.json`; `MODELO_JUIZ` e `MODELO_GERADOR` de famílias diferentes.
- [ ] Notebook sem saídas passa em `nb_check`; contém as seções 0–8; nenhuma chave no repositório.
- [ ] **Fase B:** notebook executado no Colab: todas as células com saída, nenhum erro, ROUGE e checklist calculados sobre ≥ 9 casos,
      taxa de fidelidade do texto de template = 100 %, `data/saida/alertas.json` presente.
- [ ] Ambiente e worktree limpos; testes do escopo verdes; `code-auditoria-padrao` sem violação nova.

# 7. Como verificar (uso do revisor)

- **Nível:** `escopada`.
- `git diff --stat` → só os arquivos de §3.1 aparecem (e `notebooks/` + `data/saida/` na Fase B).
- **Fase A (local):** `python -m pytest tests -q` → verde · `python tools/nb_check.py notebooks/sprint3_pln_alertas.ipynb` → verde ·
  `code-auditoria-padrao` sobre `src/pln/` e `tools/`.
- Leitura de `src/pln/alertas.py` → confirma que `Alerta` e os templates só usam campos do contrato; leitura de `src/pln/llm.py` →
  confirma ausência de fallback de modelo e de impressão de chave.
- `grep -rn "sk-or-\|OPENROUTER_API_KEY *=" .` → nenhum valor.
- **Fase B (notebook executado, trazido pelo usuário):** `python tools/nb_check.py notebooks/sprint3_pln_alertas.ipynb --executado` →
  verde; leitura das saídas das seções 4, 6 e 7: contagens, exemplos reais com `ids_leitura`, ROUGE e checklist.
- **Gate:** `nenhum` — projeto de notebooks, sem catálogo de regras de gate.

# 8. Destino da síntese

**Destino:** `specs/01.01-alertas-deterministicos.md` + `00-contexto.md`

Texto para transporte: o contrato `Alerta`; a regra de severidade por faixa acima do nominal e a de episódio (`GAP_MAX_MIN`,
`MIN_LEITURAS_LEVE`); o mapeamento canônico dos sensores e o aviso sobre `data_variables.json`; os 3 templates e a lista de termos
proibidos; o fluxo "template → LLM reescreve → verificador → fallback ao template"; os modelos escolhidos e o motivo. Em
`00-contexto.md`, trocar na §4 a linha de alertas pelo caminho da spec criada.

---

# 9. Resumo da execução

<!-- Preenchido pelo EXECUTOR. Append-only: cada rodada acrescenta um bloco novo; nada é removido. -->

---

# 10. Veredito

<!-- Preenchido pelo REVISOR. Append-only: um bloco por rodada, com o que foi verificado e como. -->
