---
tipo: "processo"
titulo: "Contexto do Repositório — Briefing de Entrada"
dominio: "Governança de Specs (SDD)"
status: "🟢 Vigente"
tags: ["processo", "contexto", "sdd"]
relacionados: ["[[00-knowledge]]", "[[00-indice]]", "[[00-backlog]]", "[[00-prompt-revisor]]", "[[00-prompt-executor]]"]
---

# 0. O que é este arquivo

Esta é a **porta de entrada de qualquer agente** neste repositório. Um agente que leu esta spec — e só ela —
deve saber: **o que** o repositório é, **quais regras** governam qualquer alteração, **onde** está cada
informação e **como** se trabalha aqui.

> ⚠️ **Este arquivo é um molde com instruções embutidas.** Ele chega ao repositório **vazio de conteúdo
> específico**: cada seção traz um bloco `> **Como escrever:**` (a instrução, que **permanece** no arquivo como
> contrato de manutenção) e um bloco `<!-- PREENCHER -->` (o conteúdo real, que o **agente revisor** escreve).
> Quem preenche esta spec é o **revisor**, direto, a pedido do usuário: é a edição de spec fixa fora do ciclo que o
> [[00-prompt-revisor]] prevê, sem plan.

**Quem escreve/atualiza:** exclusivamente o **agente revisor** ([[00-prompt-revisor]]).
**Quando atualizar:** sempre que uma plan aprovada mudar stack, arquitetura, fronteiras de módulo, regra
inegociável ou o mapa de roteamento. Nunca por conta própria: é a síntese de uma plan aprovada, ou o
preenchimento direto a pedido do usuário.

---

# 1. Identidade do repositório

> **Como escrever:** 3 a 6 linhas, em prosa direta. Responda: **o que este repositório é** (produto? base de
> conhecimento? biblioteca? site?), **qual problema resolve**, **quem consome** (usuário final, outros repos,
> agentes) e **o que ele explicitamente NÃO é**. Sem marketing, sem histórico. Um agente lê isto e para de
> supor. Proibido descrever a estrutura de pastas aqui — isso é da §3.

Repositório da **segunda entrega do Challenge FIAP × Forzy (PLN)**: um assistente de troubleshooting para motores elétricos
industriais (digital twin, motor WEG W22) que (1) transforma leituras de sensores em alertas e relatórios em português **sem
afirmar nada além dos dados**, (2) classifica eventos em 5 categorias e (3) responde perguntas por RAG sobre o catálogo técnico
do W22, citando página e seção. Consumidor: o professor avaliador (notebooks já executados, documento final e vídeo).
**Não é** um sistema em produção, nem um serviço modular: é código de pesquisa aplicada, versionado em repositório público.
A entrega anterior (nota 85) está avaliada; o feedback dela é a fonte dos requisitos F1–F7 em `docs/feedback-professor.md`.

---

# 2. Regras inegociáveis (resumo operante)

> **Como escrever:** liste **apenas** as regras que um agente pode violar sem perceber, em forma de bullets
> curtos e verificáveis. Duas fontes, nesta ordem:
> 0. **`CLAUDE.md` e `AGENTS.md` só apontam para este arquivo** — não repetem regra nem comando de verificação.
>    Uma instrução repetida lá vence esta em silêncio (mede-se: o comando antigo de lá anulou a regra nova), e
>    uma skill local de contexto paralela a este arquivo é outro ponto de divergência: não crie uma.
> 1. **Universais do ecossistema** — não reescreva: aponte para `AGENTS.md` (raiz) e para a skill
>    `padrao-escrita`. Cite no máximo os limiares que causam reprovação imediata (SRP; função ≤ 40 linhas;
>    aninhamento ≤ 3; ≤ 4 parâmetros; zero hardcoded; segredos só em `.env`; nenhuma exceção engolida).
> 1b. **Arquitetura de módulos** — se este projeto adota o template, **não descreva a anatomia**: aponte para
>    `arquitetura/04-regras.md` e diga a única coisa que o agente precisa saber sem abrir o arquivo — que ela
>    é cobrada por máquina, com `node tools/gate/validate.mjs`.
> 2. **Específicas deste repositório** — o que só vale aqui (convenções de nomes locais, uma biblioteca
>    proibida, um diretório que não se toca, um formato de retorno obrigatório).
>
> **Regra de ouro: referencie, nunca duplique.** Se uma regra já está numa spec fixa ou numa skill, escreva
> uma linha e o ponteiro. Conteúdo duplicado desatualiza e passa a mentir.

- **Fluxo determinístico primeiro.** Todo fato (valor, limiar, severidade, horário, página, seção) nasce de código; o LLM só
  **redige** texto sobre fatos já calculados, e todo texto de LLM passa por um verificador (números, referências, termos
  proibidos). Falhou no verificador → usa-se o texto de template, nunca o do LLM.
- **Nenhum diagnóstico, prognóstico ou limite inventado.** Limites citados = limiares de `data/active_assets.json`. Recomendação
  só da tabela de ações padrão. Proibido causalidade e previsão não calculadas (F1).
- **Juiz ≠ gerador.** Modelos de família diferente, ids fixos em `src/pln/config.py`, **sem fallback silencioso**; cada
  resposta registra o modelo que a produziu. Conhecimento externo nunca conta como fiel (F6).
- **Execução 100 % local, sem Colab** (decisão do dono, 2026-11-24). A chave vive só no `.env` da raiz (`OPEN-ROUTER-API-KEY`), ignorado pelo Git, e o
  código a lê de lá. Nunca em código, saída de notebook ou commit — o repositório é **público**.
- Universais: `AGENTS.md` e skills `padrao-escrita` + `padrao-python` (função ≤ 40 linhas, ≤ 4 parâmetros, zero hardcoded,
  nenhuma exceção engolida). Constantes e ids de modelo só em `src/pln/config.py`.
- Notebooks são **entregues já executados** (saídas visíveis, sem erro, sem chave). Antes da execução, ficam **sem saídas**.

---

# 3. Stack e arquitetura em uma página

> **Como escrever:** o mínimo para orientar, com ponteiro para o detalhe. Inclua:
> - **Stack**: linguagens + versões, frameworks, banco, runtime, gerenciador de pacotes.
> - **Camada de padrão da linguagem**: qual skill `padrao-*` se aplica (`padrao-python`, `padrao-typescript`).
>   Outra linguagem não tem camada de Nível 2, mas pode ter automação de limiar: o hook `padrao-limiares`
>   cobre `.go` e `.java` além de `.py` e `.ts`/`.js`. Registre qual dos dois cobre a stack — e, se nenhum
>   cobrir, que ali vale o Nível 0 do `padrao-escrita` conferido por leitura.
> - **Mapa de módulos/domínios**: tabela `módulo → papel → responsabilidade`. Projeto com o template de
>   módulos: os papéis são `domain` / `gateway` / `connector` (a forma do `module.json` de cada um, campo
>   `role`) — não transcreva, aponte.
> - **Fronteiras**: quem pode chamar quem, e por onde. No template, a resposta é sempre a mesma — pelo
>   **contrato HTTP** da `api/` do dono, declarado em `module.json:consumes`.
> - **Comandos vitais**: instalar, rodar, testar, lintar, buildar — copiáveis, verificados.
>
> Cada item aponta para a spec fixa em `arquitetura/` que o detalha. Esta seção é o índice, não o tratado.

- **Stack:** Python 3.11 ou superior (execução local), `pandas`, `rouge-score`, `scikit-learn`, `pymupdf`, `chromadb`, `sentence-transformers`,
  `requests`; testes `pytest`. Dependências fixadas em `requirements.txt`. Camada de padrão: `padrao-python`.
- **Mapa de pacotes** (`src/pln/`, nascem nas plans; ver `plan/`):

| Arquivo | Papel | Plan |
|---|---|---|
| `config.py` | constantes, ids de modelo, caminhos | 01.01 |
| `sensores.py` · `alertas.py` | mapeamento canônico, severidade, episódios, templates, verificador | 01.01 |
| `llm.py` | cliente OpenRouter (cache, sem fallback), redação verificada | 01.01 |
| `classificacao.py` · `relatorio.py` | classificador de eventos, relatório rastreável | 01.02 |
| `estado.py` · `rag.py` | estado operacional, chunking, índice, retriever (spec `02.01-pipeline-rag`) | 02.01 |
| `assistente.py` | persona, citação, confiança, abstenção, memória (spec `02.02-assistente-de-troubleshooting`) | 02.02 |
| `avaliacao.py` | métricas de recuperação, juiz por afirmação, calibração (spec `02.03-avaliacao-rag`) | 02.03 |
| `cenarios.py` | escolha dos episódios, diálogo dos cenários, tabela de limites (spec `02.04-cenarios-e-limites`) | 02.04 |

- **Fronteira:** os notebooks (`notebooks/`) só orquestram e exibem; a lógica vive em `src/pln/` e é testada em `tests/`.
- **Dados:** `data/dados-w22.csv` (43.123 leituras, 6 variáveis, 2026-05-05 a 2026-08-23), `data/active_assets.json`
  (limiares), `data/data_variables.json`, PDF em `docs/` (52 páginas, português). Saídas das execuções em `data/saida/`.
- **Comandos:** instalar `pip install -r requirements.txt` · testar `python -m pytest tests -q` · notebook sem executar
  `python tools/nb_check.py notebooks/<nb>.ipynb` · notebook executado `python tools/nb_check.py notebooks/<nb>.ipynb --executado`.

---

# 4. Mapa de roteamento — "que spec eu leio para esta tarefa?"

> **Como escrever:** esta é a seção **mais valiosa** do arquivo e a razão de ele existir. Uma tabela que
> responde à pergunta que todo agente faz ao receber uma tarefa. Uma linha por tipo de tarefa recorrente
> no repositório, com caminhos **relativos a `specs/`** e clicáveis.
>
> Preencha a coluna "Leia antes" com **specs fixas** (`arquitetura/`, `specs/`, `adr/`) — para skills e
> commands, aponte para [[00-knowledge]], que é o roteador de capacidades.
>
> As specs fixas são numeradas por **família** (`FF.NN-<slug>.md`); o catálogo é [[00-planejamento]] §1 —
> aponte para ele, nunca copie as famílias aqui.
>
> | Tipo de tarefa | Leia antes (specs fixas) | Capacidade |
> |---|---|---|
> | Alterar regra de negócio de \<módulo\> | `specs/FF.NN-<module>.md` | [[00-knowledge]] |
> | Criar/alterar endpoint | `arquitetura/FF.NN-api.md` + spec do módulo | [[00-knowledge]] |
> | Mexer em schema/migration | `arquitetura/FF.NN-dados.md` + ADR relevante | [[00-knowledge]] |
> | Container, ambientes, publicação, servidor | `arquitetura/FF.NN-operacao.md` (molde `template-operacao`) | [[00-knowledge]] |
> | Pipeline, versão, tag, proteção do repositório | `arquitetura/FF.NN-ci-cd.md` (molde `template-ci-cd`) | [[00-knowledge]] |
> | Mudar decisão estrutural | todos os `adr/` + `arquitetura/` | [[00-knowledge]] |
>
> Mantenha entre 6 e 15 linhas. Se passar disso, o repositório precisa de specs melhores, não de mais linhas
> aqui. **Ponteiro órfão é defeito**: toda spec citada tem de existir.

| Tipo de tarefa | Leia antes | Capacidade |
|---|---|---|
| Mexer em severidade, episódios, templates ou verificador de alertas | `specs/01.01-alertas-deterministicos.md` | [[00-knowledge]] |
| Mexer em classificador de eventos ou relatório | `specs/01.02-classificacao-e-relatorio.md` | [[00-knowledge]] |
| Mexer em chunking, índice, retriever ou estado operacional | `specs/02.01-pipeline-rag.md` | [[00-knowledge]] |
| Mexer em prompt, citação, confiança, abstenção ou memória do assistente | `specs/02.02-assistente-de-troubleshooting.md` | [[00-knowledge]] |
| Mexer em métricas, gabarito ou juiz | `specs/02.03-avaliacao-rag.md` | [[00-knowledge]] |
| Mexer em cenários de demonstração ou na tabela de limites | `specs/02.04-cenarios-e-limites.md` | [[00-knowledge]] |
| Documento final, README, vídeo | `plan/plan-02.05-*.md` · `docs/feedback-professor.md` | [[00-knowledge]] |
| Entender o que o professor exigiu | `docs/feedback-professor.md` · `enunciado-4.txt` | — |

> Cada plan, ao ser sintetizada, troca a sua linha acima pelo caminho da spec fixa criada.

---

# 5. Como se trabalha aqui (ciclo SDD)

> **Como escrever:** esta seção é **universal — copie o bloco abaixo como está**. Só acrescente desvios reais
> deste repositório (por exemplo: "toda plan que toca `pagamentos/` exige ADR"). Não reescreva o ciclo.

**Toda e qualquer alteração passa pelo revisor.** Nada é alterado "direto no código" — mas nem toda alteração
vira arquivo. O revisor **tria** cada demanda ([[00-prompt-revisor]] §4):

| A demanda deixa verdade documentada para trás? | Via | O que nasce |
|---|---|---|
| **Sim** — muda regra, contrato, stack, comportamento | **plan** | `plan-FF.NN` + linha no [[00-indice]] |
| **Não** — bug sem mudança de regra, typo, conformidade, limpeza | **prompt direto** | nada; a instrução vive só na conversa |

A via direta encurta a **papelada**, nunca a **verificação**: o executor trabalha igual e o revisor confere o
diff linha por linha do mesmo jeito. O ciclo abaixo é o da **plan**; a via direta salta os passos de síntese
e expurgo, porque não há verdade a transportar.

```
revisor escreve  specs/plan/plan-FF.NN-<slug>.md  +  linha no 00-indice
      ↓
executor lê  00-prompt-executor  +  plan-FF.NN  e executa
      ↓
alterações ficam no worktree (o executor não commita)
      ↓
revisor VERIFICA diretamente (não confia no resumo do executor)
      ├─ reprovado → prompt de correção → executor corrige → repete
      └─ aprovado  → status 🟢 + revisor entrega o veredito e o comando de commit (só commit)
      ↓
commit do código e da plan com o veredito, na dev/<nome> (do revisor, com panorama e "autorizo", ou do
usuário), e o usuário avisa
      ↓
revisor confere o veredito em HEAD, sintetiza nas specs fixas (adr/ · arquitetura/ · specs/) sem pedir
autorização, tira a linha do índice e entrega o comando completo; o rastro vai na resposta dele
      ↓
commit da síntese na dev/<nome> (git rm da plan, spec fixa, índice); o usuário faz o push da dev/<nome>
e abre o PR para a develop
```

**A plan é temporária**: vive em `specs/plan/` enquanto o trabalho está aberto e **some no ato da síntese**.
Não há estado "sintetizada aguardando limpeza" — o rastro passa a viver no Git. Por isso o [[00-indice]] tem
tamanho limitado pelo trabalho em andamento, e não pela idade do repositório.

Achado fora do escopo, em qualquer ponto, desce para o [[00-backlog]] — **nunca** vira plan nova no meio do
caminho.

| Papel | Spec de entrada | Pode escrever | Nunca faz |
|---|---|---|---|
| **Revisor** | [[00-prompt-revisor]] | plans, `00-indice`, `00-backlog`, specs fixas (na síntese e no preenchimento do `00-contexto`), prompts; commits em branch não protegida, com panorama | tocar código · fazer push · commitar em branch protegida |
| **Executor** | [[00-prompt-executor]] | código + resumo (na plan, ou na conversa) | criar/alterar outras specs · commitar · fazer push · mover ou remover plan |
| **Usuário** | — | qualquer coisa | — (é quem faz push, PR e merge, confirma o commit do veredito e promove itens do backlog) |

> **O executor nunca commita.** O revisor commita e mescla só em branch local não protegida, com panorama e
> "autorizo" ([[00-prompt-revisor]], "Git e ramificações"); push, PR e merge são do usuário.
> **Nenhum agente adiciona co-autoria**: sem `Co-Authored-By` e sem qualquer outra marca de autoria de agente
> na mensagem.

- **Trabalho direto na `main`** (decisão do dono: sem `develop` nem `dev/<nome>`); sem PR.
- **Execução em duas fases.** O executor entrega código, testes e notebook **sem saídas**. O revisor verifica a Fase A (local).
  O usuário roda o notebook **localmente** (venv limpo com `pip install -r requirements.txt`, `nbconvert --execute`, chave lida do `.env` da raiz, sem `--allow-errors`),
  e o revisor verifica a Fase B (saídas e arquivos de `data/saida/`) antes do veredito. A plan fica `🟠` entre as fases.
- **Nunca restaurar o notebook com `git checkout`/`git restore` enquanto houver trabalho não commitado nele:** apaga as células do
  executor (ocorreu em 2026-11-24).

### O ciclo neste repositório

O prompt da base manda; esta seção acrescenta obrigações de execução e verificação e só afrouxa os pontos que os prompts marcam como [parâmetro].

> **Os prompts e o `00-knowledge` são fixos.** Eles permanecem iguais aos da base e a base os atualiza sozinha quando mudam: não os edite aqui. Qualquer peculiaridade deste repositório (comandos, terminal, autorização, branches, obrigações) mora nesta seção e nas anteriores.

| Parâmetro | Padrão (sem declaração) | Este repositório declara |
|---|---|---|
| Git e ramificações | `main`, `master` e `develop` protegidas; a branch de trabalho é a `dev/<nome>`, e as vagas `plan/<arquivo>` saem dela só para trabalho paralelo; a `develop` só recebe PR da `dev/<nome>` e a `main` só o PR de versão; prefixos `dev/`, `plan/` e `sarak/`; nunca se trabalha nem se commita na `main` | `main` direta; sem `develop` nem `dev/<nome>`; sem PR. O push é do usuário. |
| Autorização permanente dos commits do fluxo | Não: panorama e autorização a cada escrita. | Não: o revisor entrega os comandos de commit e o usuário os executa. |
| Terminal padrão dos comandos para o usuário | O da sessão, dito a cada comando. | `bash` (Git Bash no Windows). |
| Verificação escopada | Testes e análise estática do escopo tocado, gate do módulo e gate do commit sobre o diff. | `python -m pytest tests/<arquivo> -q` do escopo · `python tools/nb_check.py <notebook>` · skills `code-auditoria-padrao` e `padrao-python` nos arquivos tocados. |
| Verificação ampla | Escopo tocado, consumidores afetados e gate do repositório. | `python -m pytest tests -q` · `python tools/nb_check.py` nos dois notebooks. Só com motivo escrito (mudança de `config.py`, de contrato entre `src/pln/` módulos ou de `requirements.txt`). |
| Verificação completa | Suíte inteira, build, ponta a ponta no navegador e container. | `python -m pytest tests -q` + os dois notebooks executados localmente (Fase B). Não há build, navegador nem container. |
| Gate do commit | Checagem equivalente ao hook sobre o diff staged. | Hook `.githooks/pre-commit` (segredos). `.githooks/verify_commit.py` fica fora do Git (`.git/info/exclude`): casa com os próprios padrões de segredo. |
| Navegador | Verificação visual no navegador, se houver superfície visual. | Não se aplica: sem superfície visual (só notebooks). |
| Numeração das plans | `plan-NN`, contador único no `00-indice`. | `plan-FF.NN`, contador por família no `00-indice`. |
| Panorama | Não adota. | Sim; este molde traz `panorama/` e o `00-indice` por família. |
| Spec de regras e geradores `--check` | `arquitetura/04-regras.md` e os geradores do template de módulos: `node tools/sync-env.mjs --check`, `node tools/sync-deploy.mjs --check`, `node tools/generate-port-schemas.mjs --check` e `node tools/generate-lint-config.mjs --check`. | Não se aplica (projeto sem template de módulos). |
| Uso de ADR | Sim, somente com duas opções reais, custo da escolhida e alto custo de reversão. | Sim, sob esses critérios. |
| Obrigações acrescentadas | Nenhuma. | Plan que altera notebook declara a Fase A (local) e a Fase B (saídas da execução local) em "Como verificar". <!-- Exemplo: execução que cria migration entrega antes/depois/rollback. --> |
| Medição do ambiente | Comandos da skill `code-limpeza-ambiente`. | subcomandos `snapshot` e `diff` da skill `code-limpeza-ambiente` (`environment.py`), com `--out <snapshot.json> --tmp-prefix <prefixo>` e `--from <snapshot.json>`; caminho da skill conforme a instalação do plugin. |

Se uma declaração de comando ficar vazia, a plan nomeia os comandos, como no legado.

---

# 6. Capacidades disponíveis

> **Como escrever:** seção **universal — não a preencha com conteúdo**. Apenas mantenha o ponteiro. As
> skills, commands, agents e hooks **não vivem neste repositório**: vêm da memória/plugin do agente. O
> catálogo e as regras de roteamento estão em [[00-knowledge]].

Antes de escolher **como** fazer algo, leia **[[00-knowledge]]** — é o roteador de capacidades
(situação → skill/command/agent/hook) e o único lugar onde esse catálogo é mantido.

---

# 7. Fronteiras — o que nunca fazer neste repositório

> **Como escrever:** bullets no imperativo negativo, cada um com o **porquê** em meia linha. Só o que é
> específico deste repositório (as proibições de papel já estão na §5 e nas specs de prompt). Exemplos do
> tipo de item: diretórios gerados que não se editam à mão; arquivos que só o usuário altera; operações
> irreversíveis que exigem confirmação; integrações que não podem ser chamadas em desenvolvimento.

- **Não versionar chave** nem imprimir `OPENROUTER_API_KEY`: o repositório é público e a saída do notebook também é.
- **Não editar à mão** `data/saida/*` nem o texto de notebook executado: são evidência da execução local.
- **Não alterar** `data/dados-w22.csv`, `data/active_assets.json` nem `data/data_variables.json`: dados de origem (a leitura
  correta deles é feita em `src/pln/sensores.py`, sem reescrever os arquivos).
- **Não usar fallback de modelo** nem trocar o modelo no meio de uma avaliação: mistura de modelos invalida as métricas.
- **Não deixar o LLM produzir fato**: número, limiar, sensor, página e seção vêm de código; o LLM só reescreve.
- **Não confiar no nome/unidade de `data_variables.json`**: contradizem a descrição e a magnitude dos dados (ver §8).

---

# 8. Estado e pendências conhecidas

> **Como escrever:** o que um agente descobriria do jeito difícil. Dívidas técnicas aceitas, áreas em
> migração, incoerências conhecidas entre código e spec, decisões em aberto. **Datas sempre absolutas**
> (`2026-07-31`, nunca "semana passada"). Item resolvido sai daqui — esta seção não é histórico; o histórico
> é o `git` e os `adr/`.

- **`data_variables.json` está inconsistente** (2026-11-23): o nome/unidade de cada variável contradiz a descrição e a magnitude
  dos valores (ex.: "Velocidade - Porta 1 [mm/s]" tem média 82,8 e limiares 75/90/110, descrita como "monitoramento térmico das
  bobinas do estator"). O mapeamento canônico (`specs/01.01-alertas-deterministicos.md` §2.1) usa descrição + magnitude e foi confirmado pelo usuário em 2026-11-24.
- Só 4 das 6 variáveis têm limiar em `active_assets.json`; as outras 2 não geram alerta.
- O PDF é um catálogo comercial WEG: não traz procedimento de troubleshooting passo a passo, então parte das perguntas
  práticas **não tem resposta no corpus** — a abstenção correta é parte do resultado, não falha.
- Modelos OpenRouter gratuitos têm limite de taxa e podem sair do ar: por isso cache em `data/saida/cache_llm.jsonl`.
- A avaliação usa um juiz de 12B e tem as 5 perguntas fora do escopo só no `dev`; os limites estão em `specs/02.03-avaliacao-rag.md` §2.7 e `specs/02.04-cenarios-e-limites.md` §2.4.

---

# 9. Contrato de manutenção desta spec

- **Alvo de tamanho:** ≤ 200 linhas preenchidas. Estourou? O conteúdo pertence a uma spec fixa — mova e aponte.
- **Referencie, nunca duplique.** Esta spec é um **mapa**, não território.
- **Ponteiro órfão é defeito.** Toda spec citada existe; todo comando citado roda.
- **Só o revisor edita**, e só na síntese de uma plan aprovada ou no preenchimento direto, a pedido do usuário.
- **Sincronia obrigatória:** se uma plan mudou stack, fronteira ou regra, a mesma plan atualiza esta spec.
  Contexto desatualizado é pior que contexto ausente — o agente confia nele.
