%! prazo_base | Art. 151, I e II | Cálculo do prazo base de integralização conforme regime do curso
prazo_base(D * 3 / 2) :- integral, duracao_minima(D).
prazo_base(D * 7 / 4) :- parcial, duracao_minima(D).

%! arredondamento | Art. 151, § 2º | Arredondamento para cima de prazos fracionados
% Nota: A aritmética de Clingo é inteira. Para simular o acréscimo de 50% (3/2) ou 75% (7/4) 
% com arredondamento para cima: (A + B - 1) / B.
prazo_base_adj(N) :- integral, duracao_minima(D), N = (D * 3 + 1) / 2.
prazo_base_adj(N) :- parcial, duracao_minima(D), N = (D * 7 + 3) / 4.

%! bonus_portaria | Portaria ProGrad 566/2022, Art. 27º | Acréscimo de 2 semestres para ingressos 2020-2022
bonus_portaria(2) :- ano_ingresso(A), A >= 2020, A <= 2022.
bonus_portaria(0) :- not bonus_portaria(2).

%! prazo_maximo | Art. 151 e Portaria 566/2022 | Prazo máximo final em semestres
prazo_maximo(N) :- prazo_base_adj(B), bonus_portaria(S), N = B + S.

%! semestres_computados | Art. 146 | Contagem de semestres para integralização (exclui trancamentos)
semestre_computado(P) :- periodo(P), not trancamento(P, _).

%! semestres_restantes | Art. 151 | Cálculo de semestres restantes
semestres_restantes(R) :- 
    prazo_maximo(M), 
    #count { P : semestre_computado(P) } = C, 
    periodo_atual(PA), 
    % Se o período atual já foi contado como computado, não soma 1.
    % A regra pede "contando o período atual".
    R = M - C.

%! risco_prazo | Art. 145, VI | Risco de cancelamento por excesso de prazo
risco_cancelamento(prazo_excedido) :- semestres_restantes(R), R < 0.

%! reprovacao_total_semestre | Art. 145, VIII | Reprovado por frequência em 100% das UCs do semestre
uc_matriculada(C, P) :- matricula(C, P).
reprovado_frequencia_total(P) :- 
    periodo(P), 
    #count { C : uc_matriculada(C, P) } = Total, 
    Total > 0,
    #count { C : uc_matriculada(C, P), reprovado_frequencia(C, P) } = Total.

%! risco_reprovacao | Art. 145, VIII | Risco de cancelamento por reprovação total em 2 semestres consecutivos
risco_cancelamento(reprovacao_total_frequencia) :- 
    periodo_atual(P), 
    reprovado_frequencia_total(P), 
    reprovado_frequencia_total(P - 1).