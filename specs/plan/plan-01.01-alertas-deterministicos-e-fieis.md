---
tipo: "plan"
familia: "01"
item: "R01.1"
titulo: "Gerar alertas determinísticos e fiéis aos dados"
dominio: "Sprint 3 — Alertas e classificação"
status: "🟠 Em revisão"
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

## Resumo da execução — 2026-11-23

**Resultado:** Concluído com pendências

**O que foi feito**
- Implementei o contrato `Alerta`, as fronteiras de severidade, agrupamento de episódios, descarte de episódios leves curtos, templates e verificador de fidelidade em `src/pln/alertas.py:31`.
- Centralizei caminhos, parâmetros e modelos em `src/pln/config.py:10`; carreguei e validei o mapeamento canônico em `src/pln/sensores.py:22` e `data/sensores.json`.
- Implementei cliente OpenRouter injetável, cache, timeout, retry no mesmo modelo e retorno ao template após reprovação em `src/pln/llm.py:68`.
- Adicionei 9 casos de referência e 1 episódio leve descartável, 23 testes, verificador do notebook e notebook sem saídas com as seções 0–8.

**Arquivos alterados**
| Arquivo | Natureza | O que mudou |
|---|---|---|
| `requirements.txt` | criado | Dependências com versões fixas. |
| `src/pln/__init__.py` | criado | Inicialização do pacote. |
| `src/pln/config.py` | criado | Caminhos, parâmetros, ativo, modelos e termos proibidos. |
| `src/pln/sensores.py` | criado | Contrato do sensor e validação do mapeamento/limiares. |
| `src/pln/alertas.py` | criado | Severidade, episódios, contrato, templates e verificador. |
| `src/pln/llm.py` | criado | Cliente, cache e redação sujeita à verificação. |
| `data/sensores.json` | criado | Mapeamento canônico e ações padrão. |
| `data/alertas_teste.json` | criado | Casos sintéticos e resumos de referência. |
| `data/saida/.gitkeep` | criado | Mantém o diretório de exportação no repositório. |
| `tests/conftest.py` | criado | Preparação do caminho de importação dos testes. |
| `tests/test_alertas.py` | criado | Testes de classificação, episódios, rastreabilidade, templates e verificador. |
| `tests/test_llm.py` | criado | Testes de fallback, cache, retry e proteção da chave. |
| `tools/nb_check.py` | criado | Validação e execução isolada de células offline. |
| `notebooks/sprint3_pln_alertas.ipynb` | alterado | Notebook com as seções 0–8, avaliação e exportação. |
| `specs/plan/plan-01.01-alertas-deterministicos-e-fieis.md` | alterado | Status atualizado e este resumo append-only. |

**Verificações executadas**
- `pytest tests -q -p no:cacheprovider --basetemp <TEMP> --cov=src.pln.alertas --cov=src.pln.sensores --cov=src.pln.llm --cov-report=term-missing` → 23 passaram; cobertura total 84% (`alertas.py` 90%, `sensores.py` 82%, `llm.py` 71%).
- `python tools/nb_check.py notebooks/sprint3_pln_alertas.ipynb` → notebook válido, sem saídas e sem chave detectada.
- `code-auditoria-padrao` em `src/pln/`, `tools/` e `tests/` → sem violações de alta confiança; um achado heurístico de baixa confiança para a URL pública fixa em `src/pln/config.py:33`.
- `git diff --check` → sem erros de whitespace.

**Estado inicial do worktree:** `main`; `git status --short` vazio. O Git avisou que não conseguiu ler `C:\Users\Igor/.config/git/ignore`.

**Ambiente após a verificação:** O venv temporário de cobertura, diretório temporário do pytest, dados de cobertura, log de instalação e snapshot ambiental criado para comparação foram removidos. A comparação reportou `system_temp.appeared: []`; nenhum serviço foi iniciado. O worktree permaneceu sem commit.

**Critérios de aceite**
- [x] Mapeamento e limiares dos sensores validados contra `active_assets.json` pelos testes.
- [x] Fronteiras de severidade, episódios e descarte de episódio leve cobertos pelos testes.
- [x] Contrato e rastreabilidade dos IDs do CSV cobertos pelos testes.
- [x] Três templates por severidade e verificações de tom cobertos pelos testes.
- [x] Verificador rejeita os casos de número, limite, diagnóstico, causa e ação inventados e aceita os 9 textos de referência.
- [x] Redação não aprovada pelo verificador retorna ao template; cache e retry no mesmo modelo cobertos pelos testes.
- [x] Constantes centralizadas e famílias do gerador e juiz diferentes; notebook validado sem saída e sem chave.
- [ ] Fase B: execução no Colab, métricas sobre os casos e exportação de `data/saida/alertas.json` — pendente de execução do notebook no Colab.
- [x] Testes e auditoria estática executados; artefatos temporários removidos.

**Decisões e suposições**
- Adotei o mapeamento por descrição e magnitude indicado na plan, pois `data_variables.json` diverge nesses campos; a própria plan registra essa premissa para confirmação do usuário.
- Mantive a branch `main` conforme a instrução explícita posterior do usuário. Isso diverge da restrição geral do executor (§7.1); nenhum commit foi criado.
- A heurística de auditoria que sinaliza `src/pln/config.py:33` foi tratada como falso positivo: é o endpoint público fixo da API.

**Achados fora do escopo (não corrigidos)**
- `C:\Users\Igor/.config/git/ignore` — o Git não teve permissão para ler o arquivo global de exclusões; não alterei configuração externa ao repositório.

**Pendências / riscos**
- Executar o notebook no Colab e verificar as saídas reais, ROUGE/checklist e `data/saida/alertas.json`; a Fase B não foi declarada concluída.
- Confirmar com o usuário o mapeamento canônico adotado para os sensores.

## Resumo da execução (correção 1) — 2026-11-23

**Resultado:** Concluído com pendências

1. **Achado 1 — clareza:** encurtei os templates para até 60 palavras, mantendo ativo, grandeza, pico/unidade, desvio/nominal, janela, horários e ação. `verificar_clareza` fornece a mesma regra usada pelo checklist do notebook; teste cobre os 9 casos.
2. **Achado 2 — segunda tentativa:** a nova mensagem inclui os códigos e trechos reprovados e instrui a corrigir usando o alerta original. Teste simula número inventado na primeira resposta e texto fiel na segunda, aceito com `origem_texto="llm"`.
3. **Achado 3 — texto extra:** comparei o multiconjunto de palavras do candidato ao template canônico. A frase sobre rolamentos/lubrificação é reprovada; o teste de frases reordenadas com os mesmos fatos é aceito.
4. **Achado 4 — referência:** corrigi `moderado-vibracao` para desvio `+1,70 mm/s` (113,33%) sobre nominal `1,50 mm/s`. Teste valida os números dos 9 resumos contra os valores permitidos de cada alerta.
5. **Achado 5 — modelo:** alterei `MODELO_CLASSIFICADOR` para `mistralai/mistral-small-3.2-24b-instruct`; o ID e os demais três constam nas páginas atuais de modelos do [OpenRouter](https://openrouter.ai/api/v1/models), incluindo a [página do Mistral Small 3.2 24B](https://openrouter.ai/mistralai/mistral-small-3.2-24b-instruct).
6. **Achado 6 — conversão de tempo:** criei `SEGUNDOS_POR_MINUTO` para converter deltas em minutos; `MINUTOS_POR_HORA` permanece somente na conversão de minutos em horas. Teste confirma duração de 60 minutos.
7. **Achado 7 — texto e fuso:** normalizei a inicial da grandeza para minúscula, retirei “no instante registrado” para durações arredondadas abaixo de um minuto e marquei horários como UTC. Teste cobre intervalo de 30 segundos com os dois horários.
8. **Achado 8 — falha da API:** `redigir_alerta_com_fallback_api` devolve o template validado e sinaliza a falha; a célula 12 soma e imprime `Falhas de API`. Teste usa cliente falso que lança `OpenRouterRequestError`.

**Verificações da correção**
- `python -m pytest tests -q -p no:cacheprovider --basetemp <TEMP>` → 30 passaram.
- `MPLBACKEND=Agg MPLCONFIGDIR=<TEMP> python tools/nb_check.py notebooks/sprint3_pln_alertas.ipynb` → notebook válido; as células offline executaram.
- Validador AST Sarak em `src/pln/`, `tests/` e `tools/nb_check.py` → exit 0; sem violações de alta confiança. Permanece apenas o achado heurístico de baixa confiança para a URL pública fixa em `src/pln/config.py:35`.
- `git diff --check` nos arquivos de código, testes, dados e notebook → limpo. O diff completo ainda aponta uma linha em branco no EOF do veredito do revisor; preservei esse bloco append-only.

**Estado inicial da correção:** branch `main`; worktree já continha as alterações da execução anterior e modificações em `specs/00-indice.md` e `specs/panorama/00-resumo.md`. Não alterei esses dois arquivos nem criei commit.

**Ambiente após a correção:** venv, log de instalação, diretórios de teste, script diagnóstico e diretórios temporários do Matplotlib foram removidos. Nenhum serviço ou chamada OpenRouter foi iniciada nesta validação local.

**Pendências preservadas:** Fase B no Colab, confirmação do mapeamento canônico e eventual reinício do runtime após instalar `numpy==2.5.5`, conforme o veredito.

## Resumo da execução (correção 2) — 2026-11-23

**Resultado:** Concluído com pendências

1. **Achado único — paráfrase fiel:** removi a exigência de igualdade do multiconjunto inteiro de palavras. O verificador continua exigindo os fatos, a severidade, a duração em uma forma reconhecida, os horários, a unidade e a ação padrão; palavras novas precisam pertencer a `VOCABULARIO_PARAFRASE_PERMITIDO` e não podem exceder `MAX_PALAVRAS_PARAFRASE_ADICIONAIS` (14). O teste da construção “No ativo ... há um alerta leve ... chegou a pico ... o episódio durou uma hora” passa; a mesma frase com conteúdo sobre rolamentos/lubrificação e a versão com ação trocada falham.

**Verificações da correção**
- `python -m pytest tests -q -p no:cacheprovider --basetemp <TEMP>` → 34 passaram.
- `MPLBACKEND=Agg MPLCONFIGDIR=<TEMP> python tools/nb_check.py notebooks/sprint3_pln_alertas.ipynb` → notebook válido; células offline executadas.
- Validador AST Sarak em `src/pln/`, `tests/` e `tools/nb_check.py` → exit 0; sem violações de alta confiança. Permanece o achado heurístico de baixa confiança para a URL pública fixa em `src/pln/config.py:36`.
- `rg -n '[ \t]+$' src/pln tests` → sem whitespace final. `git diff --check` → exit 0; apenas aviso de conversão LF/CRLF em `specs/panorama/00-resumo.md`.

**Estado inicial da correção:** branch `main`; worktree já continha as alterações das rodadas anteriores e modificações em `specs/00-backlog.md`, `specs/00-indice.md` e `specs/panorama/00-resumo.md`. Não alterei esses arquivos nem criei commit.

**Ambiente após a correção:** venv temporário, log de instalação, diretório de testes e configuração temporária do Matplotlib removidos. Nenhuma chamada OpenRouter ou serviço foi iniciado.

**Pendências preservadas:** execução da Fase B no Colab, confirmação do mapeamento canônico e possível reinício do runtime após `numpy==2.5.5`. O achado sobre clareza dos alertas reais permanece como nota de backlog, fora do escopo numerado desta correção.

## Resumo da execução (correção 3) — 2026-11-23

**Resultado:** Concluído com pendências

1. **Achado 1 — decisão consistente de clareza:** `src/pln/alertas.py` agora compartilha uma normalização que converte espaços comuns, U+00A0 e U+202F para a mesma forma nos dois verificadores. `src/pln/llm.py` só registra origem `llm` se o candidato também passar por `verificar_clareza`; uma falha de clareza segue para a segunda tentativa com o código informado e, persistindo, retorna o template. Testes cobrem U+202F, candidato fiel acima de 60 palavras e os 9 casos sintéticos.
2. **Achado 2 — rascunho rejeitado visível:** `redigir_alerta_detalhado` retorna os candidatos rejeitados e suas violações junto com o texto escolhido. A célula 12 usa esse retorno da mesma execução para mostrar o rascunho reprovado, códigos/trechos e o texto final; identifica fallback somente quando a origem final é `template`, sem solicitar outra chamada ao LLM. Teste confirma os dados do rascunho após as duas tentativas configuradas.

**Arquivos alterados**
| Arquivo | Natureza | O que mudou |
|---|---|---|
| `src/pln/alertas.py` | alterado | Normalização compartilhada e aplicada aos dois verificadores. |
| `src/pln/llm.py` | alterado | Validação de clareza, registro dos rascunhos rejeitados e retorno detalhado. |
| `tests/test_alertas.py` | alterado | Regressão de equivalência com U+202F. |
| `tests/test_llm.py` | alterado | Regressões de candidato longo, metadados de rejeição e nove casos sintéticos. |
| `notebooks/sprint3_pln_alertas.ipynb` | alterado | Célula 12 separa candidato rejeitado, violações e texto final, identificando fallback com exatidão; outputs locais preservados. |
| `specs/plan/plan-01.01-alertas-deterministicos-e-fieis.md` | alterado | Status e resumo append-only da correção 3. |

**Verificações da correção**
- `& "$env:TEMP\pln-alertas-corr3-venv\Scripts\python.exe" -m pytest tests -q -p no:cacheprovider --basetemp "$env:TEMP\pln-alertas-corr3-pytest-final"` → 38 passaram.
- `$env:MPLBACKEND='Agg'; $env:MPLCONFIGDIR="$env:TEMP\pln-alertas-corr3-mpl"; & "$env:TEMP\pln-alertas-corr3-venv\Scripts\python.exe" tools/nb_check.py notebooks/sprint3_pln_alertas.ipynb --executado` → notebook válido; células offline executadas, sem chamada OpenRouter.
- Validador AST Sarak em `src/pln/`, `tests/` e `tools/nb_check.py` → exit 0 nos três alvos; sem violações em código/testes. Permanece apenas o achado heurístico de baixa confiança para a URL pública em `src/pln/config.py:36`.
- `git diff --check` → exit 0; avisos de conversão LF/CRLF, sem erro de whitespace.

**Estado inicial da correção:** branch `main`; worktree já continha `M notebooks/sprint3_pln_alertas.ipynb`, `M specs/plan/plan-01.01-alertas-deterministicos-e-fieis.md` e `?? notebooks/Sprint-4-NLP/` (clone aninhado do ensaio local). Preservei os outputs locais já existentes do notebook e o clone; não criei commit.

**Ambiente após a correção:** venv, diretório de testes e configuração do Matplotlib criados em `%TEMP%`; removidos após as verificações. Nenhuma chamada OpenRouter foi feita.

**Critérios de aceite desta correção**
- [x] U+202F produz a mesma decisão nos verificadores — evidência: teste em `tests/test_alertas.py`.
- [x] Candidato fiel acima de 60 palavras não recebe `origem_texto="llm"` — evidência: teste em `tests/test_llm.py`.
- [x] Candidato rejeitado e violações ficam acessíveis sem chamada adicional para exibição — evidência: teste confirma os dados retornados e exatamente duas chamadas configuradas.
- [ ] Fase B no Colab — pendente; os outputs atuais do notebook são do ensaio local anterior e não foram reexecutados nesta correção.

**Decisões e suposições**
- Mantive `redigir_alerta` e `redigir_alerta_com_fallback_api` com seus retornos anteriores; a célula 12 usa `redigir_alerta_detalhado` para exibir os dados já capturados pelo fluxo.
- Não chamei o OpenRouter nesta correção. A clareza dos textos aceitos é garantida antes do retorno e exercitada com clientes falsos; os exemplos reais serão reavaliados na execução Colab pendente.

**Achados fora do escopo (não corrigidos)**
- Os outputs do ensaio local, incluindo o erro de instalação e o caminho local registrados na plan, e o clone `notebooks/Sprint-4-NLP/` já estavam no worktree inicial; mantive-os conforme o escopo exclusivo dos dois achados numerados.

**Pendências preservadas:** executar o notebook corrigido no Colab, confirmar o mapeamento canônico dos sensores e atender ao pedido do veredito sobre o clone/outputs antes de qualquer commit. O backlog sobre templates reais extensos permanece fora do escopo numerado desta correção.

---

# 10. Veredito

<!-- Preenchido pelo REVISOR. Append-only: um bloco por rodada, com o que foi verificado e como. -->

## Veredito — 2026-11-23 — 🔴 Reprovado

**Escopo da rodada:** Fase A (local). A Fase B (execução no Colab) **não** foi iniciada: reprovada antes, para não gastar uma execução num código que será alterado.

**O que foi verificado e como**
- `git status` / `git diff --stat`: só arquivos de §3.1 (mais `data/saida/.gitkeep`); nada fora do escopo; sem commit do executor.
- `python -m pytest tests -q` → 23 passaram. `python tools/nb_check.py notebooks/sprint3_pln_alertas.ipynb` → verde.
- Leitura integral de `src/pln/config.py`, `sensores.py`, `alertas.py`, `llm.py`, `tests/test_alertas.py`, `data/sensores.json`, `data/alertas_teste.json` e das 17 células do notebook.
- Execução real sobre `data/dados-w22.csv`: 43.123 leituras → 4.477 alertas (leve 495, moderado 1.788, crítico 2.194) em 0,6 s; 200 templates, 0 reprovados pelo verificador; todos os `ids_leitura` existem no CSV (teste do executor).
- `GET https://openrouter.ai/api/v1/models` (2026-11-23): 3 dos 4 ids de `config.py` existem; **1 não existe** (achado 5).
- Varredura de chave: nenhum valor de `sk-or-` ou `OPENROUTER_API_KEY=` no repositório (só o padrão de busca no `nb_check.py`).
- Resumo do executor × diff: coerente (nenhuma divergência).

**Achados**

1. **O próprio template reprova no checklist de clareza em 9/9 casos.** `notebooks/sprint3_pln_alertas.ipynb` célula 14 (`checklist_result`) exige ≤ 60 palavras; `gerar_template` (`src/pln/alertas.py:264-281`) produz 77–82 palavras. A seção 7 mostraria "clareza = False" para todo template e o critério §6 (ROUGE + checklist) falha. Critério violado: §5 passo 10 (seção 7) e §6. Resultado esperado: os 9 templates de `alertas_teste.json` passam em **clareza** (≤ 60 palavras pela mesma contagem do notebook) **mantendo** os campos exigidos pelo passo 4 da plan (ativo, grandeza, valor, desvio e nominal, janela, horário, ação padrão). O executor decide o que condensar; `verificar_texto` e `_missing_episode_facts` acompanham o template; testes atualizados, e um teste novo garante `clareza` nos 9 casos.
2. **A segunda tentativa de redação é inútil.** `src/pln/llm.py:155-161`: as duas tentativas enviam as mesmas `messages` com temperatura 0 e seed fixa, e o cache (`llm.py:75-81`) devolve a mesma resposta; `MAX_TENTATIVAS_REDACAO = 2` nunca produz um candidato diferente. Critério violado: §5 passo 6 ("até 2 tentativas"). Resultado esperado: a 2ª tentativa inclui, nas mensagens, os **códigos e trechos das violações** da 1ª (sem fatos novos). Teste novo: LLM falso devolve número inventado na 1ª e texto fiel na 2ª, e `origem_texto == "llm"`.
3. **O verificador deixa passar conteúdo livre sem número nem termo da lista.** `src/pln/alertas.py:366-383`: `verificar_texto(template + " Verifique também os rolamentos e a lubrificação.", alerta)` não é reprovado (sem número, sem termo de `TERMOS_PROIBIDOS`, ação padrão presente). É a falha exata que o professor apontou (F1: "acrescentam … diagnósticos … que não estão nos dados"). Critério violado: §1 e §6 ("`redigir_alerta` nunca devolve texto reprovado" / texto fiel). Resultado esperado: `verificar_texto` reprova **qualquer informação que não esteja no template** (decisão do executor sobre o mecanismo: por exemplo teto de comprimento e comparação de conteúdo com o template/campos do alerta), **sem** reprovar uma paráfrase que preserve todos os fatos e a ação. Testes novos: (a) template + frase extra sem número → reprovado; (b) reescrita com a ordem das frases alterada e os mesmos fatos → aceita.
4. **Referência manual com fatos errados.** `data/alertas_teste.json`, caso `moderado-vibracao`: o resumo cita "nominal de 2,80 mm/s", "+0,40 mm/s" e "26,67%"; 2,80 é o limiar `warning`; o nominal da vibração é 1,50 mm/s (pico 3,20 → desvio +1,70 mm/s, 113,33%). Referência errada contamina o ROUGE. Critério violado: §5 passo 7 ("só fatos do caso"). **Correção exata (mecânica):**
   - arquivo: `data/alertas_teste.json`
   - antes: `desvio +0,40 mm/s (26,67%) acima do nominal de 2,80 mm/s`
   - depois: `desvio +1,70 mm/s (113,33%) acima do nominal de 1,50 mm/s`
   - verificação: `grep -c "nominal de 2,80 mm/s" data/alertas_teste.json` → `0`. Acrescentar um teste que confere que **todo número** de cada `resumo_referencia` pertence ao conjunto permitido do alerta do caso (formatado como em `_format_number`); os outros 8 casos já cumprem.
5. **`MODELO_CLASSIFICADOR` não existe no OpenRouter.** `src/pln/config.py:38`: `mistralai/mistral-small-3.2-24b-instruct-2506` não consta em `GET /api/v1/models` (consta `mistralai/mistral-small-3.2-24b-instruct`). A plan 01.02 chamaria um modelo inexistente. Critério violado: §5 passo 2 (ids escolhidos da lista pública). **Correção exata (mecânica):**
   - arquivo: `src/pln/config.py`
   - antes: `MODELO_CLASSIFICADOR = "mistralai/mistral-small-3.2-24b-instruct-2506"`
   - depois: `MODELO_CLASSIFICADOR = "mistralai/mistral-small-3.2-24b-instruct"`
   - verificação: a lista de `curl -s https://openrouter.ai/api/v1/models` contém esse id e os outros três ids de `config.py`.
6. **Constante com nome e uso trocados.** `src/pln/alertas.py:149` e `:178` dividem **segundos** por `MINUTOS_POR_HORA` (60) para obter minutos; só `:237` usa a constante pelo que ela diz. Dois significados sob o mesmo nome (padrao-escrita: nomes que dizem o que são, zero hardcoded). Resultado esperado: constante própria em `config.py` (segundos por minuto) usada nas duas conversões de `alertas.py`; `MINUTOS_POR_HORA` só onde converte minutos em horas.
7. **Texto do alerta pouco natural e com uma afirmação inconsistente** (naturalidade vale 20 %): saída real do alerta `A-0003`: "A **Corrente** elétrica por fase atingiu…" (grandeza com maiúscula no meio da frase; o mesmo em "A Velocidade do eixo" e "A Temperatura do enrolamento (estator)") e "O episódio ocorreu **no instante registrado**, em 3 leituras, **entre 05/05/2026 às 01:22 e 05/05/2026 às 01:23**" (diz "instante" e informa dois horários distintos). Os horários do CSV são UTC (`+00`) e o texto não o diz, enquanto o ativo está em Sorocaba. Resultado esperado: grandeza com minúscula inicial dentro da frase; nenhuma frase afirma "instante" quando `inicio != fim`; horários marcados como UTC; `verificar_texto` acompanha. Testes: episódio de menos de 1 min não contém "instante registrado" junto de dois horários; o texto contém "UTC".
8. **Uma falha de API derruba a célula do Colab.** `notebooks/sprint3_pln_alertas.ipynb` célula 12 chama `redigir_alerta` sem tratamento; `OpenRouterClient._request_with_retry` levanta `RuntimeError` após 3 tentativas (limite de taxa é esperado em modelos baratos) e a execução para no meio, sem notebook entregável. Critério violado: §6 Fase B ("sem nenhum erro"). Resultado esperado: falha de API numa redação mantém o **template** com `origem_texto="template"`, é **contada e impressa** (`falhas_api`) e nunca interrompe a célula; nunca troca de modelo. Teste novo com cliente falso que levanta.

**Pendências que continuam para a Fase B (não são achados):** execução no Colab; confirmação pelo usuário do mapeamento canônico dos sensores; atenção ao `numpy==2.5.5` fixado em `requirements.txt` — se o Colab pedir *Restart runtime* após a célula 1, reinicie e rode de novo a partir da célula 1.

**Ao reentregar:** acrescentar novo bloco na §9 com os 8 achados tratados; rodar `python -m pytest tests -q` e `python tools/nb_check.py notebooks/sprint3_pln_alertas.ipynb`.

## Veredito — 2026-11-23 — 🔴 Reprovado (rodada 2, correção 1)

**Escopo da rodada:** Fase A (local). A Fase B continua não iniciada: ainda há um defeito que muda o comportamento do LLM, e rodar o Colab antes dele gastaria uma execução.

**O que foi verificado e como**
- `git status`: mesmos arquivos da §3.1 da rodada anterior; nada fora do escopo; sem commit do executor. Resumo da correção × diff: coerente, sem divergência.
- `python -m pytest tests -q` → 30 passaram. `python tools/nb_check.py notebooks/sprint3_pln_alertas.ipynb` → verde.
- `GET https://openrouter.ai/api/v1/models`: os 4 ids de `config.py` existem (achado 5 resolvido). `grep -c "nominal de 2,80 mm/s" data/alertas_teste.json` → 0 (achado 4 resolvido). `SEGUNDOS_POR_MINUTO` em `config.py:24`, usada em `alertas.py:152` e `:181`; `MINUTOS_POR_HORA` só em `:242` (achado 6 resolvido).
- Execução real sobre `data/dados-w22.csv` (4.477 alertas): 0 templates reprovados pelo verificador; no máximo 51 palavras por contagem simples; achado 7 resolvido no texto (grandeza em minúscula, horários com `UTC`, nenhum "instante registrado" junto de dois horários).
- Achado 3 (frase extra): `template + " Verifique também os rolamentos e a lubrificação."`, `"... precisa de manutenção imediata."` e `"... parar a máquina."` → todas reprovadas; frases reordenadas → aceitas.
- Achados 2 e 8: lidos em `llm.py:164-228` e nos testes `test_second_rewrite_includes_the_previous_violations` e `test_api_failure_returns_the_template_and_reports_failure`; coerentes com o resultado pedido.
- Varredura de chave: nenhum valor de chave no repositório.

**Achados desta rodada**

1. **O verificador só aceita reordenação: toda reescrita real é reprovada, e o LLM nunca vira o texto final.** `src/pln/alertas.py:391-409` (`_unsupported_content_violations`) exige que o multiconjunto de palavras do candidato seja **idêntico** ao do template; o prompt de `src/pln/llm.py:203-204` pede "português fluido", ou seja, reescrever. Reproduzido: uma paráfrase fiel, com todos os números, unidades, horários e a ação padrão, só trocando conectivos ("No ativo Teste (Sorocaba) há um alerta leve: a corrente elétrica por fase chegou a pico 129,48 A, …") devolve `conteudo_nao_sustentado`. Qualquer palavra a mais ou a menos reprova, então na Fase B `origem_texto` será quase sempre `template` e a etapa de LLM do pipeline fica decorativa. Critério violado: veredito anterior, achado 3, resultado esperado ("**sem** reprovar uma paráfrase que preserve todos os fatos e a ação") e §1 da plan (o LLM só reescreve o que o código calculou). O exemplo (b) que o veredito anterior pedia, só "ordem das frases alterada", era estreito demais; o executor o cumpriu à risca, e a lacuna é da instrução. Resultado esperado agora: `verificar_texto` continua reprovando **informação nova** (frase sem número com conteúdo extra, afirmação de causa, diagnóstico ou prognóstico, outro ativo, outra grandeza, outra unidade, outra ação) **e passa a aceitar** uma reescrita que troque conectivos e a construção das frases mantendo todos os fatos e a ação padrão. O mecanismo é decisão do executor, dentro do padrão (por exemplo, exigir os fatos e a ação e limitar o vocabulário adicional por teto de palavras novas, ou por lista fechada de conectivos). Testes novos: (a) a paráfrase fiel acima → aceita; (b) a mesma paráfrase com uma frase extra sem número ("Verifique também os rolamentos e a lubrificação.") → reprovada; (c) uma paráfrase que troque a ação padrão por outra → reprovada; os testes existentes continuam verdes.

**Registrado no backlog (não reprova):** com a régua `verificar_clareza` do notebook (≤ 60 palavras por `\w+`, que conta cada parte de uma data), 1.412 dos 4.477 templates reais a falham (vibração e velocidade críticas ou moderadas, de ação padrão longa); o notebook só aplica a régua aos 9 casos de teste, que passam.

**Ao reentregar:** acrescentar bloco novo na §9 com o achado tratado; rodar `python -m pytest tests -q` e `python tools/nb_check.py notebooks/sprint3_pln_alertas.ipynb`. Pendências da Fase B continuam: execução no Colab; confirmação do mapeamento canônico dos sensores; possível *Restart runtime* após a célula 1 por causa do `numpy==2.5.5`.

## Veredito — 2026-11-23 — 🔴 Reprovado (rodada 3, correção 2 + execução local de ensaio)

**Escopo da rodada:** Fase A da correção 2 (código aprovado em leitura e comportamento) e **leitura da execução do notebook feita localmente pelo usuário**, tratada como **ensaio**: o critério da Fase B exige execução no Colab, e esta rodou em Python 3.11 local (clone de `8bdd29d` dentro de `notebooks/Sprint-4-NLP/`). O ensaio revelou dois defeitos de comportamento/apresentação, descritos abaixo.

**O que foi verificado e como**
- `python -m pytest tests -q` → 34 passaram. `python tools/nb_check.py notebooks/sprint3_pln_alertas.ipynb --executado` → "Notebook válido".
- Código executado = código commitado: `git -C notebooks/Sprint-4-NLP log` → `8bdd29d`; `diff -rq --strip-trailing-cr src notebooks/Sprint-4-NLP/src` → vazio.
- Saídas lidas célula a célula (8 células de código, `execution_count` 1 a 8, nenhum `output_type: error`): 43.123 leituras; leituras por faixa normal 9.918 / leve 12.055 / moderado 3.961 / crítico 2.818; **4.477 alertas** (495 / 1.788 / 2.194, idêntico ao pipeline que o revisor rodou à parte); 3 exemplos reais com `ids_leitura`; fidelidade dos templates **100 %** (9/9); taxa de aceitação do LLM 88,9 % (8/9); **0 falhas de API**; ROUGE template 0,586 / 0,396 / 0,543 e ROUGE LLM 0,584 / 0,406 / 0,491 (1 / 2 / L); checklist sobre 18 linhas (9 de template + 9 de LLM); `data/saida/alertas.json` com 4.477 registros (4.476 `template`, 1 `llm`: só os 3 exemplos reais passam pelo LLM, e um deles caiu no template).
- Chave: 0 ocorrências de `sk-or` ou `Bearer` no notebook executado e em `cache_llm.jsonl` (21 registros: modelo e resposta, sem chave).
- Reprodução dos achados abaixo contra as respostas reais gravadas em `cache_llm.jsonl`.

**Achados**

1. **O texto que o pipeline entrega com `origem_texto="llm"` reprova na própria clareza em 4 de 8 casos.** Tabela do checklist (célula 14): `leve-temperatura`, `leve-vibracao`, `moderado-limite-warning` e `critico-temperatura` com `origem=llm` têm `clareza=False`. Reproduzido com as respostas do cache: (a) em 3 casos o modelo escreveu o valor com **espaço fino não separável (U+202F)** entre número e unidade (`82,00\u202f°C`, `90,00\u202f°C`, `120,00\u202f°C`); `_mentions_unit` (`src/pln/alertas.py`, `\s*`) aceita, mas `verificar_clareza` compara o texto literal `82,00 °C` e reprova; (b) em `leve-vibracao` o texto tem 62 palavras (> `MAX_PALAVRAS_ALERTA` = 60), porque o verificador aceita até `MAX_PALAVRAS_PARAFRASE_ADICIONAIS` = 14 palavras novas sobre um template que já chega perto do teto. Critério violado: §5 passo 10 (seção 7: checklist de clareza) e a coerência dos dois verificadores (o que `redigir_alerta` aceita deve passar no checklist que o notebook aplica). Resultado esperado: (i) os dois verificadores usam **uma só normalização** de espaços equivalentes (comuns, não separáveis, finos); (ii) `redigir_alerta` só devolve `origem_texto="llm"` para texto que **também** passa em `verificar_clareza` (texto fiel mas longo demais vira nova tentativa com a violação informada, ou template); (iii) com isso, nos 9 casos de teste e nos exemplos reais, todo texto `llm` passa na clareza. Testes novos: texto fiel com U+202F entre valor e unidade → decisão idêntica nos dois verificadores; texto fiel com mais de 60 palavras → não vira `llm`.
2. **Rótulo enganoso na célula 12.** `notebooks/sprint3_pln_alertas.ipynb` célula 12 imprime `"Exemplo rejeitado pelo verificador:"` seguido do **template** do caso `moderado-corrente` (o texto que ficou depois da rejeição), não do candidato que o LLM escreveu e foi reprovado; o leitor conclui que o texto mostrado violou o verificador, e ele é o texto aprovado. Critério violado: §5 passo 10 (seção 6: exemplos aceito/**rejeitado**) e a honestidade do que o notebook declara (o problema que o professor apontou em F4). Resultado esperado: o exemplo rejeitado mostra o **candidato rejeitado** e os **códigos das violações** (o executor decide como expor isso a partir de `redigir_alerta`), e o texto final que ficou é rotulado como tal (fallback para o template). Teste: o candidato rejeitado e as violações ficam acessíveis sem chamada extra ao LLM.

**Pendências da Fase B (não são achados; o Colab continua obrigatório)**
- Reexecutar no **Colab**, com o segredo `OPENROUTER_API_KEY`, depois da correção. A execução local deixou na saída da célula 1 um **erro visível do `pip`** (`numpy==2.5.5` exige Python ≥ 3.12; o ensaio usou 3.11) e um **caminho absoluto local** impresso na célula 16 (`C:\Users\Igor\...`); no Colab nenhum dos dois deve aparecer.
- Antes de qualquer commit: remover `notebooks/Sprint-4-NLP/` (clone aninhado, contém `.git`) e não commitar o `notebooks/sprint3_pln_alertas.ipynb` desta execução local.
- Confirmação do mapeamento canônico dos sensores pelo usuário.

**Ao reentregar:** bloco novo na §9 com os 2 achados tratados; `python -m pytest tests -q` e `python tools/nb_check.py notebooks/sprint3_pln_alertas.ipynb`.
