%! prazo_base | Art. 151, I e II | Cálculo do prazo máximo com acréscimo por regime
prazo_base(D * 3 / 2) :- integral, duracao_minima(D).
prazo_base(D * 7 / 4) :- parcial, duracao_minima(D).

%! arredondamento | Art. 151, § 2º | Arredondamento para cima do prazo fracionado
% Como a aritmética do clingo é inteira, o cálculo acima (D*3/2) trunca. 
% Para arredondar para cima: (A + B - 1) / B.
prazo_base_adj(N) :- integral, duracao_minima(D), N = (D * 3 + 1) / 2. % Simplificação de (D * 1.5)
% Correção rigorosa do arredondamento para cima:
prazo_base_final(N) :- integral, duracao_minima(D), N = (D * 3 + 1) / 2.
prazo_base_final(N) :- parcial, duracao_minima(D), N = (D * 7 + 3) / 4.

%! bonus_prograd | Portaria ProGrad 566/2022, Art. 27º | Acréscimo de 2 semestres para ingressos 2020-2022
bonus_prograd(2) :- ano_ingresso(A), A >= 2020, A <= 2022.

%! prazo_maximo | Art. 151 e Portaria 566/2022 | Prazo final de integralização
prazo_maximo(N) :- prazo_base_final(B), bonus_prograd(S), N = B + S.
prazo_maximo(N) :- prazo_base_final(N), not bonus_prograd(_).

%! tempo_decorrido | Art. 146 e Art. 151, § 1º | Semestres computados para integralização
% O prazo conta a partir do ingresso (ou origem em caso de transferência)
tempo_decorrido(T) :- ingresso(P0), periodo_atual(P), 
                      T = (P - P0 + 1) - total_trancado.

%! total_trancado | Art. 146 | Soma de períodos de trancamento (não contam para integralização)
total_trancado(T) :- T = #count { P : trancamento(P, _) }.

%! semestres_restantes | Art. 151 | Diferença entre prazo máximo e tempo decorrido
semestres_restantes(R) :- prazo_maximo(M), tempo_decorrido(T), R = M - T.

%! risco_prazo | Art. 145, VI | Risco de cancelamento por exceder prazo máximo
risco_cancelamento(prazo_excedido) :- semestres_restantes(R), R < 0.

%! reprovacao_total_frequencia_periodo | Art. 145, VIII | Reprovado por freq em 100% das UCs do período
reprovado_total_frequencia_periodo(P) :- 
    periodo(P), 
    #count { C : matricula(C, P) } = N, 
    N > 0, 
    #count { C : matricula(C, P), reprovado_frequencia(C, P) } = N.

%! risco_reprovacao | Art. 145, VIII | Risco por reprovação total em frequência por 2 semestres consecutivos
risco_cancelamento(reprovacao_total_frequencia) :- 
    periodo_atual(P), 
    reprovado_total_frequencia_periodo(P), 
    reprovado_total_frequencia_periodo(P - 1).