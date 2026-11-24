---
tipo: "processo"
titulo: "Índice de Execução — Mapa das Plans"
dominio: "Governança de Specs (SDD)"
status: "🟢 Vigente"
tags: ["processo", "indice", "sdd"]
relacionados: ["[[00-contexto]]", "[[00-backlog]]", "[[00-prompt-revisor]]", "[[00-prompt-executor]]"]
proximo_numero_plan: {"01": 3, "02": 6} # Com famílias: mapa família → NN; simples: escalar NN único. Só sobe, nunca reaproveitado — ver §4.
---

# 0. O que é este arquivo

O **mapa do trabalho em andamento**. Responde a duas perguntas, sempre:

1. **O que executo agora?** (a plan `🟡 Em execução` mais acima na fila: liberada, com o prompt já emitido)
2. **O que está em jogo e não terminou?** (todo o resto da tabela)

**Este arquivo não é histórico.** Ele espelha, linha a linha, as plans que existem em `specs/plan/` — e uma
plan só existe enquanto não foi sintetizada. **Sintetizar remove a plan e a linha, na mesma ação**
([[00-prompt-revisor]] §7.4): a verdade passa a viver na spec fixa de destino, e o rastro completo, no Git.

Por isso o tamanho deste arquivo é limitado pelo **trabalho aberto**, não pela idade do repositório. Índice
que cresce é índice quebrado.

| Não confunda | É |
|---|---|
| [[00-indice]] | o que **está sendo feito** — uma linha por plan viva |
| [[00-backlog]] | o que foi **notado e não agendado** — sem status, sem fila, ninguém executa |

> ⚠️ **Este arquivo é um molde com instruções embutidas.** O bloco `> **Como escrever:**` **permanece** no
> arquivo como contrato de manutenção; a tabela começa vazia e é mantida pelo **agente revisor**.

**Quem escreve/atualiza:** exclusivamente o **agente revisor** ([[00-prompt-revisor]]).
**Quando atualizar:** ao criar uma plan (nova linha + contador do esquema declarado), mudar status ou
**sintetizar** (remover linha e arquivo juntos). **Status vive aqui e na plan, gravado na mesma ação** — salvo o
`🟠`, que o executor grava só na plan e o revisor leva para cá junto do veredito. Regenere
`panorama/00-resumo.md` na mesma ação só se o repositório adota panorama.

---

# 1. Fila de execução

> **Como escrever:** uma linha por plan que existe em disco, **em ordem de execução** — a ordem da tabela
> **é** o plano; não use a numeração para ordenar. Colunas obrigatórias, nesta ordem:
>
> - **#** — posição na fila (1, 2, 3…). Reordenável.
> - **Plan** — link relativo: `[plan-<número>-slug](plan/plan-<número>-slug.md)`; padrão `plan-NN`, ou `plan-FF.NN` (com famílias).
> - **Objetivo** — uma linha, no infinitivo. O que muda no sistema.
> - **Depende de** — número da plan que precisa estar sintetizada antes, ou `—`.
> - **Status** — um dos valores da §2. **Igual** ao frontmatter da plan, salvo a janela `🟠` × `🟡` ou `🔵` (§2).
> - **Destino** — para onde o conteúdo será sintetizado (§3).
>
> Quando a plan é sintetizada, **a linha sai desta tabela e o arquivo sai do disco**, juntos. Não há segunda
> tabela para onde migrar: o que acabou não ocupa mais espaço aqui.

| # | Plan | Objetivo | Depende de | Status | Destino |
|---|---|---|---|---|---|
| 2 | [plan-01.02-classificacao-e-relatorio-rastreavel](plan/plan-01.02-classificacao-e-relatorio-rastreavel.md) | Classificar eventos em 5 categorias e gerar relatório rastreável (F1, F2) | — | 🔴 A executar | specs/01.02 + 00-contexto |
| 3 | [plan-02.01-rag-com-pagina-secao-e-estado](plan/plan-02.01-rag-com-pagina-secao-e-estado.md) | Construir RAG com página, seção e estado operacional na busca (F3, F4) | plan-01.02 | 🔴 A executar | specs/02.01 + 00-contexto |
| 4 | [plan-02.02-assistente-de-troubleshooting](plan/plan-02.02-assistente-de-troubleshooting.md) | Construir o assistente com citação, confiança calculada e abstenção | plan-02.01 | 🔴 A executar | specs/02.02 + 00-contexto |
| 5 | [plan-02.03-avaliacao-confiavel-do-rag-e-do-juiz](plan/plan-02.03-avaliacao-confiavel-do-rag-e-do-juiz.md) | Avaliar o RAG com gabarito de página e juiz por afirmação (F5, F6) | plan-02.02 | 🔴 A executar | specs/02.03 + 00-contexto |
| 6 | [plan-02.04-cenarios-e-limites](plan/plan-02.04-cenarios-e-limites.md) | Demonstrar os três cenários em separado e documentar os limites (F7) | plan-02.03 | 🔴 A executar | specs/02.04 + 00-contexto |
| 7 | [plan-02.05-entrega](plan/plan-02.05-entrega.md) | Preparar a entrega: documento final, README, roteiro do vídeo e notebooks executados | plan-02.04 | 🔴 A executar | — |

---

# 2. Legenda de status

| Status | Significado | Quem marca |
|---|---|---|
| 🔴 A executar | Plan escrita com dependência aberta: **sem** prompt de execução, aguarda a dependência ser sintetizada. | revisor, na plan e no índice, ao criar a plan com dependência aberta |
| 🟡 Em execução | Plan liberada, com o prompt de execução entregue; executor trabalhando. A plan liberada já nasce assim. | revisor, na plan e no índice, ao emitir o prompt |
| 🟠 Em revisão | Execução concluída no worktree, aguardando veredito. | executor, **só na plan**, ao entregar; revisor, **no índice**, junto do veredito |
| 🔵 Em correção | Reprovada. Prompt de correção emitido, executor refazendo. | revisor, na plan e no índice, ao reprovar |
| ⛔ Bloqueada | Impedida por dependência externa ou decisão pendente. **Exige motivo** na coluna Objetivo. | revisor |
| 🟢 Aprovada | Verificada. Liberada para commit; a síntese vem depois do commit do veredito, sem pedir autorização. | revisor, na plan e no índice, ao aprovar |

> Um status avança na ordem `🔴 → 🟡 → 🟠 → (🔵 ⇄ 🟠) → 🟢 → (sintetizada e removida)`; a plan liberada na criação
> começa em `🟡`. **🔵 não volta para 🔴** — correção não é execução nova; a plan e o histórico de vereditos são os
> mesmos.
>
> **A janela `🟠` × `🟡` ou `🔵`:** entre a entrega do executor e o veredito, a plan diz `🟠` e o índice ainda diz
> `🟡` (primeira entrega) ou `🔵` (entrega de uma correção).
> Não é divergência: é o intervalo normal, e o revisor leva o status ao índice junto do veredito. A `spec-revisao`
> o informa como `awaiting-review`, sem contá-lo como achado.
>
> **`🟢` é o estado mais curto que existe aqui.** Ele dura o tempo de o usuário commitar o veredito — minutos,
> na mesma conversa. Commitou e avisou, o revisor sintetiza, apaga a plan e apaga esta linha. Um
> `🟢` que passou o dia parado é sinal de commit do veredito não feito, não de estado normal.
>
> **`⛔` não é depósito.** Plan bloqueada há tempo demais deixou de ser trabalho aberto: ou o impedimento caiu
> e ela volta para `🔴`, ou ela não vai acontecer. No segundo caso o revisor **não remove nada** — ele leva o
> caso ao usuário e desce para o [[00-backlog]] o que sobrou de útil; a **remoção é manual, do usuário**,
> quando for o caso. Abandono silencioso é o que faz índice virar cemitério.

---

# 3. Coluna *Destino* — valores válidos

Toda plan declara, **desde o momento em que é escrita**, para onde seu conteúdo será sintetizado:

| Valor | Quando usar |
|---|---|
| `arquitetura/<nome>.md` | Mudou design estrutural, stack, fronteira de módulo, contrato de API. |
| `specs/<nome>.md` | Mudou regra de negócio ou comportamento de funcionalidade. |
| `00-contexto.md` | Mudou regra inegociável, stack ou mapa de roteamento. |
| `adr/NNN-<nome>.md` | Houve **decisão com alternativa real descartada**. Passa a régua de três perguntas do [[00-prompt-revisor]] §5.2 — se não passa, não é ADR. **É o destino mais raro.** |
| **`—` (nenhum)** | Execução que não altera verdade documentada: correção de bug sem mudança de regra, refactor de conformidade, ajuste de build/CI, limpeza. |

> Vários destinos são permitidos (`arquitetura/02.03-api.md` + `adr/004-...`). **`—` é a resposta mais comum** —
> não invente destino para preencher a coluna, e não promova uma escolha óbvia a ADR só porque o menu oferece.
>
> Se a plan tem destino `—`, ela ainda passa pela síntese: o revisor confirma que não havia o que transportar
> e **remove a plan do mesmo jeito**. Destino `—` não é motivo para o arquivo ficar.

---

# 4. Regras de manutenção

- **Numeração segue `00-contexto`.** Padrão simples: `plan-NN` com contador escalar único. Com famílias: `plan-FF.NN`
  (com famílias), contador por família no mapa. O esquema declarado é o que o `proximo_numero_plan` mostra
  (escalar = `plan-NN`; mapa = `plan-FF.NN`), e as ferramentas (`spec-revisao`, `spec-panorama`) leem dele. Em
  ambos, monotônico e definitivo: nunca renumere nem reaproveite; incremente na criação, nunca escaneie `plan/`. O
  namespace das plans é separado das specs.
- **Famílias só se adotadas:** use o catálogo ([[00-planejamento]] §1); família nova exige aprovação do usuário.
- **Uma linha aqui = um arquivo em `plan/`.** Sempre. Linha sem arquivo é índice mentindo; arquivo sem linha
  é trabalho invisível. Divergiu? A **plan** é a fonte da verdade e este índice está errado — corrija aqui.
- **Status e arquivo andam juntos.** Aprovou → `🟢` na plan **e** aqui. Sintetizou → spec fixa atualizada,
  `git rm` da plan **e** remoção da linha, na mesma passada. Nunca um sem o outro.
- **Antes de SINTETIZAR, confirme que a plan aprovada está commitada.** `git show HEAD:<caminho-da-plan>`
  tem de trazer o bloco `## Veredito — … — 🟢 Aprovado`. Sem ele, o estado aprovado nunca foi guardado: removê-la
  seria **perda total**, e um `git log` não vazio não basta (uma plan commitada ainda `🔴` passaria). A
  checagem vem **antes** de escrever qualquer coisa — o usuário commita a plan aprovada primeiro, e só então a
  síntese acontece inteira, **sem bloco na plan** (o rastro vai na resposta do revisor, para a mensagem do
  commit). Nunca sintetize agora para remover depois: isso cria uma plan sintetizada em disco sem status que a
  descreva.
- **Dependência é contrato:** a plan cuja dependência ainda está aberta nasce `🔴`, **sem** prompt; só se libera
  (`🟡`, com o prompt na mesma ação) quando a dependência sai da tabela. Dependência
  que sumiu da tabela **foi sintetizada** — logo já está embutida na spec fixa de destino; atualize a dependente
  para apontar à spec. **Plan sintetizada nunca fica em disco para servir de contexto a outra**: se
  a dependente precisa de algo que a spec fixa não carrega, a síntese estava incompleta — o revisor a
  completa **antes** de remover ([[00-prompt-revisor]] §7.4).
- **Plan nunca referencia outra plan como fonte de conteúdo** — só `depende_de`, que é ordem de execução.
- **Uma plan `🟡 Em execução` por vez**, salvo plans comprovadamente disjuntas (arquivos sem interseção) — o
  revisor declara a disjunção ao liberar as duas.
- **Achado não entra aqui.** Vai para o [[00-backlog]]. Este arquivo é só trabalho liberado.
- **Só o revisor edita este arquivo.** O **executor nunca o toca**; ele escreve apenas na plan que executou.
