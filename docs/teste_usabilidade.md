# FESP-AI — Roteiro de Teste Assistido de Usabilidade

Documento de apoio para sessões moderadas de teste de usabilidade do FESP-AI, assistente acadêmico neurossimbólico da UNIFESP (ICT/SJC). Pronto para impressão e compartilhamento.

---

## 1. Objetivo e método

**Objetivo.** Avaliar se estudantes conseguem, sem treinamento prévio, obter do FESP-AI respostas corretas e confiáveis para dúvidas acadêmicas reais (formatura, pré-requisitos, grade, serviços do campus, docentes), observando onde o fluxo de conversa falha, confunde ou exige reformulação.

**Método.** Teste assistido moderado, presencial ou por videochamada com compartilhamento de tela.

- Protocolo **think-aloud**: o participante verbaliza o que está pensando enquanto usa o sistema ("vou perguntar assim porque...", "não entendi essa resposta...").
- Duração alvo: **20 a 30 minutos por participante** (5 min de abertura, 15-20 min de tarefas, 5 min de perguntas finais).
- O moderador **apenas observa e anota**. Não ajuda, não sugere perguntas, não corrige o participante. Se o participante travar, o moderador pergunta "o que você faria agora?" e, persistindo o bloqueio por mais de 3 minutos, marca a tarefa como Falha e passa à seguinte.
- Cada tarefa é lida em voz alta a partir do **cenário** (Seção 3). O cenário descreve a necessidade, nunca a pergunta pronta: queremos observar como o participante formula a própria pergunta.

**Papéis.**

| Papel | Responsabilidade |
|---|---|
| Moderador | Conduz a sessão, lê os cenários, cronometra, preenche a planilha (Seção 5) |
| Participante | Usa o sistema pensando em voz alta |
| Observador (opcional) | Anota citações literais e eventos inesperados |

---

## 2. Perfil dos participantes e consentimento

**Perfil-alvo** (5 a 8 participantes):

- Estudantes de graduação da UNIFESP ICT/SJC (prioridade: BCT e cursos de saída como BCC, Engenharia de Computação, Engenharia Biomédica);
- Misturar veteranos e ingressantes (ingressantes tendem a ter as dúvidas que o sistema mais quer resolver);
- Sem contato prévio com o FESP-AI (excluir quem participou do desenvolvimento);
- Registrar no cabeçalho da planilha: curso, termo/ano de ingresso, familiaridade com chatbots (baixa/média/alta).

**Termo de consentimento (ler em voz alta e colher aceite verbal ou assinatura):**

> Você está participando de um teste do FESP-AI, um assistente acadêmico em desenvolvimento na UNIFESP. Estamos avaliando o sistema, e não você: não existem respostas certas ou erradas. A sessão dura de 20 a 30 minutos e suas interações e comentários serão anotados de forma **anonimizada**, para uso exclusivamente **acadêmico** (melhoria do sistema e eventual publicação científica agregada, sem qualquer dado que identifique você). Você pode interromper a participação a qualquer momento, sem justificativa. Você concorda em participar?

- [ ] Aceite registrado. Data: ____/____/______  Identificador do participante: P____

---

## 3. Roteiro de tarefas

Regras gerais para todas as tarefas:

- O moderador lê **somente o cenário**. Se o participante pedir "como eu pergunto isso?", responder: "pergunte do jeito que você perguntaria a um colega".
- Cronometrar do fim da leitura do cenário até o participante declarar que obteve (ou desistiu de obter) a informação.
- **Reformulação** = qualquer nova mensagem enviada porque a anterior não produziu o que o participante queria (inclui reenvio, troca de palavras e pedidos de esclarecimento ao bot).
- Classificação de sucesso: **S** (sucesso: obteve a informação-alvo sem ajuda), **P** (sucesso parcial: obteve parte da informação, ou obteve tudo mas declarou dúvida sobre a resposta), **F** (falha: desistiu, estourou 5 minutos ou aceitou resposta errada).

### Tarefa 1 — Requisitos para se formar

- **Objetivo do teste:** verificar se o participante extrai do sistema os requisitos de integralização do próprio curso (carga horária total e componentes: fixas, eletivas, extensão, atividades complementares).
- **Cenário lido ao participante:** "Você está planejando os próximos anos e quer saber o que precisa cumprir para se formar no seu curso: quantas horas no total e do que elas se compõem. Use o assistente para descobrir."
- **Critério de sucesso observável:** o participante obtém e verbaliza a carga horária total do curso (ex.: 2400 horas no BCT) e cita ao menos dois componentes (eletivas, atividades complementares, extensão).
- **Métricas:** S/P/F, tempo, número de reformulações.

### Tarefa 2 — Caminho até uma disciplina-alvo

- **Objetivo do teste:** avaliar o planejamento de trajetória no grafo de pré-requisitos (o que cursar antes de uma disciplina avançada).
- **Cenário lido ao participante:** "Você ouviu falar da disciplina de Compiladores e quer cursá-la no futuro. Descubra o que você precisaria cursar antes de conseguir se matricular nela."
- **Critério de sucesso observável:** o participante obtém a cadeia de pré-requisitos (diretos e, idealmente, o caminho completo desde as disciplinas iniciais) e demonstra entender a ordem ("primeiro isso, depois aquilo").
- **Métricas:** S/P/F, tempo, número de reformulações. Anotar se o participante notou/entendeu as indicações de confiança ou regras exibidas na resposta.

### Tarefa 3 — Montar a grade do próximo semestre

- **Objetivo do teste:** verificar se o participante consegue usar o assistente para compor uma grade viável considerando o que já cursou.
- **Cenário lido ao participante:** "Pense em duas ou três disciplinas que você já concluiu (ou invente, se preferir). Com base nisso, use o assistente para montar uma sugestão de grade para o seu próximo semestre."
- **Critério de sucesso observável:** o participante informa as disciplinas já cursadas na conversa e recebe uma sugestão de disciplinas compatível (o sistema não sugere disciplinas cujo pré-requisito não foi cumprido); o participante declara que a sugestão faz sentido.
- **Métricas:** S/P/F, tempo, número de reformulações. Anotar se o participante tentou informar as disciplinas cursadas em uma única mensagem ou em várias.

### Tarefa 4 — Materiais de apoio da DAE

- **Objetivo do teste:** avaliar a descoberta de serviços institucionais do campus (corpus do site) partindo de uma necessidade vaga.
- **Cenário lido ao participante:** "Você soube que a Divisão de Assuntos Educacionais (DAE) do campus disponibiliza materiais e orientações de apoio ao estudante. Encontre com o assistente quais são esses materiais e onde acessá-los."
- **Critério de sucesso observável:** a resposta obtida menciona a DAE (ou apoio ao estudante) com conteúdo do site institucional e inclui link/indicação de onde acessar; o participante identifica ao menos um material ou serviço concreto.
- **Métricas:** S/P/F, tempo, número de reformulações. Anotar se o participante confiou no link citado.

### Tarefa 5 — Quem leciona e como contatar

- **Objetivo do teste:** avaliar o fluxo multi-turno disciplina → docente → contato, incluindo herança de contexto ("e o e-mail dele?").
- **Cenário lido ao participante:** "Escolha uma disciplina que você pretende cursar. Descubra quem a leciona e como você faria para entrar em contato com essa pessoa."
- **Critério de sucesso observável:** o participante obtém o nome do docente e, em seguida, o contato (ou a informação honesta de que o contato não está na base), usando follow-up sem repetir o nome completo da disciplina; o sistema mantém o contexto entre os turnos.
- **Métricas:** S/P/F, tempo, número de reformulações. Anotar se o follow-up com pronome ("dele", "dela") foi entendido pelo sistema.

### Tarefa 6 — Conversa contínua sobre a matriz ("e as eletivas?")

- **Objetivo do teste:** avaliar a continuidade da conversa em uma sequência natural de follow-ups sobre o mesmo curso, sem que o participante repita o contexto.
- **Cenário lido ao participante:** "Você quer entender a estrutura do seu curso. Comece pedindo uma visão geral da matriz curricular e depois aprofunde com perguntas curtas de continuação sobre o que aparecer — por exemplo, sobre as eletivas, sobre quem coordena ou sobre alguma disciplina citada."
- **Critério de sucesso observável:** em pelo menos dois follow-ups curtos (ex.: "e as eletivas?", "quem coordena?"), o sistema herda o curso da conversa e responde sobre a entidade correta, sem recomeçar com saudação e sem trocar de assunto; o participante não precisa reescrever o nome do curso.
- **Métricas:** S/P/F, tempo, número de reformulações. Anotar cada follow-up que o sistema perdeu (respondeu sobre outra coisa ou pediu o contexto de novo).

---

## 4. Perguntas pós-tarefa e pós-teste

### 4.1 Pós-tarefa (fazer imediatamente após cada tarefa; escala 1 a 5)

1. "De 1 a 5, quão **fácil** foi completar essa tarefa?" (1 = muito difícil, 5 = muito fácil)
2. "De 1 a 5, quanto você **confia** na resposta que recebeu?" (1 = não confio, 5 = confio totalmente)

### 4.2 Pós-teste — SUS (System Usability Scale, 10 itens)

Escala de 1 (discordo totalmente) a 5 (concordo totalmente):

| # | Afirmação | 1-5 |
|---|---|---|
| 1 | Eu acho que gostaria de usar este sistema com frequência | |
| 2 | Eu achei o sistema desnecessariamente complexo | |
| 3 | Eu achei o sistema fácil de usar | |
| 4 | Eu acho que precisaria da ajuda de uma pessoa com conhecimento técnico para usar o sistema | |
| 5 | Eu achei que as diversas funções do sistema estão bem integradas | |
| 6 | Eu achei que o sistema apresenta muita inconsistência | |
| 7 | Eu imagino que a maioria das pessoas aprenderia a usar esse sistema rapidamente | |
| 8 | Eu achei o sistema muito complicado de usar | |
| 9 | Eu me senti confiante ao usar o sistema | |
| 10 | Eu precisei aprender várias coisas novas antes de conseguir usar o sistema | |

Cálculo: itens ímpares contribuem (nota - 1); itens pares contribuem (5 - nota); somar tudo e multiplicar por 2,5 (escala final 0-100).

### 4.3 Pós-teste — perguntas abertas

1. "O que mais te **confundiu** durante o uso?"
2. "O que você sentiu que **faltou** — alguma informação ou recurso que você esperava e não encontrou?"
3. "Você **confiaria** nas respostas deste assistente para tomar decisões reais de matrícula? Por quê?"

---

## 5. Planilha de anotação do moderador

Preencher uma linha por tarefa. Identificador do participante: P____  Curso: __________  Ingresso: ______  Familiaridade com chatbots: baixa / média / alta

| Tarefa | Resultado (S/P/F) | Tempo (mm:ss) | Reformulações (n) | Facilidade (1-5) | Confiança (1-5) | Erros do sistema observados | Citações e observações (think-aloud) |
|---|---|---|---|---|---|---|---|
| 1. Requisitos para se formar | | | | | | | |
| 2. Caminho até Compiladores | | | | | | | |
| 3. Montar a grade | | | | | | | |
| 4. Materiais da DAE | | | | | | | |
| 5. Docente e contato | | | | | | | |
| 6. Follow-ups da matriz | | | | | | | |

Registro pós-teste: SUS (0-100): ______  Respostas abertas anotadas no verso ou em folha anexa.

Convenções de anotação rápida durante a sessão:

- **[R]** reformulação; **[E]** resposta errada aceita pelo participante; **[H]** possível alucinação do sistema; **[C]** perda de contexto em follow-up; **[T]** demora perceptível (> 15 s) comentada pelo participante.

---

## 6. Setup da sessão (checklist do moderador)

Antes de cada sessão:

1. Abrir a demo pública em `<URL_DA_DEMO>` e confirmar que a página carrega.
2. **Aquecer o sistema** com 1 pergunta real (ex.: enviar uma pergunta sobre carga horária de um curso) antes da chegada do participante — a primeira resposta após um período ocioso é mais lenta e não deve contaminar os tempos medidos.
3. Iniciar **uma conversa nova por participante** (botão "Nova conversa" no topo do chat) — o histórico de outro participante contamina a herança de contexto das tarefas 5 e 6.
4. Conferir gravação/anotação: cronômetro, planilha da Seção 5 impressa (uma por participante), termo de consentimento à mão.
5. Em videochamada: pedir compartilhamento de tela e ativar a gravação somente após o aceite do termo.

Durante a sessão:

- Ler o cenário, não a pergunta. Não digitar pelo participante.
- Se o sistema exibir erro de servidor ou não responder em até 2 minutos, anotar o incidente, recarregar a página e repetir a tarefa uma única vez (anotar que houve repetição).

Após a sessão:

- Transcrever a planilha para a base consolidada no mesmo dia.
- Registrar bugs e alucinações observadas como itens no `BACKLOG.md`.
