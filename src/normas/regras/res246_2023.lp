% Regulamento dos Cursos de Graduação da Unifesp - Resolução CONSU nº 246/2023
% (markdown_regimentos/regulamento_cursos_graduacao_resolucao_246_2023.md)
% + Portaria ProGrad 566/2022, Art. 27 (markdown_regimentos/secoes_oficiais_bct_site.md)
%
% Formalização ESCRITA À MÃO (condição de controle do piloto). Cada bloco começa
% com uma anotação  %! <id> | <dispositivo> | <paráfrase>  que o motor usa para
% rastrear a prova (qual artigo derivou cada conclusão).
%
% Convenções: período P = ano*2 + (semestre-1); notas ×10 (inteiros, 5,9 → 59);
% frequência em % inteiro. Vocabulário de entrada em src/normas/estado.py.
%
% Vigência (Arts. 169-170): a Resolução vale a partir de 08/01/2024 (2024/1) e
% revoga o Regimento Interno da ProGrad 2014 e a Portaria ProGrad 356/2022. Um
% fato anterior (ex.: reprovação em 2023/2) julgado por estas normas é
% anacronismo: o motor marca e só mantém a crença se o histórico confirmar.
%@ vigencia | * | 2024/1 | - | antes valia o Regimento Interno da ProGrad 2014 (revogado pelo Art. 169), não formalizado
%@ vigencia | port566_27 | 2022/1 | - | Portaria ProGrad 566/2022
%@ vigencia | port566_27_ing | 2022/1 | - | Portaria ProGrad 566/2022

%! aux_periodo | (auxiliar) | Períodos letivos em que o(a) estudante teve matrícula.
periodo(P) :- matricula(_, P).
ano_atual(A) :- periodo_atual(P), A = P / 2.

% ---------------------------------------------------------------- Frequência

%! art109 | Art. 109, caput | Frequência mínima de 75% para aprovação em uma UC.
freq_min(C, 75) :- matricula(C, _), not freq_min_propria(C).

%! art109_pu | Art. 109, parágrafo único | A Comissão de Curso pode exigir frequência mínima superior, registrada no PPC.
freq_min(C, F) :- freq_minima_ppc(C, F).
freq_min_propria(C) :- freq_minima_ppc(C, _).

%! art120_2 | Art. 120, § 2º | Quem não cumpre a frequência mínima está reprovado, independentemente de nota.
reprovado_frequencia(C, P) :- freq(C, P, F), freq_min(C, Fm), F < Fm.

% ------------------------------------------------- Aprovação por nota (média)

%! art122_I | Art. 122, I | Com frequência mínima, média inferior a 3,0: reprovado sem direito a exame.
reprovado_sem_exame(C, P) :- media10(C, P, M), M < 30, not reprovado_frequencia(C, P).

%! art122_II | Art. 122, II | Com frequência mínima, média entre 3,0 e 5,9: deve se submeter a exame.
deve_fazer_exame(C, P) :- media10(C, P, M), M >= 30, M < 60, not reprovado_frequencia(C, P).

%! art122_III | Art. 122, III | Com frequência mínima, média igual ou maior que 6,0: aprovado automaticamente.
aprovado(C, P) :- media10(C, P, M), M >= 60, not reprovado_frequencia(C, P).

% Art. 123: nota final = (média + exame)/2 >= 6,0  <=>  M + E >= 120.
% Comparação EXATA: 5,95 não vira 6,0. O Art. 120 § 3º ("computadas até a
% primeira casa decimal") admite ler arredondamento; ambiguidade registrada.
%! art123 | Art. 123 | Após exame, aprovado se (média + nota do exame)/2 for igual ou maior que 6,0.
aprovado(C, P) :- deve_fazer_exame(C, P), media10(C, P, M), exame10(C, P, E), M + E >= 120.
reprovado_nota(C, P) :- deve_fazer_exame(C, P), media10(C, P, M), exame10(C, P, E), M + E < 120.

%! art122_I_rep | Art. 122, I | Reprovação sem direito a exame é reprovação por nota.
reprovado_nota(C, P) :- reprovado_sem_exame(C, P).

% ------------------------------------- Resultado a partir da nota FINAL (histórico)

%! art120_final | Arts. 120 e 122-123 | Com a nota final registrada: aprovado se cumpriu a frequência e a nota final é igual ou maior que 6,0.
aprovado(C, P) :- nota10(C, P, N), N >= 60, not reprovado_frequencia(C, P).
reprovado_nota(C, P) :- nota10(C, P, N), N < 60, not reprovado_frequencia(C, P).

%! art106_V | Art. 106, V; Art. 136, IV | Atividades sem conceito (cumpridas) contam só o registro de cumprimento.
aprovado(C, P) :- situacao(C, P, cumprido), not reprovado_frequencia(C, P).

%! aux_reprovado | (auxiliar) | Reprovação por nota ou por frequência.
reprovado(C, P) :- reprovado_nota(C, P).
reprovado(C, P) :- reprovado_frequencia(C, P).
aprovado_alguma_vez(C) :- aprovado(C, _).
pendente(C) :- reprovado(C, _), not aprovado_alguma_vez(C).

% Verificação contra o registro oficial: a norma tem que reproduzir a situação
% que o sistema acadêmico gravou. Divergência = regra errada OU parser errado
% OU PPC com critério próprio (Art. 109, p.u.).
%! verif_registro | (verificação) | O resultado derivado das normas deve coincidir com a situação oficial do histórico.
divergencia_registro(C, P, derivado_aprovado) :- aprovado(C, P), situacao(C, P, reprovado).
divergencia_registro(C, P, derivado_reprovado) :- reprovado(C, P), situacao(C, P, aprovado).

% ------------------------------------------ Regime Especial de Recuperação (RER)

%! art130 | Art. 130, caput | Reprovado(a) por nota em apenas uma UC num período letivo pode cursá-la depois em RER.
reprovacoes_nota_no_periodo(P, K) :- periodo(P), K = #count { C : reprovado_nota(C, P) }.
candidato_rer(C) :- reprovado_nota(C, P), reprovacoes_nota_no_periodo(P, 1), pendente(C).

%! art124_I | Art. 124, I | Reprovação por frequência obriga a cursar a UC de forma presencial.
impedimento_rer(C, art124_I) :- reprovado_frequencia(C, _), pendente(C).

%! art124_II | Art. 124, II | Reprovação por nota em duas ou mais UCs obriga a cursá-las de forma presencial.
impedimento_rer(C, art124_II) :- reprovado_nota(C, P), reprovacoes_nota_no_periodo(P, K), K >= 2, pendente(C).

%! art124_III | Art. 124, III | UC que é pré-requisito de outra deve ser cursada de forma presencial.
impedimento_rer(C, art124_III) :- pendente(C), prereq(C, _).

%! art129 | Arts. 124, IV e 129 | Vedado RER em UC exclusivamente prática ou não listada pela Comissão de Curso.
impedimento_rer(C, art129) :- pendente(C), uc_pratica(C).
impedimento_rer(C, art129) :- pendente(C), rer_vedado(C).

%! art130_3 | Art. 130, § 3º; Art. 124, V | Uma UC só pode ser cursada em RER uma única vez.
impedimento_rer(C, art130_3) :- pendente(C), em_rer(C, _).

%! art130_rer | Art. 130 | Pode cursar em RER se for candidato e nenhum impedimento se aplicar.
tem_impedimento_rer(C) :- impedimento_rer(C, _).
pode_rer(C) :- candidato_rer(C), not tem_impedimento_rer(C).

%! art124 | Art. 124 | Reprovação que não pode ir para RER deve ser refeita de forma presencial.
deve_cursar_presencial(C) :- impedimento_rer(C, _).

% -------------------------------------------------------------- Trancamento

%! art148_I | Art. 148, I | É vedado o trancamento a quem está no primeiro ano do curso.
impedimento_trancar(art148_I) :- ingresso(P0), periodo_atual(P), P - P0 < 2.

%! art148_II | Art. 148, II | É vedado o trancamento a quem foi transferido(a), no mesmo ano da transferência.
impedimento_trancar(art148_II) :- transferido_no_ano(A), ano_atual(A).

%! art148_III | Art. 148, III | É vedado o trancamento a quem responde a processo disciplinar.
impedimento_trancar(art148_III) :- processo_disciplinar.

% Trancamento especial (Art. 149, § 4º) e administrativo (Art. 150, p.u.)
% não consomem o direito ao trancamento regular.
%! art147_1 | Art. 147, § 1º; Art. 149, § 4º; Art. 150, p.u. | O trancamento regular total não pode exceder 1 ano (2 semestres); especial e administrativo não contam.
semestres_trancados_regular(N) :- N = #count { P : trancamento(P, regular) }.
impedimento_trancar(art147_1) :- semestres_trancados_regular(N), N >= 2.
saldo_trancamento(2 - N) :- semestres_trancados_regular(N), N < 2.

%! art147 | Art. 147, caput | Pode trancar a pedido, respeitado o prazo do calendário, se nenhuma vedação se aplicar.
tem_impedimento_trancar :- impedimento_trancar(_).
pode_trancar :- not tem_impedimento_trancar.

% ------------------------------------------------- Prazo máximo de integralização

%! art151_I | Art. 151, I e § 2º | Curso integral: prazo máximo = duração mínima + 50%, arredondado para cima.
prazo_base(M) :- duracao_minima(D), integral, M = (D * 150 + 99) / 100.

%! art151_II | Art. 151, II e § 2º | Curso em período parcial: prazo máximo = duração mínima + 75%, arredondado para cima.
prazo_base(M) :- duracao_minima(D), parcial, M = (D * 175 + 99) / 100.

%! art151_III | Art. 151, III | Em caso excepcional aprovado pela Comissão e homologado pelo CG, até 100% acima do mínimo.
prazo_excepcional(2 * D) :- duracao_minima(D).

% "matriculados nos anos de 2020, 2021 e 2022" admite duas leituras; o código
% em produção (progresso.py) e os LLMs testados leem "ingressantes", a letra e
% a tabela do site do BCT (+2 semestres também para ingressantes até 2018)
% apontam para "teve vínculo". As duas ficam explícitas; a padrão é a literal.
%? port566 | literal | teve matrícula em algum dos anos 2020, 2021 ou 2022
%? port566 | ingressantes | ingressou em 2020, 2021 ou 2022
%! port566_27 | Portaria 566/2022, Art. 27 | Estudantes matriculados(as) em 2020, 2021 ou 2022 têm +2 semestres no prazo máximo.
vinculado_no_ano(A) :- ano_ingresso(I), ano_atual(T), A = I..T.
acrescimo_pandemia(2) :- leitura(port566, literal), vinculado_no_ano(A), A >= 2020, A <= 2022.

%! port566_27_ing | Portaria 566/2022, Art. 27 (leitura: ingressantes) | Ingressantes em 2020, 2021 ou 2022 têm +2 semestres no prazo máximo.
acrescimo_pandemia(2) :- leitura(port566, ingressantes), ano_ingresso(A), A >= 2020, A <= 2022.

%! art151_max | Art. 151; Portaria 566/2022, Art. 27 | Prazo máximo efetivo = prazo base + acréscimos aplicáveis.
tem_acrescimo :- acrescimo_pandemia(_).
prazo_maximo(M + X) :- prazo_base(M), acrescimo_pandemia(X).
prazo_maximo(M) :- prazo_base(M), not tem_acrescimo.

%! art146 | Art. 146; Art. 149, § 4º; Art. 150, p.u. | Períodos trancados não contam para a integralização.
semestres_trancados(N) :- N = #count { P : trancamento(P, _) }.
semestres_computados(K) :- ingresso(P0), periodo_atual(P), semestres_trancados(T), K = P - P0 + 1 - T.

%! art151_rest | Art. 151 | Semestres restantes = prazo máximo - semestres computados (incluindo o atual).
semestres_restantes(R) :- prazo_maximo(M), semestres_computados(K), R = M - K.

%! art145_VI | Art. 145, VI e § 2º | Exceder o prazo máximo leva ao cancelamento, salvo força maior analisada pela Comissão.
risco_cancelamento(prazo_excedido) :- semestres_restantes(R), R < 0.

%! art145_VIII | Art. 145, VIII | Reprovação por frequência em 100% das UCs por dois semestres consecutivos leva ao cancelamento.
reprovou_tudo_por_frequencia(P) :- periodo(P), N = #count { C : matricula(C, P) }, N > 0,
                                   N = #count { C : reprovado_frequencia(C, P) }.
risco_cancelamento(reprovacao_total_frequencia) :- reprovou_tudo_por_frequencia(P), reprovou_tudo_por_frequencia(P + 1).

% ------------------------------------------------------- Coeficiente de Rendimento

%! art136 | Art. 136 | Fora do CR: aproveitamento de estudos, TCC, AC, estágio e UCs sem nota.
fora_do_cr(C, P) :- situacao(C, P, aproveitamento).
fora_do_cr(C, P) :- matricula(C, P), natureza(C, tcc).
fora_do_cr(C, P) :- matricula(C, P), natureza(C, estagio).
fora_do_cr(C, P) :- matricula(C, P), natureza(C, ac).

%! art135_I | Arts. 133 e 135, I e III | Entram no CR a nota e a carga horária das UCs sem reprovação por frequência (inclusive RER).
cr_parcela(C, P, N, H) :- nota10(C, P, N), carga(C, H), not reprovado_frequencia(C, P), not fora_do_cr(C, P).

%! art135_II | Art. 135, II | Reprovação por frequência entra no CR com nota zero.
cr_parcela(C, P, 0, H) :- nota10(C, P, _), carga(C, H), reprovado_frequencia(C, P), not fora_do_cr(C, P).

% CR = sum(N*H)/sum(H); ×1000 com divisão inteira = truncado na 3ª casa (Art. 132 § 1º).
%! art134 | Arts. 132 § 1º e 134 | CR acumulado = média das notas ponderada pela carga horária, truncada na 3ª casa decimal.
cr_soma(S, T) :- S = #sum { N * H, C, P : cr_parcela(C, P, N, H) },
                 T = #sum { H, C, P : cr_parcela(C, P, _, H) }.
cr_x1000(S * 100 / T) :- cr_soma(S, T), T > 0.

% -------------------------------------------------------- Integralização / colação

%! art104 | Art. 104; matriz ATIVA (SIIU) | Para integralizar, cada componente da matriz deve atingir a carga exigida.
falta(Comp, E - H) :- exigido(Comp, E), horas(Comp, H), H < E.
a_confirmar(Comp) :- exigido(Comp, _), not tem_horas(Comp).
tem_horas(Comp) :- horas(Comp, _).

%! art160 | Art. 160 | Satisfeitas todas as exigências de integralização, o(a) estudante fica apto(a) a colar grau.
tem_falta :- falta(_, _).
tem_a_confirmar :- a_confirmar(_).
tem_exigencia :- exigido(_, _).
apto_colar_grau :- tem_exigencia, not tem_falta, not tem_a_confirmar.
