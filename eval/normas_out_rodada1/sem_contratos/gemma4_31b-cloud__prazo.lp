%! prazo_base | Art. 151, I e II | Cálculo do prazo máximo com acréscimo por regime
prazo_base(D + (D * 50 / 100)) :- integral, duracao_minima(D).
prazo_base(D + (D * 75 / 100)) :- parcial, duracao_minima(D).

%! prazo_portaria | Portaria ProGrad 566/2022, Art. 27 | Acréscimo de 2 semestres para ingressos 2020-2022
bonus_portaria(2) :- ano_ingresso(A), A >= 2020, A <= 2022.
bonus_portaria(0) :- ano_ingresso(A), A < 2020.
bonus_portaria(0) :- ano_ingresso(A), A > 2022.

%! prazo_maximo | Art. 151 e Portaria 566/2022 | Prazo final arredondado para cima
prazo_maximo(N) :- 
    prazo_base(B), 
    bonus_portaria(Bonus), 
    N = B + Bonus.

%! semestres_computados | Art. 146 | Semestres que contam para integralização (exclui trancados)
semestres_computados(S) :- 
    ingresso(P0), 
    periodo_atual(P), 
    Total = P - P0 + 1, 
    #count { T : trancamento(T, _) } = Trancados, 
    S = Total - Trancados.

%! semestres_restantes | Art. 151 | Diferença entre prazo máximo e tempo computado
semestres_restantes(R) :- 
    prazo_maximo(M), 
    semestres_computados(S), 
    R = M - S.

%! risco_cancelamento_prazo | Art. 145, VI | Risco por exceder prazo de integralização
risco_cancelamento(prazo_excedido) :- 
    semestres_restantes(R), 
    R < 0.

%! reprovacao_total_frequencia_periodo | Art. 145, VIII | Reprovado por freq em 100% das UCs do período
reprovacao_total_frequencia_periodo(P) :- 
    periodo(P), 
    #count { C : matricula(C, P) } = Total, 
    Total > 0, 
    #count { C : matricula(C, P), reprovado_frequencia(C, P) } = Total.

%! risco_cancelamento_freq | Art. 145, VIII | Risco por reprovação total por freq em 2 semestres consecutivos
risco_cancelamento(reprovacao_total_frequencia) :- 
    reprovacao_total_frequencia_periodo(P), 
    reprovacao_total_frequencia_periodo(P-1).