# Relatório final — Assistente de troubleshooting para motores elétricos (Sprints 3 e 4)

Challenge FIAP × Forzy · Processamento de Linguagem Natural · motor WEG W22 (digital twin).

> Todo número de resultado deste documento está entre marcadores invisíveis (comentários HTML) e é preenchido por
> `python tools/gerar_relatorio_final.py` a partir de `data/saida/*.json` e das saídas executadas do notebook da Sprint 3;
> `python tools/gerar_relatorio_final.py --check` falha se um valor divergir da saída. Os números não foram digitados.

## 1. Visão geral e arquitetura

O sistema transforma leituras de sensores em alertas e relatórios em português **sem afirmar nada além dos dados**, classifica
eventos em cinco categorias e responde perguntas sobre o catálogo técnico do W22 citando **página e seção**. A regra que governa
tudo: **todo fato nasce de código; o LLM só redige**, e todo texto de LLM passa por um verificador antes de valer.

```
dados (CSV de leituras + limiares)
   │  sensores.py: mapeamento canônico, severidade por faixa
   ▼
alertas (episódios com ids de leitura)  ──►  templates (3 tons)  ──►  [LLM redige]  ──►  verificador  ──►  texto final
   │                                                                                        (reprovou → template)
   ├──►  classificação de eventos (linha de base × zero-shot)      ──►  F1 por categoria
   ├──►  relatório diário/semanal rastreável                       ──►  ROUGE + checklist
   ▼
estado operacional (alertas ativos no instante)
   │
   ▼
retriever (PDF → chunks com página/seção → embeddings → ChromaDB → reranker; o estado entra na busca)
   ▼
assistente (prompt, citação [p., seç.], confiança calculada, abstenção sem LLM, memória de 3 turnos)
   ▼
avaliação (recuperação por página e estrita; faithfulness por afirmação; relevancy; calibração do juiz)  ──►  cenários e limites
```

Dados de origem: <!--{nb3.readings|d}-->43123<!--/--> leituras de um ativo, seis variáveis, das quais só quatro têm limiar em
`active_assets.json`. O mapeamento canônico dos sensores (`data/sensores.json`) usa descrição e magnitude, porque nome e unidade de
`data_variables.json` contradizem os dados; foi confirmado pelo dono do projeto. A lógica vive em `src/pln/` e os notebooks só
orquestram e exibem.

## 2. Templates de narrativa e verificador

Há **três templates**, um por severidade, com tom distinto. Eles usam só campos calculados do alerta (grandeza, pico, desvio acima do
nominal, janela em UTC) e a **ação padrão** da tabela de ações; nunca causa nem previsão. Exemplos reais, tirados de `data/saida/alertas.json`:

- **Leve** (monitoramento) — <!--{alertas[id=A-0003].id|s}-->A-0003<!--/-->: <!--{alertas[id=A-0003].texto|s}-->Alerta leve para o ativo Teste (Sorocaba); acompanhe a corrente elétrica por fase: pico 129,48 A; desvio +4,48 A acima do nominal 125,00 A. Em menos de um minuto, entre 05/05/2026 às 01:22:58 UTC e 05/05/2026 às 01:23:10 UTC. Monitore a corrente elétrica por fase nas próximas leituras.<!--/-->
- **Moderado** (inspeção programada) — <!--{alertas[id=A-0004].id|s}-->A-0004<!--/-->: <!--{alertas[id=A-0004].texto|s}-->Alerta moderado para o ativo Teste (Sorocaba); programe inspeção da velocidade do eixo: pico 1.821,75 rpm; desvio +71,75 rpm acima do nominal 1.750,00 rpm. Em menos de um minuto, entre 05/05/2026 às 01:22:58 UTC e 05/05/2026 às 01:23:04 UTC. Verifique a velocidade do eixo e programe inspeção.<!--/-->
- **Crítico** (urgência) — <!--{alertas[id=A-0001].id|s}-->A-0001<!--/-->: <!--{alertas[id=A-0001].texto|s}-->Alerta crítico para o ativo Teste (Sorocaba); verifique com urgência a temperatura do enrolamento (estator): pico 122,96 °C; desvio +47,96 °C acima do nominal 75,00 °C. Em menos de um minuto, entre 05/05/2026 às 01:22:22 UTC e 05/05/2026 às 01:22:32 UTC. Interrompa a operação e solicite inspeção imediata.<!--/-->

**Verificador** (`verificar_texto`, `verificar_clareza`): reprova número fora do conjunto permitido, grandeza/ativo/unidade ausentes ou de
outro alerta, fato obrigatório ausente, termo de causa, diagnóstico ou prognóstico, ação diferente da padrão, conteúdo novo e paráfrase
além de um vocabulário fechado, além de limite de palavras. O texto do LLM só vira final se passar nos dois verificadores; senão
fica o template. Falha de API mantém o template e não interrompe a execução.

Resultado sobre os nove alertas-teste com resumo de referência: fidelidade dos templates <!--{nb3.fidelidade_templates_pct|f1}-->100,0<!--/-->;
taxa de aceitação dos textos do LLM pelo verificador <!--{nb3.taxa_aceitacao_pct|f1}-->88,9<!--/-->; ROUGE-1/2/L dos templates
<!--{nb3.rouge_template.rouge1|f3}-->0,586<!--/--> / <!--{nb3.rouge_template.rouge2|f3}-->0,396<!--/--> / <!--{nb3.rouge_template.rougeL|f3}-->0,543<!--/-->
e dos textos com LLM <!--{nb3.rouge_llm.rouge1|f3}-->0,587<!--/--> / <!--{nb3.rouge_llm.rouge2|f3}-->0,401<!--/--> / <!--{nb3.rouge_llm.rougeL|f3}-->0,497<!--/-->.
O checklist (precisão, clareza e utilidade) fica verdadeiro em todas as linhas, inclusive nas de origem `llm`.
Sobre os dados reais, o notebook emitiu <!--{alertas.#|d}-->4477<!--/--> alertas
(<!--{nb3.alert_counts.leve|d}-->495<!--/--> leves, <!--{nb3.alert_counts.moderado|d}-->1788<!--/--> moderados,
<!--{nb3.alert_counts.critico|d}-->2194<!--/--> críticos), todos com texto de template e com os ids das leituras que os sustentam.

## 3. Critérios de classificação

Cinco categorias, com rótulo exato: manutenção corretiva, manutenção preventiva, anomalia elétrica, anomalia mecânica e operação normal.
O critério de cada uma vive em `CRITERIOS_CATEGORIA_EVENTO` (`src/pln/config.py`) e é o texto que o prompt entrega ao modelo:

| Categoria | Critério |
|---|---|
| manutenção corretiva | Intervenção não planejada para reparar ou substituir um componente após uma ocorrência. |
| manutenção preventiva | Inspeção, limpeza, lubrificação ou ajuste planejado antes de uma falha registrada. |
| anomalia elétrica | Evento observado em corrente, tensão, conexão, isolamento ou proteção elétrica. |
| anomalia mecânica | Evento observado em vibração, ruído, rotação, eixo, acoplamento ou suporte mecânico. |
| operação normal | Registro sem ocorrência ou desvio observado durante a operação do motor. |

**Conjunto:** <!--{nb3.events_total|d}-->60<!--/--> eventos, balanceados entre as cinco categorias, rotulados e revisados pelo dono; parte
deles é derivada de alertas reais e parte é sintética, com casos difíceis de propósito (preventiva que cita vibração, corretiva posterior a
uma anomalia, normal com leitura próxima do nominal). **Protocolo:** o léxico da linha de base e o prompt do zero-shot são ajustados só com
o split `dev`; o split `teste` (<!--{classificacao.suporte_teste|d}-->50<!--/--> eventos) é avaliado uma única vez. Classificador
zero-shot: `<!--{classificacao.modelo|s}-->mistralai/mistral-small-3.2-24b-instruct<!--/-->`, temperatura 0, resposta fora das cinco categorias vira `indeterminado` e conta como erro.

## 4. Relatório operacional e rastreabilidade

O relatório diário e o semanal são **determinísticos** (sem LLM) e têm cinco seções: resumo, alertas emitidos, sensores em risco,
tendências (só variação numérica entre a primeira e a segunda metade da janela) e ações padrão, rotuladas como "não é diagnóstico".
Toda frase termina com `[ref: A-… | ids: …]` (alerta e leituras do CSV) ou `[ref: período | sensor …]` (agregado), e o verificador
reprova frase sem referência, referência que não resolve, número fora do conjunto e termo proibido.

| Relatório | ROUGE-1 | ROUGE-2 | ROUGE-L | Frases rastreáveis | Violações |
|---|---|---|---|---|---|
| Diário | <!--{relatorio_diario.avaliacao.rouge.rouge1|f3}-->0,449<!--/--> | <!--{relatorio_diario.avaliacao.rouge.rouge2|f3}-->0,286<!--/--> | <!--{relatorio_diario.avaliacao.rouge.rougeL|f3}-->0,350<!--/--> | <!--{relatorio_diario.avaliacao.frases_rastreaveis_pct|f1}-->100,0<!--/--> % | <!--{relatorio_diario.avaliacao.violacoes.#|d}-->0<!--/--> |
| Semanal | <!--{relatorio_semanal.avaliacao.rouge.rouge1|f3}-->0,453<!--/--> | <!--{relatorio_semanal.avaliacao.rouge.rouge2|f3}-->0,298<!--/--> | <!--{relatorio_semanal.avaliacao.rouge.rougeL|f3}-->0,368<!--/--> | <!--{relatorio_semanal.avaliacao.frases_rastreaveis_pct|f1}-->100,0<!--/--> % | <!--{relatorio_semanal.avaliacao.violacoes.#|d}-->0<!--/--> |

O checklist de precisão, clareza, utilidade e rastreabilidade fica verdadeiro nos dois. A referência do ROUGE foi escrita à mão a partir dos
números calculados. O verificador confere números e referências, **não** que a frase descreva o alerta citado além deles.

## 5. Arquitetura do RAG

- **Fonte e chunking.** O catálogo W22 (PDF em português) é lido por página com PyMuPDF; cabeçalho e rodapé saem, tabelas viram linhas
  `Coluna: valor`, e a **hierarquia de seções vem do sumário do catálogo**. O chunking é **por seção**, nunca atravessa o título seguinte
  e carrega `pagina`, `pagina_fim`, `secao` e `secao_titulo`; o texto indexado começa por `[Seção 4.1 — … | p. 13]`. Tamanhos em `config.py`
  (`CHUNK_MAX`, `CHUNK_OVERLAP`, `CHUNK_MIN`).
- **Modelos.** Preset `NOVO`: embedding `intfloat/multilingual-e5-base` e reranker `cross-encoder/mmarco-mMiniLMv2-L12-H384-v1`.
  Preset `LEGADO` (a entrega anterior): chunking por parágrafo sem metadados, `all-MiniLM-L6-v2` e `ms-marco-MiniLM-L-6-v2`. Os dois
  ficam lado a lado para a comparação antes × depois.
- **Índice.** ChromaDB em memória, distância cosseno, com os metadados de página e seção.
- **Retriever com estado (F3).** A consulta é expandida com termos em português do domínio de falha dos alertas ativos, a busca densa traz
  os candidatos, o reranker pontua `(pergunta, chunk)`, os escores são normalizados e as seções-alvo do estado recebem um bônus
  (`PESO_ESTADO` = <!--{avaliacao_recuperacao.parametros.peso_estado|f2}-->0,15<!--/-->, calibrado só com o `dev`). `estado=None` desliga bônus e termos
  extras: é a ablação "sem estado".
- **Estado operacional.** Alertas ativos no instante, com id, grandeza, severidade, valor e domínio de falha (temperatura → térmica,
  corrente → elétrica, vibração e velocidade → mecânica); sem alertas, `operacao_normal`.

## 6. Assistente

- **Prompt de sistema:** persona de assistente técnico em motores elétricos; responde **só com o contexto recuperado**; cita cada afirmação
  como `[p. <página>, seç. <seção>]`; trata o estado operacional como dado confiável do sistema; não usa conhecimento externo nem inventa números.
- **Citação:** o par página/seção citado é conferido contra os chunks fornecidos; citação inexistente é sinalizada (`citacao_invalida`), nunca
  corrigida em silêncio. Sem citação do modelo, as fontes são os chunks usados.
- **Confiança calculada por código** (Alta/Média/Baixa) sobre o escore bruto do reranker e o número de chunks acima do limiar; a confiança
  autodeclarada pelo LLM é descartada.
- **Abstenção determinística:** se o melhor chunk pontua abaixo de `LIMIAR_ABSTENCAO` (<!--{avaliacao_recuperacao.parametros.limiar_abstencao|f1}-->2,0<!--/-->
  de escore bruto), o assistente devolve a frase fixa de abstenção **sem chamar o LLM**.
- **Memória de curto prazo:** três turnos; pergunta curta ou com anáfora ("essa", "esse") é recuperada junto da pergunta anterior.
- **Modelo:** gerador `<!--{avaliacao_respostas.modelo_gerador|s}-->meta-llama/llama-3.3-70b-instruct<!--/-->`, juiz `<!--{avaliacao_respostas.modelo_juiz|s}-->google/gemma-3-12b-it<!--/-->`, de famílias
  diferentes, ids fixos em `config.py`, sem fallback; cada resposta registra o modelo que a produziu.

## 7. Métricas obtidas

### 7.1 Classificação (F1 por categoria, split `teste`)

| Categoria | F1 linha de base | F1 zero-shot | Suporte |
|---|---|---|---|
| manutenção corretiva | <!--{classificacao.linha_de_base.por_categoria.manutenção corretiva.f1-score|f3}-->0,167<!--/--> | <!--{classificacao.zero_shot.por_categoria.manutenção corretiva.f1-score|f3}-->0,824<!--/--> | <!--{classificacao.zero_shot.por_categoria.manutenção corretiva.support|d}-->10<!--/--> |
| manutenção preventiva | <!--{classificacao.linha_de_base.por_categoria.manutenção preventiva.f1-score|f3}-->0,182<!--/--> | <!--{classificacao.zero_shot.por_categoria.manutenção preventiva.f1-score|f3}-->0,750<!--/--> | <!--{classificacao.zero_shot.por_categoria.manutenção preventiva.support|d}-->10<!--/--> |
| anomalia elétrica | <!--{classificacao.linha_de_base.por_categoria.anomalia elétrica.f1-score|f3}-->0,000<!--/--> | <!--{classificacao.zero_shot.por_categoria.anomalia elétrica.f1-score|f3}-->0,909<!--/--> | <!--{classificacao.zero_shot.por_categoria.anomalia elétrica.support|d}-->10<!--/--> |
| anomalia mecânica | <!--{classificacao.linha_de_base.por_categoria.anomalia mecânica.f1-score|f3}-->0,000<!--/--> | <!--{classificacao.zero_shot.por_categoria.anomalia mecânica.f1-score|f3}-->0,741<!--/--> | <!--{classificacao.zero_shot.por_categoria.anomalia mecânica.support|d}-->10<!--/--> |
| operação normal | <!--{classificacao.linha_de_base.por_categoria.operação normal.f1-score|f3}-->0,000<!--/--> | <!--{classificacao.zero_shot.por_categoria.operação normal.f1-score|f3}-->0,778<!--/--> | <!--{classificacao.zero_shot.por_categoria.operação normal.support|d}-->10<!--/--> |
| **macro** | <!--{classificacao.linha_de_base.macro.f1-score|f3}-->0,070<!--/--> | <!--{classificacao.zero_shot.macro.f1-score|f3}-->0,800<!--/--> | <!--{classificacao.zero_shot.macro.support|d}-->50<!--/--> |

A linha de base por léxico (poucos termos, escrito olhando só o `dev`) deixa <!--{classificacao.linha_de_base.erros.#|d}-->48<!--/--> dos
<!--{classificacao.suporte_teste|d}-->50<!--/--> eventos errados ou `indeterminados`; o zero-shot erra <!--{classificacao.zero_shot.erros.#|d}-->10<!--/-->.
Os erros do zero-shot concentram-se em corretivas e preventivas lidas como anomalia, e em "operação normal" lida como anomalia quando o texto cita
uma leitura próxima do nominal. A diferença entre os dois mede também o tamanho do léxico.

### 7.2 Recuperação (split `teste`, k = 4)

| Configuração | hit@4 (página) | MRR@4 | context precision@4 | hit@4 (estrita) |
|---|---|---|---|---|
| `LEGADO` | <!--{avaliacao_recuperacao.configuracoes.LEGADO.resumo[grupo=teste,criterio=pagina,k=4].hit|f3}-->0,800<!--/--> | <!--{avaliacao_recuperacao.configuracoes.LEGADO.resumo[grupo=teste,criterio=pagina,k=4].mrr|f3}-->0,628<!--/--> | <!--{avaliacao_recuperacao.configuracoes.LEGADO.resumo[grupo=teste,criterio=pagina,k=4].context_precision|f3}-->0,606<!--/--> | <!--{avaliacao_recuperacao.configuracoes.LEGADO.resumo[grupo=teste,criterio=estrita,k=4].hit|f3}-->0,400<!--/--> |
| `NOVO` sem estado | <!--{avaliacao_recuperacao.configuracoes.NOVO sem estado.resumo[grupo=teste,criterio=pagina,k=4].hit|f3}-->0,933<!--/--> | <!--{avaliacao_recuperacao.configuracoes.NOVO sem estado.resumo[grupo=teste,criterio=pagina,k=4].mrr|f3}-->0,933<!--/--> | <!--{avaliacao_recuperacao.configuracoes.NOVO sem estado.resumo[grupo=teste,criterio=pagina,k=4].context_precision|f3}-->0,896<!--/--> | <!--{avaliacao_recuperacao.configuracoes.NOVO sem estado.resumo[grupo=teste,criterio=estrita,k=4].hit|f3}-->0,933<!--/--> |
| `NOVO` com estado | <!--{avaliacao_recuperacao.configuracoes.NOVO com estado.resumo[grupo=teste,criterio=pagina,k=4].hit|f3}-->0,933<!--/--> | <!--{avaliacao_recuperacao.configuracoes.NOVO com estado.resumo[grupo=teste,criterio=pagina,k=4].mrr|f3}-->0,933<!--/--> | <!--{avaliacao_recuperacao.configuracoes.NOVO com estado.resumo[grupo=teste,criterio=pagina,k=4].context_precision|f3}-->0,876<!--/--> | <!--{avaliacao_recuperacao.configuracoes.NOVO com estado.resumo[grupo=teste,criterio=estrita,k=4].hit|f3}-->0,867<!--/--> |

Relevância "por página": o intervalo de páginas do chunk toca uma página do gabarito. "Estrita": o chunk contém o trecho-âncora do catálogo. O
gabarito tem <!--{avaliacao_recuperacao.configuracoes.NOVO com estado.registros.#|d}-->20<!--/--> perguntas dentro do escopo, com página, seção e trecho-âncora.

**O estado operacional não melhora a recuperação.** Nas perguntas em que `NOVO com estado` e `sem estado` realmente diferem
(<!--{avaliacao_recuperacao.configuracoes.NOVO com estado.resumo[grupo=com_estado,criterio=pagina,k=4].n|d}-->9<!--/--> perguntas), o hit@4 por página é
<!--{avaliacao_recuperacao.configuracoes.NOVO sem estado.resumo[grupo=com_estado,criterio=pagina,k=4].hit|f3}-->1,000<!--/--> sem estado e
<!--{avaliacao_recuperacao.configuracoes.NOVO com estado.resumo[grupo=com_estado,criterio=pagina,k=4].hit|f3}-->1,000<!--/--> com estado, e a context precision cai de
<!--{avaliacao_recuperacao.configuracoes.NOVO sem estado.resumo[grupo=com_estado,criterio=pagina,k=4].context_precision|f3}-->0,917<!--/--> para
<!--{avaliacao_recuperacao.configuracoes.NOVO com estado.resumo[grupo=com_estado,criterio=pagina,k=4].context_precision|f3}-->0,846<!--/-->. O ganho do `NOVO` sobre o `LEGADO` vem
do chunking por seção e dos modelos multilíngues, não do estado.

### 7.3 Respostas do assistente (`NOVO com estado`)

<!--{avaliacao_respostas.resumo.geral.n|d}-->25<!--/--> perguntas (as dentro do escopo mais as fora do escopo):
**faithfulness média <!--{avaliacao_respostas.resumo.geral.faithfulness_media|f2}-->0,98<!--/-->**, **answer relevancy média
<!--{avaliacao_respostas.resumo.geral.relevancy_media|f2}-->0,85<!--/-->** (cosseno médio resposta × referência
<!--{avaliacao_respostas.resumo.geral.cosseno_medio|f2}-->0,96<!--/-->), <!--{avaliacao_respostas.resumo.geral.erros|d}-->0<!--/--> erros de API,
<!--{avaliacao_respostas.resumo.geral.abstencoes_corretas|d}-->5<!--/--> abstenções corretas,
<!--{avaliacao_respostas.resumo.geral.abstencoes_indevidas|d}-->2<!--/--> abstenções indevidas e
<!--{avaliacao_respostas.resumo.geral.alucinacoes_fora_escopo|d}-->0<!--/--> respostas factuais a perguntas fora do escopo.

| Categoria | Faithfulness | Relevancy | Abstenções indevidas |
|---|---|---|---|
| elétrica | <!--{avaliacao_respostas.resumo.por_categoria.elétrica.faithfulness_media|f2}-->1,00<!--/--> | <!--{avaliacao_respostas.resumo.por_categoria.elétrica.relevancy_media|f2}-->0,90<!--/--> | <!--{avaliacao_respostas.resumo.por_categoria.elétrica.abstencoes_indevidas|d}-->0<!--/--> |
| mecânica | <!--{avaliacao_respostas.resumo.por_categoria.mecânica.faithfulness_media|f2}-->1,00<!--/--> | <!--{avaliacao_respostas.resumo.por_categoria.mecânica.relevancy_media|f2}-->1,00<!--/--> | <!--{avaliacao_respostas.resumo.por_categoria.mecânica.abstencoes_indevidas|d}-->0<!--/--> |
| preventiva | <!--{avaliacao_respostas.resumo.por_categoria.preventiva.faithfulness_media|f2}-->1,00<!--/--> | <!--{avaliacao_respostas.resumo.por_categoria.preventiva.relevancy_media|f2}-->0,60<!--/--> | <!--{avaliacao_respostas.resumo.por_categoria.preventiva.abstencoes_indevidas|d}-->2<!--/--> |
| especificação | <!--{avaliacao_respostas.resumo.por_categoria.especificação.faithfulness_media|f2}-->0,90<!--/--> | <!--{avaliacao_respostas.resumo.por_categoria.especificação.relevancy_media|f2}-->0,90<!--/--> | <!--{avaliacao_respostas.resumo.por_categoria.especificação.abstencoes_indevidas|d}-->0<!--/--> |

**Faithfulness** é medida **por afirmação**: o juiz rotula cada frase da resposta como `SUSTENTADA`, `EXTERNA` (não está no contexto, mesmo que
verdadeira), `CONTRADIZ` ou `META`, e a métrica é `SUSTENTADA / (SUSTENTADA + EXTERNA + CONTRADIZ)`. Guardas determinísticas prevalecem sobre o
juiz: número ausente do contexto ou marcador de conhecimento externo ("em geral", "normalmente") vira `EXTERNA`. **Answer relevancy** compara a
resposta com a referência (`COBRE` = 1, `PARCIAL` = 0,5, `NAO_COBRE` = 0). A comparação com a entrega anterior só dá ordem de grandeza: o método mudou
(antes, uma nota única do juiz sobre a resposta inteira).

### 7.4 Calibração do juiz (F6)

16 casos `(contexto, afirmação, rótulo)` escritos à mão, incluindo afirmações verdadeiras mas externas ao contexto. Juiz com guardas, todos os casos:
acurácia <!--{juiz_calibracao.metricas.todos.juiz_com_guardas.acuracia|f3}-->0,938<!--/-->, revocação de `EXTERNA`
<!--{juiz_calibracao.metricas.todos.juiz_com_guardas.revocacao_externa|f3}-->1,000<!--/-->, precisão de `EXTERNA`
<!--{juiz_calibracao.metricas.todos.juiz_com_guardas.precisao_externa|f3}-->0,833<!--/-->. No `dev` (<!--{juiz_calibracao.metricas.dev.juiz_com_guardas.n|d}-->6<!--/--> casos)
a acurácia é <!--{juiz_calibracao.metricas.dev.juiz_com_guardas.acuracia|f3}-->1,000<!--/-->; no `teste` (<!--{juiz_calibracao.metricas.teste.juiz_com_guardas.n|d}-->10<!--/--> casos),
<!--{juiz_calibracao.metricas.teste.juiz_com_guardas.acuracia|f3}-->0,900<!--/-->. O prompt foi ajustado
<!--{juiz_calibracao.ajustes_de_prompt_com_dev|d}-->0<!--/--> vezes olhando o `dev`.

## 8. Cenários

Três cenários separados (F7), cada um com estado montado a partir de um **alerta real**, escolhido por regra (nunca à mão), e um diálogo de
três turnos: pergunta natural, seguimento anafórico e pergunta fora do escopo (esperado: abstenção).

| Cenário | Episódio do estado | Faithfulness | Relevancy | Fonte esperada recuperada | Abstenções corretas |
|---|---|---|---|---|---|
| Anomalia elétrica | <!--{cenarios.cenarios[id=eletrica].episodio.alerta_id|s}-->A-4468<!--/-->, <!--{cenarios.cenarios[id=eletrica].episodio.valor_max|f2}-->172,01<!--/--> A (crítico) | <!--{cenarios.resumo.eletrica.faithfulness_media|f2}-->0,83<!--/--> | <!--{cenarios.resumo.eletrica.relevancy_media|f2}-->0,75<!--/--> | <!--{cenarios.resumo.eletrica.fontes_esperadas_recuperadas|d}-->2<!--/--> de <!--{cenarios.resumo.eletrica.fontes_esperadas|d}-->2<!--/--> | <!--{cenarios.resumo.eletrica.abstencoes_corretas|d}-->1<!--/--> |
| Anomalia mecânica | <!--{cenarios.cenarios[id=mecanica].episodio.alerta_id|s}-->A-4471<!--/-->, <!--{cenarios.cenarios[id=mecanica].episodio.valor_max|f2}-->4,87<!--/--> mm/s (crítico) | <!--{cenarios.resumo.mecanica.faithfulness_media|f2}-->1,00<!--/--> | <!--{cenarios.resumo.mecanica.relevancy_media|f2}-->0,50<!--/--> | <!--{cenarios.resumo.mecanica.fontes_esperadas_recuperadas|d}-->2<!--/--> de <!--{cenarios.resumo.mecanica.fontes_esperadas|d}-->2<!--/--> | <!--{cenarios.resumo.mecanica.abstencoes_corretas|d}-->1<!--/--> |
| Manutenção preventiva | leitura de <!--{cenarios.cenarios[id=preventiva].episodio.instante|s}-->2026-08-23T09:46:39.901427+00:00<!--/-->, operação normal | <!--{cenarios.resumo.preventiva.faithfulness_media|f2}-->1,00<!--/--> | <!--{cenarios.resumo.preventiva.relevancy_media|f2}-->1,00<!--/--> | <!--{cenarios.resumo.preventiva.fontes_esperadas_recuperadas|d}-->2<!--/--> de <!--{cenarios.resumo.preventiva.fontes_esperadas|d}-->2<!--/--> | <!--{cenarios.resumo.preventiva.abstencoes_corretas|d}-->1<!--/--> |

No cenário mecânico, o seguimento (`mecanica-t2`) recuperou a página esperada, mas o gerador respondeu a frase de abstenção: a abstenção não veio só do
limiar. Há ainda um **cenário adversarial** (estado contraditório e conhecimento externo): das <!--{cenarios.resumo.adversarial.n_turnos|d}-->2<!--/--> perguntas,
<!--{cenarios.resumo.adversarial.respostas_sem_abster_fora_escopo|d}-->1<!--/--> foi respondida sem abstenção (faithfulness média
<!--{cenarios.resumo.adversarial.faithfulness_media|f2}-->0,50<!--/-->), e o assistente comparou o valor do estado com o nominal do catálogo.

## 9. Limites e mitigações

Tabela montada por código a partir da execução (`data/saida/limites.json`); cada linha cita um caso ou número observado.

- **Fora do escopo.** <!--{limites.linhas[id=fora_escopo_abstencao].limite|s}-->Perguntas fora do escopo do catálogo: 9 de 10 abstiveram e 1 responderam sem abster (ids: adversarial-t1).<!--/-->
  *Mitigação:* <!--{limites.linhas[id=fora_escopo_abstencao].mitigacao|s}-->Abstenção determinística: sem chunk com escore bruto acima do limiar, o assistente devolve a frase fixa sem chamar o LLM.<!--/-->
  *Risco residual:* <!--{limites.linhas[id=fora_escopo_abstencao].risco_residual|s}-->O escore bruto não separa os escopos por construção: uma pergunta fora do escopo que recupere um chunk acima do limiar é respondida (1 de 10 nesta execução).<!--/-->
- **Alucinação por afirmação.** <!--{limites.linhas[id=alucinacao_afirmacoes].limite|s}-->Alucinação medida por afirmação: 6 de 42 afirmações rotuladas EXTERNA ou CONTRADIZ (6 EXTERNA, 0 CONTRADIZ; ids: adversarial-t1, eletrica-t2, s02).<!--/-->
  *Mitigação:* <!--{limites.linhas[id=alucinacao_afirmacoes].mitigacao|s}-->Citação obrigatória [p., seç.] conferida contra os chunks, verificador numérico (número ausente do contexto vira EXTERNA), guarda de marcadores de conhecimento externo e juiz de família diferente da do gerador.<!--/-->
  *Risco residual:* <!--{limites.linhas[id=alucinacao_afirmacoes].risco_residual|s}-->O juiz só vê os chunks e não o estado operacional: uma afirmação que vem do estado pode ser rotulada EXTERNA, e uma frase que o chunk não sustenta pode passar como SUSTENTADA.<!--/-->
- **Alucinação com estado contraditório.** <!--{limites.linhas[id=alucinacao_adversarial].limite|s}-->Estado contraditório com a intuição do modelo (Teste (Sorocaba): severidade geral critico. Alerta A-1800: Velocidade do eixo, severidade critico, valor máximo 1850.47 rpm, início 2026-05-07T20:38:05+00:00.): 1 de 2 turnos adversariais abstiveram.<!--/-->
  *Mitigação:* <!--{limites.linhas[id=alucinacao_adversarial].mitigacao|s}-->Estado operacional tratado como dado confiável no prompt do sistema; severidade e confiança são calculadas por código, não pelo LLM.<!--/-->
  *Risco residual:* <!--{limites.linhas[id=alucinacao_adversarial].risco_residual|s}-->Nada impede o LLM de redigir uma frase que minimize o alerta quando o catálogo traz uma informação parecida; só a leitura da resposta e o juiz por afirmação a detectam depois.<!--/-->
- **Corpus sem troubleshooting.** <!--{limites.linhas[id=corpus_troubleshooting].limite|s}-->O catálogo é comercial e não traz troubleshooting passo a passo: 3 de 3 perguntas de procedimento prático dos cenários abstiveram, e a fonte esperada foi recuperada em 6 de 6 turnos dentro do escopo.<!--/-->
  *Mitigação:* <!--{limites.linhas[id=corpus_troubleshooting].mitigacao|s}-->Cenários só com perguntas que o PDF cobre (fonte esperada conferida na página) e uma pergunta deliberadamente sem resposta por cenário, para mostrar a abstenção.<!--/-->
  *Risco residual:* <!--{limites.linhas[id=corpus_troubleshooting].risco_residual|s}-->Perguntas de diagnóstico (causa, reparo, torque) não têm resposta no corpus: o assistente só diz o que o catálogo afirma sobre o componente.<!--/-->
- **Juiz de 12B.** <!--{limites.linhas[id=metodo_juiz].limite|s}-->Juiz LLM de 12B: acurácia 0,938 e revocação de EXTERNA 1,000 (precisão 0,833) em 16 casos de calibração; 1 caso(s) com rótulo final diferente do esperado.<!--/-->
  *Mitigação:* <!--{limites.linhas[id=metodo_juiz].mitigacao|s}-->Juiz diferente do gerador (famílias distintas, ids fixos, sem fallback), temperatura 0 com cache e guardas determinísticas que prevalecem sobre o rótulo do juiz.<!--/-->
  *Risco residual:* <!--{limites.linhas[id=metodo_juiz].risco_residual|s}-->Uma calibração de 16 casos não garante revocação em respostas reais: a faithfulness próxima de 1,0 pode esconder afirmações que o contexto não sustenta.<!--/-->
- **Amostra e gabarito.** <!--{limites.linhas[id=metodo_amostra].limite|s}-->Amostra pequena e gabarito por página: 20 perguntas dentro e 5 fora do escopo (0 fora no split teste), mais 11 turnos de cenário; faithfulness média 0,980.<!--/-->
  *Mitigação:* <!--{limites.linhas[id=metodo_amostra].mitigacao|s}-->Split dev/teste (calibração só no dev), relevância por página e estrita, e números reportados como saíram, inclusive as falhas.<!--/-->
  *Risco residual:* <!--{limites.linhas[id=metodo_amostra].risco_residual|s}-->Com 20 perguntas dentro do escopo, diferenças pequenas entre configurações não são distinguíveis; a abstenção correta só é medida nas perguntas do dev.<!--/-->
- **Limiar fixo de abstenção.** <!--{limites.linhas[id=metodo_limiar_abstencao].limite|s}-->Limiar fixo de abstenção (2,000 de escore bruto): 3 pergunta(s) dentro do escopo com abstenção indevida (ids: p01, p02, mecanica-t2).<!--/-->
  *Mitigação:* <!--{limites.linhas[id=metodo_limiar_abstencao].mitigacao|s}-->Limiar calibrado só no dev, no par que abstém em todas as perguntas fora do escopo: prefere abster a responder sem sustentação.<!--/-->
  *Risco residual:* <!--{limites.linhas[id=metodo_limiar_abstencao].risco_residual|s}-->O mesmo limiar abstém em perguntas legítimas cujo melhor chunk pontua abaixo de 2,000 (ids: p01, p02, mecanica-t2); o usuário recebe a frase de abstenção mesmo havendo resposta no catálogo.<!--/-->
- **Variáveis sem limiar.** <!--{limites.linhas[id=dados_limiares].limite|s}-->Só 4 das 6 variáveis têm limiar em active_assets.json; as outras 2 não geram alerta.<!--/-->
  *Mitigação:* <!--{limites.linhas[id=dados_limiares].mitigacao|s}-->Variável sem limiar não gera alerta nem entra no estado; os limiares nunca são copiados à mão (sensores.py falha se divergirem de active_assets.json).<!--/-->
  *Risco residual:* <!--{limites.linhas[id=dados_limiares].risco_residual|s}-->Uma anomalia nas 2 variáveis sem limiar passa despercebida pelo estado operacional e, portanto, pelo assistente.<!--/-->
- **Nomes e unidades inconsistentes.** <!--{limites.linhas[id=dados_nomes].limite|s}-->Nomes e unidades de data_variables.json inconsistentes: 6 de 6 variáveis com unidade diferente do mapeamento canônico (ex.: Velocidade - Porta 2 [mm/s] × Velocidade do eixo (rpm)).<!--/-->
  *Mitigação:* <!--{limites.linhas[id=dados_nomes].mitigacao|s}-->Mapeamento canônico em sensores.json por descrição e magnitude, confirmado pelo dono do projeto; o verificador exige a grandeza e a unidade do alerta no texto.<!--/-->
  *Risco residual:* <!--{limites.linhas[id=dados_nomes].risco_residual|s}-->Se o mapeamento canônico estiver errado, o assistente cita grandeza e unidade erradas com a mesma confiança; a evidência é só a descrição de cada variável.<!--/-->
- **Sem baseline por motor.** <!--{limites.linhas[id=dados_baseline].limite|s}-->Sem baseline histórico por motor: 1 ativo, 43123 leituras em 110 dias e limiares fixos; só 34 leituras estão sem alerta moderado ou crítico nas 24 h anteriores.<!--/-->
  *Mitigação:* <!--{limites.linhas[id=dados_baseline].mitigacao|s}-->O estado operacional vem só dos alertas determinísticos do instante; nenhum prognóstico nem comparação com histórico é afirmado.<!--/-->
  *Risco residual:* <!--{limites.linhas[id=dados_baseline].risco_residual|s}-->O cenário preventivo é demonstrado em operação normal: o assistente não sabe se um valor é normal para este motor, só se cruzou o limiar de active_assets.json.<!--/-->

## 10. Como as críticas foram tratadas

O feedback da entrega anterior (nota 85) gerou os requisitos F1–F7. A matriz com a evidência de cada um, inclusive o que ficou **parcial**,
está em [`matriz-criticas.md`](matriz-criticas.md). Em uma linha: F1, F2, F4, F5, F6 e F7 têm evidência nas saídas executadas; F3 entrou na
recuperação, mas **não melhorou** a recuperação medida (seção 7.2).
