---
tipo: "processo"
titulo: "Planejamento — Famílias e Horizonte"
dominio: "Governança de Specs (SDD)"
status: "🟢 Vigente"
tags: ["processo", "planejamento", "familias", "sdd"]
relacionados: ["[[00-contexto]]", "[[00-indice]]", "[[00-prompt-revisor]]"]
---

# 0. O que é este arquivo

O **catálogo de famílias** do projeto: a **fonte única** dos grupos de assunto que numeram as specs fixas
(`specs/`, `arquitetura/`) e as plans. Nenhum outro arquivo lista as famílias — todos apontam para cá. Na §2,
o **horizonte**: a evolução de longo prazo, em itens por família — a base do progresso do `00-resumo.md`.

**Quem escreve/atualiza:** o **agente revisor** ([[00-prompt-revisor]]), e cada família nova só depois da
**aprovação do usuário**.

---

# 1. Famílias

> **Como escrever:**
> - **Família** = número de dois dígitos `FF` + nome. Agrupa por **assunto** (ex.: `01` Conexão, `02` Base de
>   dados), não por pasta nem por tipo de arquivo.
> - **`00` é reservada à fundação.** Seus nomes chegam fixos e **não são renomeados** para `FF.NN`:
>   - os arquivos de processo `00-*.md` (este inclusive);
>   - em projeto modular, a lei do template em `arquitetura/`: `00-arquitetura.md`, `01-modulo.md`,
>     `02-contrato-e-dados.md`, `03-operacao.md`, `04-regras.md`, `05-ci-cd.md`, `README.md` e `00-base-<binding>.md`;
>   - `arquitetura/00-fundacao-tecnologica.md`, gerada pela skill `spec-fundacao` na abertura do repositório.
>
>   **Esta é a única lista desses nomes** — os outros arquivos apontam para cá.
> - **`specs/` e `arquitetura/`**: `FF.NN-<slug>.md`, zero à esquerda nos dois números, mais `familia: "FF"` no
>   frontmatter. O par `FF.NN` é **único na família somando as duas pastas**; o próximo `NN` livre sai da
>   varredura das duas.
> - **Plans**: `plan-FF.NN-<slug>.md` + `familia: "FF"`. Contador **por família**, monotônico e definitivo, no
>   mapa `proximo_numero_plan` do [[00-indice]]; família sem entrada começa em `01`. Namespace separado do das
>   specs: `plan-02.03` e `specs/02.03-*.md` não têm relação.
> - **ADR não tem família**: `adr/NNN-<slug>.md`, cronológico.
> - **Família nova**: o revisor propõe, o **usuário aprova**, e só então ela entra nesta tabela — e só então é
>   usada. Spec ou plan com família fora daqui é defeito.
> - Uma linha por família, escopo em **uma** linha. Família não se renumera nem se reaproveita.

| FF | Família | Escopo (uma linha) |
|---|---|---|
| 00 | Fundação | processo SDD, lei do template e fundação tecnológica — reservada |
| 01 | Sprint 3 — Alertas e classificação | geração fiel de alertas, classificação de eventos em 5 categorias e relatório operacional rastreável |
| 02 | Sprint 4 — RAG e assistente | pipeline RAG sobre o manual W22, assistente de troubleshooting, avaliação, cenários e entrega |

---

# 2. Horizonte

> **Como escrever:** o **longo prazo**, em tópicos por família — o que ainda vai virar plan ou spec. A unidade
> de progresso é o **item**, não a plan: a plan some na síntese, o item fica.
>
> - **Um título por família**, com o número e o nome do catálogo: `## 02 · Base de dados`.
> - **Um item por linha**, neste formato fixo, que a skill `spec-panorama` lê:
>   `- 🔷 **R02.3** Índices de busca — uma frase opcional`. Concluído pode levar a data no fim: `(✅ AAAA-MM-DD)`.
> - **ID** `R<FF>.<n>`: `FF` é a família do catálogo; `n` é sequencial dentro da família, sem zero à esquerda,
>   e **nunca** reaproveitado.
> - **Estado:** `⬜` planejado · `🔷` em andamento (ao menos uma plan aberta com `item:` apontando para ele) ·
>   `✅` concluído (a última plan dele foi sintetizada).
> - **Ligação:** a plan aponta para o item pelo campo opcional `item: "R02.3"` do frontmatter. Plan sem item
>   (bug, conformidade) é normal e não entra na % de progresso.
> - **Quem mexe:** só o revisor. Primeira plan de um item → `🔷`; síntese da última plan do item → `✅`, **na
>   mesma ação** em que a plan é removida. O **usuário** decide o que entra no horizonte; o revisor escreve.
> - **Não é backlog:** o [[00-backlog]] guarda *achados* (problemas notados); este horizonte guarda *evolução
>   pretendida*. Um achado que o usuário promove a evolução de longo prazo pode virar item.

## 01 · Sprint 3 — Alertas e classificação
- ✅ **R01.1** Alertas determinísticos e fiéis — severidade, templates e verificador sobre os dados reais (F1) (✅ 2026-11-24)
- ✅ **R01.2** Classificação em 5 categorias e relatório rastreável — 60 eventos rotulados, F1 por classe, ROUGE e checklist (F1, F2) (✅ 2026-11-24)

## 02 · Sprint 4 — RAG e assistente
- ✅ **R02.1** Pipeline RAG com página, seção e estado — chunking por seção, embeddings multilíngues, estado na busca (F3, F4) (✅ 2026-11-25)
- ✅ **R02.2** Assistente de troubleshooting — persona, citação, confiança calculada, abstenção e memória (✅ 2026-11-25)
- 🔷 **R02.3** Avaliação confiável do RAG e do juiz — 20 perguntas com gabarito de página, métricas de recuperação, juiz por afirmação (F5, F6)
- 🔷 **R02.4** Cenários e limites — elétrica, mecânica e preventiva em separado, limites observados (F7)
- 🔷 **R02.5** Entrega — documento final, README, roteiro do vídeo e notebooks executados

<!-- Exemplo (comentado: não conta como item real)
## 02 · Base de dados
- ✅ **R02.1** Schema inicial — tabelas do domínio de pedidos (✅ 2026-10-09)
- 🔷 **R02.2** Índices de busca — há uma plan aberta com item: "R02.2"
- 🔷 **R02.3** Particionamento por mês
-->
