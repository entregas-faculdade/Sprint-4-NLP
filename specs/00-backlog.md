---
tipo: "processo"
titulo: "Backlog — Achados Registrados, Não Agendados"
dominio: "Governança de Specs (SDD)"
status: "🟢 Vigente"
tags: ["processo", "backlog", "achados", "sdd"]
relacionados: ["[[00-indice]]", "[[00-prompt-revisor]]", "[[00-prompt-executor]]"]
---

# 0. O que é este arquivo

O lugar onde um achado **descansa**. Nem executado, nem esquecido.

Antes deste arquivo existir, um problema encontrado no meio do caminho tinha só dois destinos: virar
trabalho **agora** (uma plan nova, um ciclo inteiro) ou se perder. Como a doutrina proíbe perder, tudo
virava trabalho — e cada execução gerava as próximas, sem caso-base. Este arquivo é o caso-base.

**Um item aqui não é uma plan.** Não tem `NN`, não tem status, não entra em fila, ninguém o executa. É uma
linha dizendo *"isto existe e alguém olhou"*. Só vira trabalho quando **o usuário** manda — e aí passa pela
triagem normal ([[00-prompt-revisor]] §4) como qualquer outra demanda.

**Quem escreve:** o **revisor**, sempre. O executor **relata** achados no resumo dele (é o formato da
[[00-prompt-executor]] §5); quem transcreve para cá é o revisor, no veredito.
**Quem promove:** só o **usuário**. Nenhum agente decide sozinho que chegou a hora de um item.
**Quem remove:** quem promoveu (o item sai daqui quando vira plan ou prompt direto) — ou o revisor, ao
registrar um achado novo (§4), quando encontra um antigo que deixou de valer. O usuário pode podar a
qualquer momento.

---

# 1. A regra que este arquivo sustenta

> **Achado descoberto durante a execução da plan-N não vira trabalho antes da plan-N fechar.**

Sem exceção. Ele desce para cá, e o ciclo em andamento termina primeiro. Isso é o que impede o aninhamento:
uma execução nunca abre outra execução por dentro.

Três coisas alimentam este arquivo:

| Origem | Quem traz | Quando |
|---|---|---|
| Achado fora do escopo | executor, no resumo | o revisor transcreve no veredito |
| Divergência entre spec fixa e código | revisor, no ritual de entrada | ao encontrar |
| Ressalva relevante que não reprova a execução | revisor, no veredito | ao aprovar |

**Nada aqui é urgente por estar aqui.** Se um achado é grave a ponto de não poder esperar, ele não é backlog
— é uma demanda que o revisor leva ao usuário na hora, em texto livre, e que vira plan ou prompt direto pela
via normal.

---

# 2. A tabela

> **Como escrever:** uma linha por achado, e **uma linha só**. Se você precisa de um parágrafo, o item não é
> achado — é uma demanda; leve ao usuário.
>
> - **#** — sequencial simples. Reaproveitável: sai um, o número volta a ficar livre. Isto **não** é `plan-FF.NN`.
> - **Achado** — o que há de errado, em uma frase, com `arquivo:linha` quando existir.
> - **Origem** — `execução`, `via direta` ou `ritual`. **Nunca `plan-FF.NN`**: a plan é removida na síntese e a
>   referência morre. Saber que o achado veio de uma execução basta; de qual plan, não ajuda depois que ela sai.
> - **Registrado em** — data absoluta (`AAAA-MM-DD`).
> - **Peso** — `alto` · `médio` · `baixo`. É uma dica ao usuário, não uma fila: nada aqui é agendado.

| # | Achado | Origem | Registrado em | Peso |
|---|---|---|---|---|
| 1 | `verificar_clareza` (≤ 60 palavras por `\w+`) reprova 1.412 dos 4.477 templates reais (vibração e velocidade, ação padrão longa); o notebook só a aplica aos 9 casos de teste | execução | 2026-11-23 | médio |
| 2 | `rag.py` (serialização de tabelas): cabeçalhos multinível saem colados e repetidos por célula (`PotênciaNominal kW` na p. 5; 77 chunks da seção 5.2.1 quase só rótulo `Carga radial máxima - 60 Hz - 25 .000 horas - Fr em (kN) …`), o que dilui a busca nessas tabelas | execução | 2026-11-24 | médio |
| 3 | Notebook da plan 02.01, seção 5: com estado crítico os mesmos 4 chunks voltam na mesma ordem (só os scores mudam) e a seção 10.1 "Resistências de Aquecimento" (aquecedor anticondensação) entra no top 4 para "aquecimento do motor"; o boost de seção por estado ainda não muda a recuperação de forma útil | execução | 2026-11-25 | médio |
| 4 | `Retriever` (`score_rerank_bruto`): o escore bruto do reranker não separa bem escopo de fora de escopo — "características do sistema de ventilação" (dentro) pontua -4,24, abaixo de "população atual do Brasil" (fora, -3,03); no gabarito, p01 (dentro, -3,91) e p02 (dentro, 0,27) ficam abaixo de f01 (fora, 0,41); abstenção por limiar fixo sacrifica perguntas legítimas | execução | 2026-11-25 | médio |
| 5 | `Juiz` (`MODELO_JUIZ` de 12B): rotulou SUSTENTADA "o Pt-100 é um termistor" (o contexto separa Pt-100 de termistores PTC) e as 24 respostas ficaram com faithfulness ≈ 1,0; falso negativo de EXTERNA que a calibração de 16 casos não pegou | execução | 2026-11-25 | médio |

| 6 | `Assistente`: o gerador respondeu a frase de abstenção mesmo com escore bruto 3,39 (acima do limiar 2,0) e a página esperada recuperada (`mecanica-t2`, seguimento sobre lubrificação); a abstenção indevida não vem só do limiar | execução | 2026-11-25 | médio |
| 7 | `config.py:168`: URL do OpenRouter literal (achado do validador `padrao-python`) | execução | 2026-11-25 | baixo |

---

# 3. Promover um item

Só o usuário dispara. Ao promover, o **revisor**:

1. Tria o item pela [[00-prompt-revisor]] §4 — plan se deixa verdade documentada, prompt direto se não.
2. Conduz a via escolhida como qualquer outra demanda.
3. **Remove a linha daqui**, na mesma ação. Item promovido não fica de lembrança: a partir daí quem responde
   por ele é o [[00-indice]] (se virou plan) ou a própria conversa (se virou prompt direto).

Promover **não** é obrigatório e não tem prazo. Um item pode ficar aqui indefinidamente sem que isso seja
dívida — é exatamente para isso que ele existe.

---

# 4. Regras de manutenção

- **Este arquivo não cresce sem limite, e o dreno tem gatilho.** Ele registra o que **ainda** é verdade.
  **Ao registrar um achado, o revisor relê os que já estão aqui** — é a única vez em que alguém abre o
  arquivo inteiro, e por isso é onde ele se drena. Achado corrigido de passagem por outra tarefa, código que
  deixou de existir, problema que a spec fixa passou a permitir: a linha **sai** na mesma ação, e o revisor
  diz isso na resposta. Regra de limpeza sem gatilho não roda — foi assim que o índice virou cemitério.
- **Não duplique.** Antes de registrar, procure — o mesmo achado visto em duas execuções é uma linha só.
- **Sem status, sem dono, sem prazo.** Se você sentiu falta de um desses campos, o item não é backlog: é
  plan. Promova ou deixe.
- **Nunca referencie um item daqui dentro do código.** Vale a mesma regra da plan: comentário não cita
  `backlog #3` (norma completa em `padrao-escrita`, `references/comentarios.md`).
- **Item que já está numa plan não fica aqui.** Um dos dois é a verdade — e é o [[00-indice]].
