---
tipo: "plan"
familia: "01"
titulo: "Ler a chave do OpenRouter do .env da raiz e remover o Colab do notebook"
dominio: "Sprint 3 — Alertas e classificação"
status: "🟡 Em execução"
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

---

# 10. Veredito

<!-- Preenchido pelo REVISOR. Append-only: um bloco por rodada, com o que foi verificado e como. -->
