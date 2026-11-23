# Feedback da avaliação anterior (nota 85)

Transcrição fiel do feedback recebido na entrega anterior. É a fonte dos requisitos F1–F7 usados nas plans em `specs/plan/`.

> O grupo demonstrou a integração entre busca vetorial, re-ranking, LLM e memória, com notebooks executados e vinte perguntas de avaliação. Para atender integralmente ao Sprint 3, é necessário melhorar a fidelidade das narrativas: os alertas e o relatório acrescentam limites, diagnósticos e prognósticos que não estão nos dados de entrada. A avaliação do classificador precisa abranger as cinco categorias, com exemplos além dos três alertas atuais. No RAG, incluam o estado operacional na recuperação, preservem página e seção das fontes e avaliem a precisão dos chunks. Revisem o juiz automático, que atribuiu alta fidelidade mesmo reconhecendo uso de conhecimento externo.
>
> Demonstrem separadamente anomalia elétrica, mecânica e manutenção preventiva.

## Requisitos derivados

| ID | Requisito | Sprint |
|---|---|---|
| F1 | Alertas e relatório só afirmam o que está nos dados de entrada: sem limites, diagnósticos ou prognósticos inventados | 3 |
| F2 | Classificador avaliado nas 5 categorias, com exemplos além dos 3 alertas | 3 |
| F3 | Estado operacional entra na recuperação (não só no prompt) | 4 |
| F4 | Página e seção das fontes preservadas e citadas | 4 |
| F5 | Precisão dos chunks avaliada contra gabarito | 4 |
| F6 | Juiz automático revisado: conhecimento externo não conta como fiel | 4 |
| F7 | Anomalia elétrica, anomalia mecânica e manutenção preventiva demonstradas separadamente | 4 |
