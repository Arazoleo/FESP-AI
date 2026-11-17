%! prazo_base | Art. 151, I e II | Cálculo do prazo base com acréscimo por regime
prazo_base(D + (D * 50 / 100)) :- integral, duracao_minima(D).
prazo_base(D + (D * 75 / 100)) :- parcial, duracao_minima(D).

%! prazo_portaria | Portaria ProGrad 566/2022, Art. 27 | Acréscimo de 2 semestres para ingressos 2020-2022
acrescimo_portaria(2) :- ano_ingresso(A), A >= 2020, A <= 2022.
acrescimo_portaria(0) :- not acrescimo_portaria(2).

%! prazo_maximo | Art. 151 e Portaria 566/2022 | Prazo final arredondado para cima
prazo_maximo(N) :- 
    prazo_base(B), 
    acrescimo_portaria(S), 
    N = B + S.

%! semestres_computados | Art. 146 | Contagem de semestres para integralização (exclui trancamentos)
periodo_computado(P) :- 
    periodo(P), 
    not trancamento(P, _).

%! semestres_restantes | Art. 151 | Diferença entre prazo máximo e semestres computados
% Calcula a quantidade de semestres computados até o período anterior ao atual
computados_anteriores(C) :- 
    #count { P : periodo_computado(P), periodo_atual(PA), P < PA } = C.

% O período atual conta se não estiver trancado
atual_computado(1) :- periodo_atual(PA), not trancamento(PA, _).
atual_computado(0) :- periodo_atual(PA), trancamento(PA, _).

semestres_restantes(R) :- 
    prazo_maximo(M), 
    computados_anteriores(C), 
    atual_computado(A), 
    R = M - (C + A).

%! reprovacao_total_frequencia | Art. 145, VIII | Reprovado por freq em 100% das UCs por 2 semestres consecutivos
todas_reprovadas_freq(P) :- 
    periodo(P), 
    #count { C : matricula(C, P) } = Total, 
    Total > 0, 
    #count { C : matricula(C, P), reprovado_frequencia(C, P) } = Total.

risco_cancelamento(reprovacao_total_frequencia) :- 
    periodo_atual(P), 
    todas_reprovadas_freq(P), 
    todas_reprovadas_freq(P - 1).

%! risco_prazo | Art. 145, VI | Risco de cancelamento por exceder prazo de integralização
risco_cancelamento(prazo_excedido) :- 
    semestres_restantes(R), 
    R < 0.