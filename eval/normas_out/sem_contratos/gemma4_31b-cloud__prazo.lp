%! prazo_base | Art. 151, I e II | Cálculo do prazo base de integralização conforme regime do curso
% Arredondamento para cima: (A + B - 1) / B. 
% Integral: D * 1.5 = (3*D)/2. Teto: (3*D + 2 - 1) / 2 = (3*D + 1) / 2.
% Parcial: D * 1.75 = (7*D)/4. Teto: (7*D + 4 - 1) / 4 = (7*D + 3) / 4.
prazo_base_final(N) :- integral, duracao_minima(D), N = (D * 3 + 1) / 2.
prazo_base_final(N) :- parcial, duracao_minima(D), N = (D * 7 + 3) / 4.

%! bonus_prograd | Portaria ProGrad 566/2022, Art. 27º | Acréscimo de 2 semestres para ingressos 2020-2022
bonus_prograd(2) :- ano_ingresso(A), A >= 2020, A <= 2022.
bonus_prograd(0) :- not bonus_prograd(2).

%! prazo_maximo | Art. 151 e Portaria 566/2022 | Prazo final de integralização
prazo_maximo(N) :- prazo_base_final(B), bonus_prograd(Bonus), N = B + Bonus.

%! semestres_computados | Art. 146 | Contagem de semestres para integralização (exclui trancamentos)
semestre_computado(P) :- periodo(P), not trancamento(P, _).

%! semestres_restantes | Art. 151 | Cálculo de semestres restantes
semestres_restantes(R) :- prazo_maximo(Max), #count{ P : semestre_computado(P) } = C, R = Max - C.

%! risco_prazo | Art. 145, VI | Risco de cancelamento por excesso de prazo
risco_cancelamento(prazo_excedido) :- semestres_restantes(R), R < 0.

%! reprovacao_total_semestre | Art. 145, VIII | Estudante reprovado por frequência em 100% das UCs do período
ucs_no_periodo(C, P) :- matricula(C, P).
reprovado_frequencia_total(P) :- 
    periodo(P), 
    #count{ C : ucs_no_periodo(C, P) } = Total, 
    Total > 0,
    #count{ C : ucs_no_periodo(C, P), reprovado_frequencia(C, P) } = Total.

%! risco_reprovacao | Art. 145, VIII | Risco de cancelamento por reprovação total em frequência por 2 semestres consecutivos
risco_cancelamento(reprovacao_total_frequencia) :- 
    periodo_atual(P), 
    reprovado_frequencia_total(P), 
    P > 0, 
    reprovado_frequencia_total(P - 1).