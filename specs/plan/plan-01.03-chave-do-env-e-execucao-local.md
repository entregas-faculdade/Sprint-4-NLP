---
tipo: "plan"
familia: "01"
titulo: "Ler a chave do OpenRouter do .env da raiz e remover o Colab do notebook"
dominio: "Sprint 3 — Alertas e classificação"
status: "🟢 Aprovada"
prioridade: "Alta"
tags: ["plan", "chave", "execucao-local", "llm"]
relacionados: ["[[00-contexto]]", "[[01.01-alertas-deterministicos]]", "[[01.02-classificacao-e-relatorio]]"]
depende_de: ""
destino_sintese: "specs/01.01-alertas-deterministicos.md + 00-contexto.md"
---

# 1. Objetivo

Toda execução é **local** e a chave do OpenRouter vem do `.env` da raiz, sem o usuário copiá-la para o ambiente da sessão. O
carregador da chave deixa de depender de Colab, e o notebook da Sprint 3 deixa de clonar o repositório e de instalar pacotes.

# 2. Contexto

- Decisão do dono (2026-11-24): "toda execução será local; os notebooks usam a chave do env da raiz". Hoje `load_openrouter_api_key()`
  (`src/pln/llm.py`) tenta `google.colab.userdata` e depois a variável `OPENROUTER_API_KEY`; o `.env` não é lido. O `.env` e o
  `.env.example` do projeto usam o nome **`OPEN-ROUTER-API-KEY`** (com hífens) e também `GROQ-API-KEY`; o `.env` é ignorado pelo Git.
- O notebook `sprint3_pln_alertas.ipynb` (seção 1) ainda tem texto e código de Colab: clona o repositório e roda `%pip install`.
- A spec `01.01-alertas-deterministicos.md` §2.5 diz que "`.env` não é lido pelo código" e cita Colab `userdata`: esta plan inverte isso.
- Sem dependência nova: `python-dotenv` não entra (o nome com hífen e o formato simples cabem num leitor de poucas linhas).

# 3. Escopo

## 3.1 Dentro
- `src/pln/config.py` — constantes novas: `ENV_FILE` (`ROOT_DIR / ".env"`) e `NOMES_VARIAVEL_CHAVE` com os dois nomes aceitos
- `src/pln/llm.py` — `load_openrouter_api_key` reescrita (sem ramo Colab) e um leitor do `.env`
- `tests/test_llm.py` — testes novos do carregador
- `notebooks/sprint3_pln_alertas.ipynb` — só as células 1 (markdown) e 2 (código) da seção "Configuração do ambiente"
- `data/saida/` — nenhum arquivo muda (o cache atende todas as chamadas)

## 3.2 Fora
- Regras de alerta, classificação, relatório, verificadores e qualquer outro arquivo de `src/pln/`, `tools/nb_check.py`
- `notebooks/sprint4_pln_rag.ipynb` (reconstruído na plan 02.01), `.env`, `.env.example`, `requirements.txt`, `specs/`

# 4. Referências obrigatórias

| Tipo | Referência | Por quê |
|---|---|---|
| Spec fixa | `specs/01.01-alertas-deterministicos.md` §2.5 · `specs/01.02-classificacao-e-relatorio.md` | o cliente e como o notebook o usa |
| Contexto | `00-contexto.md` §2, §7 e §8 | a regra de segredos e a pendência desta plan |
| **Skill** | `padrao-escrita` + `padrao-python` · `test-unitario` · `code-auditoria-padrao` | escrita, testes, gate |
| Código | `src/pln/llm.py` · `src/pln/config.py` · `tests/test_llm.py` | onde mexer |

# 5. Instruções de execução

1. [dirigido] **Constantes** em `config.py`: `ENV_FILE = ROOT_DIR / ".env"` e `NOMES_VARIAVEL_CHAVE = ("OPENROUTER_API_KEY", "OPEN-ROUTER-API-KEY")`.
2. [dirigido] **Leitor do `.env`** em `llm.py`, função pequena e testável (por exemplo `_read_env_file(path) -> dict[str, str]`): uma linha
   por variável no formato `NOME=valor`; ignora linhas vazias e as que começam com `#`; aceita o prefixo `export `; remove espaços
   nas pontas e um par de aspas simples ou duplas em volta do valor; não expande `$VAR`; arquivo ausente → dicionário vazio.
3. [dirigido] **`load_openrouter_api_key(env_file: Path = ENV_FILE) -> str`**: ordem de busca, parando no primeiro valor não vazio —
   (a) variável de ambiente `OPENROUTER_API_KEY`; (b) variável de ambiente `OPEN-ROUTER-API-KEY`; (c) o `.env` com cada nome de
   `NOMES_VARIAVEL_CHAVE`, na ordem. Nenhum valor encontrado → `RuntimeError` cuja mensagem cita **os nomes e o caminho do `.env`**, nunca
   um valor. Remover por completo o ramo `google.colab` e a docstring antiga. A chave nunca é impressa, logada nem entra em `repr`.
4. [dirigido] **Testes** (skill `test-unitario`; `tmp_path` e `monkeypatch.setenv/delenv`; nada de rede): variável de ambiente vence o
   `.env`; `.env` com `OPEN-ROUTER-API-KEY`; com `OPENROUTER_API_KEY`; com `export`, aspas e comentário; valor vazio é ignorado e a busca
   segue; ausência em todo lugar → `RuntimeError` com os nomes e **sem** o valor de nenhuma variável do teste; o valor lido nunca aparece
   em `caplog`, na saída capturada nem no arquivo de cache. Os testes existentes de `create_openrouter_client` continuam passando.
5. [dirigido] **Notebook, células 1 e 2** (seção "Configuração do ambiente"): o markdown passa a dizer que a execução é local, que as
   dependências vêm de `pip install -r requirements.txt` (feito antes de abrir o notebook) e que a chave é lida do `.env` da raiz; a célula
   de código **remove** `REPOSITORY_URL`, `REPOSITORY_DIRECTORY`, o `git clone`, o `subprocess` e o `%pip install`, mantendo: achar a raiz
   do repositório subindo a partir do diretório atual, falhar com `RuntimeError` se não achar, `sys.path`, `os.chdir`, e o bloco que
   define `openrouter_key_available` e imprime só `chave carregada: True/False`. Sem saídas na entrega (a execução é do revisor).
6. [dirigido] Rodar `python -m pytest tests -q`, `python tools/nb_check.py notebooks/sprint3_pln_alertas.ipynb` e `code-auditoria-padrao`
   nos arquivos tocados. **Não executar o notebook, não chamar a API, não ler nem imprimir o `.env`** e **nunca** usar `git checkout`/
   `git restore` em arquivo do projeto.

# 6. Critérios de aceite

- [ ] `load_openrouter_api_key` lê, nesta ordem, as duas variáveis de ambiente e depois o `.env` da raiz com os dois nomes; sem ramo Colab.
- [ ] Sem chave em lugar nenhum → `RuntimeError` com os nomes e o caminho, sem nenhum valor.
- [ ] A chave não aparece em log, saída, `repr` nem cache (teste).
- [ ] O notebook da Sprint 3 não tem `git clone`, `subprocess`, `%pip install` nem menção a Colab/Secrets; `nb_check` válido sem saídas.
- [ ] Nenhuma dependência nova; só os arquivos de §3.1 mudam.
- [ ] **Fase B (local, sem copiar a chave para o ambiente):** notebook executado sem erro, `chave carregada: True`, `cache_llm.jsonl`
      com as mesmas 71 linhas (zero chamada nova), as três saídas da 01.02 e `alertas.json` idênticas às commitadas, números da
      classificação e dos relatórios iguais aos da spec 01.02; `nb_check --executado` verde.
- [ ] Ambiente e worktree limpos; testes do escopo verdes; `code-auditoria-padrao` sem violação nova.

# 7. Como verificar (uso do revisor)

- **Nível:** `ampla` (muda `config.py` e `llm.py`, usados por `alertas.py`, `classificacao.py` e `relatorio.py`).
- `git diff --stat` → só os arquivos de §3.1.
- **Fase A:** `python -m pytest tests -q` · `python tools/nb_check.py notebooks/sprint3_pln_alertas.ipynb` · `code-auditoria-padrao` ·
  leitura de `llm.py` (sem `google.colab`, sem `print` de chave) · `grep -i "colab\|userdata\|git clone\|%pip"` no notebook → vazio.
- **Fase B:** o usuário executa o notebook em venv limpo **sem** definir `OPENROUTER_API_KEY` na sessão, sem `--allow-errors`;
  `python tools/nb_check.py notebooks/sprint3_pln_alertas.ipynb --executado` · leitura das saídas · `git diff --stat data/saida/`
  (só pode aparecer `classificacao.json`/relatórios se o conteúdo mudar; `cache_llm.jsonl` sem diferença).
- **Gate:** `nenhum`.

# 8. Destino da síntese

**Destino:** `specs/01.01-alertas-deterministicos.md` + `00-contexto.md`

Texto para transporte: na spec 01.01 §2.5, a chave vem da variável de ambiente (`OPENROUTER_API_KEY` ou `OPEN-ROUTER-API-KEY`) e,
depois, do `.env` da raiz, sem Colab; erro sem valor. Em `00-contexto.md`: tirar a pendência da §8, ajustar a §2 (o código já lê o
`.env`) e a receita de execução local da §5 (a chave não precisa mais ser copiada para a sessão).

---

# 9. Resumo da execução

<!-- Preenchido pelo EXECUTOR. Append-only: cada rodada acrescenta um bloco novo; nada é removido. -->

## Resumo da execução — 2026-11-24

**Resultado:** Concluído com pendências

**O que foi feito**
- Adicionei `ENV_FILE` e `NOMES_VARIAVEL_CHAVE` em `src/pln/config.py:11` para centralizar o caminho e os nomes aceitos.
- Implementei o leitor do `.env` e a precedência de busca em `src/pln/llm.py:68` e `src/pln/llm.py:97`; a mensagem sem chave contém os nomes e o caminho, sem valores.
- Adicionei testes do carregador, parsing, precedência, erro sem segredo e não exposição em `tests/test_llm.py:79` e `tests/test_llm.py:290`.
- Atualizei apenas as células `alerts-01` e `alerts-02` de `notebooks/sprint3_pln_alertas.ipynb`; removi clone, instalação e saídas da célula de configuração.

**Arquivos alterados**
| Arquivo | Natureza | O que mudou |
|---|---|---|
| `src/pln/config.py` | alterado | Caminho `.env` e nomes aceitos para a chave. |
| `src/pln/llm.py` | alterado | Leitura simples do `.env` e busca ambiente → arquivo. |
| `tests/test_llm.py` | alterado | Cobertura do carregador e da proteção do segredo. |
| `notebooks/sprint3_pln_alertas.ipynb` | alterado | Instruções locais e célula de configuração sem Colab, clone, instalação ou saídas. |
| `specs/plan/plan-01.03-chave-do-env-e-execucao-local.md` | alterado | Resumo append-only e status `Em revisão`. |

**Verificações executadas**
- `python -m pytest tests -q` com Python 3.11 local → 66 passaram, 1 aviso de depreciação, 5,23 s. O Python padrão da sessão (3.14) não tinha `pytest`.
- `python tools/nb_check.py notebooks/sprint3_pln_alertas.ipynb` com Python 3.11 → falhou na célula 4, que já tinha `execution_count` e saídas antes desta execução. O Python 3.14 não tinha `nbformat`.
- Validador `padrao-python` em `src/pln/llm.py` e `tests/test_llm.py` → nenhum achado. Em `src/pln/config.py` → 1 achado heurístico de baixa confiança para a URL preexistente em `config.py:93`.
- Busca `colab|userdata|git clone|%pip` no notebook → nenhuma ocorrência.

**Estado inicial do worktree:** `git status --short` vazio; branch `main`, declarada como branch de trabalho direta em `00-contexto.md`. O Git avisou que não conseguiu acessar o ignore global e `.pytest_cache`.

**Ambiente após a verificação:** snapshot criado e removido. O diff registrou 0 diretórios temporários novos e nenhuma mudança em recursos Docker; 7 processos apareceram, 39 desapareceram e 1 entrada de `system_temp` apareceu. A ferramenta não atribui autoria a essas mudanças; não encerrei nenhum item.

**Critérios de aceite**
- [x] Busca ordenada pelas duas variáveis de ambiente e depois pelos dois nomes no `.env`, sem Colab — evidência: `src/pln/llm.py:97` e testes em `tests/test_llm.py:79`.
- [x] Erro sem chave inclui os nomes e o caminho sem incluir valores — evidência: `src/pln/llm.py:109` e `tests/test_llm.py:144`.
- [x] A chave não aparece em logs, saída capturada, `repr` do cliente ou cache — evidência: `tests/test_llm.py:290`.
- [ ] Notebook aprovado pelo `nb_check` sem saídas — pendente: o verificador exige que todas as células de código estejam sem execução; a célula 4 e outras posteriores já tinham saídas, fora do escopo restrito às células 1 e 2.
- [x] Nenhuma dependência nova; os quatro arquivos de código/teste/notebook previstos foram os únicos arquivos de produto alterados — evidência: `git diff --stat`.
- [ ] Fase B local — não executada conforme a instrução da plan, que proíbe executar o notebook e deixa essa execução para o revisor/usuário.
- [x] Suíte passou e o validador não apontou achado novo nos arquivos alterados; a URL em `config.py:93` é preexistente e de baixa confiança.
- [ ] Ambiente limpo — pendente de atribuição: o diff registrou uma entrada nova em `system_temp` e processos sem autoria confirmada; nenhum item foi removido.

**Decisões e suposições**
- As specs fixas citadas pela plan foram lidas nos caminhos existentes `specs/specs/01.01-alertas-deterministicos.md` e `specs/specs/01.02-classificacao-e-relatorio.md`.
- Mantive a edição do notebook nas células autorizadas. Não removi saídas das demais células sem autorização para ampliar esse escopo.
- Não li o `.env` real, não executei o notebook e não chamei a API.

**Achados fora do escopo (não corrigidos)**
- `src/pln/config.py:93` — URL existente sinalizada pelo validador como `hardcoded`, com confiança baixa; não foi introduzida por esta tarefa.

**Pendências / riscos**
- O `nb_check` permanece reprovado pelas saídas preexistentes das células fora do escopo. A execução com a plan estritamente aplicada não pode satisfazer esse comando sem alterar células adicionais.
- A Fase B precisa ser executada e conferida pelo revisor/usuário.
- O diff do ambiente mostrou processos e uma entrada de temporário sem autoria inferível; por isso o ambiente não foi declarado limpo.
- Cobertura percentual não foi medida; a verificação prescrita pela plan não incluiu relatório de cobertura.

## Complemento da execução — 2026-11-24

**Resultado:** Concluído com pendências

**O que foi feito**
- Após autorização do usuário, removi as saídas, contagens de execução e metadados de execução das 14 células de código do notebook. As fontes fora de `alerts-01` e `alerts-02` permaneceram intactas.

**Arquivos alterados**
| Arquivo | Natureza | O que mudou |
|---|---|---|
| `notebooks/sprint3_pln_alertas.ipynb` | alterado | As 14 células de código ficaram sem saídas ou contagem de execução. |
| `specs/plan/plan-01.03-chave-do-env-e-execucao-local.md` | alterado | Este complemento append-only registra a autorização e a verificação. |

**Verificações executadas**
- `MPLBACKEND=Agg` + Python 3.11 `tools/nb_check.py notebooks/sprint3_pln_alertas.ipynb` → Notebook válido. A primeira tentativa aguardou em `plt.show()` e foi interrompida; a repetição usou backend não interativo.
- Inspeção estrutural do JSON → 14 células de código sem `outputs`, `execution_count` ou metadados `execution`.
- Busca `colab|userdata|git clone|%pip` no notebook → nenhuma ocorrência.
- A suíte Python não foi repetida: apenas saídas e metadados do notebook mudaram desde os 66 testes aprovados.

**Estado inicial do worktree:** já continha as quatro alterações de produto e o resumo da execução anterior; nenhuma outra alteração foi detectada.

**Ambiente após a verificação:** snapshot criado e removido. O diff registrou 0 diretórios temporários novos e nenhuma mudança em recursos Docker; 11 processos apareceram, 5 desapareceram e 1 entrada de `system_temp` apareceu. A ferramenta não atribui autoria a essas mudanças; não encerrei nenhum item.

**Critérios de aceite**
- [x] Notebook sem saídas e aprovado pelo `nb_check` — evidência: 14 células limpas e saída `Notebook válido`.
- [ ] Fase B local — continua pendente para o revisor/usuário; não executei o notebook.
- [ ] Ambiente limpo — processos e entrada de `system_temp` sem autoria confirmada; nenhum foi removido.

**Decisões e suposições**
- A autorização do usuário permitiu limpar as saídas das células fora do escopo inicial; os respectivos códigos-fonte não foram alterados.
- O `nb_check` executou somente as células marcadas `offline`, sem chamada à API; o notebook inteiro não foi executado.

**Pendências / riscos**
- A Fase B precisa ser executada e conferida pelo revisor/usuário.
- O diff do ambiente ainda contém mudanças sem autoria inferível; por isso o ambiente não foi declarado limpo.

## Registro após a conferência final — 2026-11-24

**Resultado:** Concluído com pendências

**O que foi feito**
- Comparei novamente o ambiente após conferir o worktree; não alterei arquivos de produto nesta etapa.

**Arquivos alterados**
| Arquivo | Natureza | O que mudou |
|---|---|---|
| `specs/plan/plan-01.03-chave-do-env-e-execucao-local.md` | alterado | Registro append-only da fotografia final do ambiente. |

**Verificações executadas**
- `environment.py diff` → 14 processos apareceram, 4 desapareceram; 0 diretórios temporários, 0 entradas novas em `system_temp` e nenhuma mudança em recursos Docker.

**Estado inicial do worktree:** apenas os arquivos esperados da execução estavam alterados; branch `main`.

**Ambiente após a verificação:** snapshot removido; nenhum diretório temporário ou recurso Docker novo. Processos observados sem autoria confirmada não foram encerrados.

**Critérios de aceite**
- [x] Nenhum arquivo de produto fora do escopo foi alterado — evidência: `git status --short` e `git diff --stat`.
- [ ] Ambiente limpo — autoria dos processos observados não pôde ser confirmada.

**Decisões e suposições**
- Preservei processos sem autoria confirmada conforme o procedimento de ambiente.

**Achados fora do escopo (não corrigidos)**
- Nenhum novo achado nesta etapa.

**Pendências / riscos**
- O ambiente não foi declarado limpo porque não é seguro atribuir os processos observados a esta tarefa.

---

# 10. Veredito

<!-- Preenchido pelo REVISOR. Append-only: um bloco por rodada, com o que foi verificado e como. -->

## Veredito — 2026-11-24 — 🟢 Aprovado (rodada 1, Fase A + Fase B)

**Escopo da rodada:** carregador da chave do `.env`, notebook da Sprint 3 sem Colab, e a execução local do notebook **sem** copiar a chave para o ambiente da sessão.

**O que foi verificado e como**
- `git diff --stat`: só `config.py`, `llm.py`, `tests/test_llm.py`, o notebook e a plan; `data/` sem diferença. Nenhuma dependência nova.
- `python -m pytest tests -q` → 66 passaram. `python tools/nb_check.py notebooks/sprint3_pln_alertas.ipynb` → válido (sem saídas) e `--executado` → válido (exit 0).
- Leitura de `llm.py`: sem `google.colab` nem `print` de chave; erro sem chave cita os nomes e o caminho, nunca um valor. Sonda com `.env` temporário e valores fictícios: variável de ambiente vence o arquivo, `OPENROUTER_API_KEY` vence `OPEN-ROUTER-API-KEY`, `export`, aspas e espaços aceitos, valor vazio ignorado, valor com `=` preservado, arquivo ausente → erro com nomes e caminho.
- Notebook: só as células 1 e 2 mudaram de fonte (27 idênticas ao `HEAD`); `colab|userdata|git clone|%pip|subprocess` → 0 ocorrências. As saídas limpas pelo executor com autorização do usuário foram regeneradas na Fase B.
- **Fase B:** o usuário executou em venv limpo, sem variável de ambiente da chave e sem `--allow-errors`. Notebook com 14 células de código, `execution_count` 1 a 14, nenhum erro; célula 2 imprime só `chave carregada: True`, sem ruído de `pip`. As saídas das células 4 a 28 são **idênticas** às do commit anterior (classificação, relatórios, ROUGE e exportação inclusive). `cache_llm.jsonl` segue com 71 linhas (nenhuma chamada nova) e `git diff --stat data/saida` vazio. 0 ocorrências de `sk-or` ou `Bearer` no notebook.

**Observações (não reprovam)**
- O executor entregou 3 blocos na §9 (resumo, complemento, registro final); o primeiro declarou o `nb_check` reprovado só por saídas fora do escopo, e o segundo o resolveu com autorização expressa do usuário. Coerente com a instrução da plan.
- O teste `test_legacy_environment_api_key_name_is_supported` chama de "legado" o nome `OPEN-ROUTER-API-KEY`, que é o nome oficial do projeto; só o rótulo do teste, sem efeito.
- O diff de ambiente do executor registrou processos sem autoria; não afeta nada do produto e o worktree está limpo fora dos arquivos da plan.
