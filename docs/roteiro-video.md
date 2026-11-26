# Roteiro do vídeo (3 a 5 minutos)

Duração total prevista: **4 min 40 s** (30 + 40 + 50 + 50 + 50 + 40 + 20 = 280 s). Gravação feita pelo dono do
projeto; este arquivo é só o roteiro. Fala em português, ritmo calmo, uma ideia por cena.

| # | Cena | Tempo | Acumulado |
|---|---|---|---|
| 1 | Abertura e arquitetura | 30 s | 0:30 |
| 2 | Alerta fiel e verificador | 40 s | 1:10 |
| 3 | Cenário elétrico | 50 s | 2:00 |
| 4 | Cenário mecânico | 50 s | 2:50 |
| 5 | Cenário preventivo | 50 s | 3:40 |
| 6 | Avaliação e limites | 40 s | 4:20 |
| 7 | Fechamento | 20 s | 4:40 |

Total: **4 min 40 s**, dentro da faixa de 3 a 5 minutos. Sobram 20 s de folga até o limite de 5 minutos; não acrescente cena.

## Antes de gravar

- Execute os dois notebooks localmente e abra-os já executados; use as saídas existentes (não rode células ao vivo).
- **Não exiba a chave.** Não abra o `.env`, não mostre a célula de configuração com a variável e feche terminais com variáveis de ambiente.
- Zoom do notebook em 125 % ou mais, para a saída ser legível.

## Cenas

### 1. Abertura e arquitetura (30 s)
- **Tela:** `docs/relatorio-final.md`, diagrama da seção 1.
- **Dizer:** "Este é o assistente de troubleshooting do motor WEG W22. Os dados viram alertas; os alertas viram o estado operacional; o estado entra na
  busca sobre o catálogo; o assistente responde citando página e seção. Todo fato nasce de código e o LLM só redige, sempre sob verificador."

### 2. Alerta fiel e verificador (40 s)
- **Tela:** `sprint3_pln_alertas.ipynb`, seção 5 (os três templates) e seção 6 (exemplo rejeitado pelo verificador).
- **Dizer:** "Três templates, para alerta leve, moderado e crítico, com tom diferente. Quando o LLM reescreve, o verificador confere número, grandeza, ação e
  termos proibidos; se reprovar, fica o template. Aqui o texto com um limite inventado foi rejeitado." Mostrar a taxa de aceitação e a fidelidade dos templates.

### 3. Cenário elétrico (50 s)
- **Tela:** `sprint4_pln_rag.ipynb`, seção 15: estado do alerta de corrente, os três turnos, fontes `[p., seç.]`, confiança.
- **Dizer:** "O estado vem de um alerta crítico real de corrente. O operador pergunta pela sobrecorrente; a resposta cita página e seção. O seguimento usa
  a memória. A terceira pergunta o catálogo não responde, e o assistente se abstém sem chamar o LLM."

### 4. Cenário mecânico (50 s)
- **Tela:** seção 16: alerta crítico de vibração, resposta sobre os níveis de vibração, o seguimento sobre lubrificação.
- **Dizer:** "Agora vibração acima do limite. A fonte esperada é recuperada. No seguimento o assistente se absteve mesmo com a página certa recuperada:
  isso é um limite que documentamos, não escondemos."

### 5. Cenário preventivo (50 s)
- **Tela:** seção 17: estado em operação normal, pergunta sobre lubrificação dos rolamentos, seguimento sobre monitorar a temperatura.
- **Dizer:** "Aqui não há alerta moderado ou crítico: é operação normal, e a pergunta é de manutenção preventiva. As respostas citam o catálogo. Sem baseline
  histórico por motor, o assistente só diz o que o catálogo afirma."

### 6. Avaliação e limites (40 s)
- **Tela:** seções 10 a 13 (recuperação, juiz por afirmação) e seção 18 (tabela de limites); ou o `docs/relatorio-final.md`, seções 7 e 9.
- **Dizer:** "Medimos recuperação por página e estrita, faithfulness por afirmação, com juiz de família diferente do gerador, calibrado. O estado operacional
  entra na busca, mas não melhorou a recuperação; dizemos isso. Limites: catálogo sem troubleshooting, juiz de 12B, limiar fixo de abstenção."

### 7. Fechamento (20 s)
- **Tela:** `docs/matriz-criticas.md`.
- **Dizer:** "A matriz mostra onde cada crítica do professor foi tratada, inclusive a parcial. Repositório e documento final estão no link."

## Depois de gravar

- Publicar no YouTube como **"não listado"**.
- Colar o link no `README.md`, no lugar do comentário `<!-- VIDEO_URL -->`.
