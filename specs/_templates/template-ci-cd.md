---
tipo: "arquitetura"
familia: "FF" # Opcional; só com famílias declaradas.
titulo: "CI/CD — verificação, versão e publicação"
dominio: "Infraestrutura"
status: "🟢 Vigente" # Opções: 🟢 Vigente, 🔴 Obsoleto
tags: ["arquitetura", "ci-cd", "github-actions", "versao"]
relacionados: [] # SÓ specs fixas (specs/ · arquitetura/ · adr/). NUNCA uma plan — ela some na síntese.
---

> **Molde da spec de CI/CD.** Sem famílias, `arquitetura/ci-cd.md`; com famílias, `arquitetura/FF.NN-ci-cd.md`.
> O `/ci1-implementar` instala o pipeline (skills `ci-padrao`, `ci-verificacao`, `ci-versionamento`, `ci-protecao`);
> quem grava aqui o que o projeto escolheu é o revisor. Descreva como o pipeline **é** neste projeto; a **regra** mora na skill dona e a lei em
> `arquitetura/05-ci-cd.md` — esta spec **aponta**, nunca copia. Nunca guarde token nem valor de segredo, só o nome da
> variável e onde mora. Seção que não se aplica fica com "Não se aplica" e o motivo.

# 1. Estágio e tipo

Dono: `ci-versionamento` (`references/estagio-e-nivel.md`). Lei: `05-ci-cd.md` §4.

| Item | Valor |
|---|---|
| Arquivo | `config/release.json` |
| Estágio (`stage`) | <development / production> |
| Tipo (`kind`) | <system / library> |
| Virada para produção | <ainda não / AAAA-MM-DD, pela `meta-marco-0`> |
| Workflows instalados | <o que `node tools/ci-install.mjs --check` confirma para este estágio × tipo> |

# 2. Fluxo de branches

Dono: `ci-versionamento`. Lei: `05-ci-cd.md` §2.

| Branch | Papel | Entra por |
|---|---|---|
| `dev/<nome>` | trabalho de cada pessoa; permanente | commit local e push |
| `develop` | integração; branch padrão do GitHub | PR vindo de `dev/<nome>`, merge commit |
| `main` | o que foi lançado | PR de versão vindo só da `develop`, merge commit |

Desvios deste projeto: <nenhum / o desvio e o motivo>.

# 3. Verificação

Dono: `ci-verificacao`. Forma dos workflows: `ci-padrao`. Lei: `05-ci-cd.md` §3 e §7.

| Job do `verify.yml` | Papel | Obrigatório |
|---|---|---|
| `source`, `stage`, `proof` | origem do PR, estágio e prova de conteúdo | <na `main`, conforme o `ci-aggregate`> |
| `checks` | gate, formato, tipos, testes, segredo, dependências, workflows, mensagens | <na `develop`; na `main` se não houver prova> |
| `version`, `migrations`, `heavy` | versão declarada, migrations, camada pesada | <no PR de versão> |
| `record` | registra a prova do conteúdo | <na `develop`> |
| `verify` | agregador; **o único check exigido** pela proteção | sim |

- Checagens do projeto além das do template: <nenhuma / qual, em que camada, em `npm run ci:<nome>` ou no `verify.py`>.
- Segurança quinzenal (`security.yml`): <sim, em produção / não se aplica>.

# 4. Versão e tags

Dono: `ci-versionamento`. Lei: `05-ci-cd.md` §5.

| Item | Valor |
|---|---|
| Convenção de commit | Conventional Commits; o nível calculado é o piso |
| Declaração da versão | `CHANGELOG.md`, por `release:prepare` |
| Abertura do PR de versão | `release:open` (nunca à mão) |
| Tag | <sistema: criada pela CI depois de o servidor confirmar / lib: criada pela CI no merge / development: não há> |
| Versão atual | <X.Y.Z / nenhuma> |

# 5. Publicação e reversão

Dono do destino: <`docker-producao` (Docker) / `ci-versionamento` (lib, por tag)>.

| Item | Valor |
|---|---|
| Destino | <Docker em servidor / lib por tag> |
| Quem dispara | <variável `PUBLISHERS` (logins) / o merge do PR de versão> |
| Confirmação | <rota de estado `<URL>` / teste de instalação> |
| Reversão | <`publish.yml` com `operation: rollback` / próxima versão (tag é imutável)> |
| Detalhe da operação | <`arquitetura/FF.NN-operacao.md` (molde `template-operacao`) / não se aplica> |

# 6. Proteção do repositório

Dono: `ci-protecao`. Lei: `05-ci-cd.md` §6 e §8.

| Item | Valor |
|---|---|
| Arquivo desejado | `config/github.json` |
| Modo (`protectionMode`) | <ruleset / no-ruleset> e o motivo: <plano do repositório> |
| Desejado × efetivo | <última conferência `ci-settings --check --scope full`: AAAA-MM-DD, resultado> |
| Itens `unverified` | <nenhum / quais e quem pode resolver> |
| Quem tem admin | <logins> |
| Dono da organização | <login> |

# 7. Exceções registradas

Dono: `ci-padrao` (`references/excecoes.md`). Cada exceção tem regra, linha, motivo e quem aprovou.

| Arquivo:linha | Regra | Motivo | Aprovada por | Data |
|---|---|---|---|---|
| <`.github/workflows/x.yml:N`> | <rule-id> | <motivo concreto> | <login> | <AAAA-MM-DD> |

Nenhuma exceção em `verify.yml`. Sem exceção: "Nenhuma".
