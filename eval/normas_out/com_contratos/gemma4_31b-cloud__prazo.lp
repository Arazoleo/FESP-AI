%! prazo_base | Art. 151, I e II | Cálculo do prazo máximo com acréscimo por regime de curso
prazo_base(D * 3 / 2) :- integral, duracao_minima(D).
prazo_base(D * 7 / 4) :- parcial, duracao_minima(D).

%! arredondamento | Art. 151, § 2º | Arredondamento para cima do prazo fracionado
% Como a aritmética do clingo é inteira, a multiplicação por 3/2 ou 7/4 pode truncar.
% Para arredondar para cima: (A + B - 1) / B.
prazo_arredondado(N) :- integral, duracao_minima(D), N = (D * 3 + 1) / 2.
prazo_arredondado(N) :- parcial, duracao_minima(D), N = (D * 7 + 3) / 4.

%! bonus_prograd | Portaria ProGrad 566/2022, Art. 27º | Acréscimo de 2 semestres para ingressos 2020-2022
bonus_prograd(2) :- ano_ingresso(A), A >= 2020, A <= 2022.
bonus_prograd(0) :- not bonus_prograd(2).

%! prazo_maximo | Art. 151 e Portaria 566/2022 | Prazo final de integralização
prazo_maximo(N) :- prazo_arredondado(B), bonus_prograd(S), N = B + S.

%! semestres_computados | Art. 146 | Contagem de semestres excluindo trancamentos
% Um semestre é computado se houve matrícula ou se é o período atual, exceto se houve trancamento.
semestre_computado(P) :- periodo(P), not trancamento(P, _).
semestre_computado(P) :- periodo_atual(P), not trancamento(P, _).

%! total_computado | Auxiliar | Soma de semestres decorridos desde o ingresso
% O cálculo inicia do ingresso (P0).
total_computado(T) :- ingresso(P0), periodo_atual(P), 
                     T = #count { P1 : P1 >= P0, P1 <= P, semestre_computado(P1) }.

%! semestres_restantes | Art. 151 | Diferença entre prazo máximo e tempo computado
semestres_restantes(R) :- prazo_maximo(M), total_computado(T), R = M - T.

%! reprovacao_total_semestre | Art. 145, VIII | Reprovado por frequência em 100% das UCs do semestre
uc_matriculada(C, P) :- matricula(C, P).
reprovado_frequencia_total(P) :- periodo(P), 
                                 #count { C : uc_matriculada(C, P) } = N, 
                                 N > 0,
                                 #count { C : uc_matriculada(C, P), reprovado_frequencia(C, P) } = N.

%! risco_cancelamento_frequencia | Art. 145, VIII | Reprovação total por frequência em 2 semestres consecutivos
risco_cancelamento(reprovacao_total_frequencia) :- reprovado_frequencia_total(P), 
                                                  reprovado_frequencia_total(P + 1).

%! risco_cancelamento_prazo | Art. 145, VI | Cancelamento por exceder prazo máximo de integralização
risco_cancelamento(prazo_excedido) :- semestres_restantes(R), R < 0.