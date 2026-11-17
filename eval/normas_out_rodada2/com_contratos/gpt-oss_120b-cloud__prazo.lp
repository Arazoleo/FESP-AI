%! pmax | Art.151 I,II | cálculo do prazo máximo com acréscimos de regime (sem exceção III)
mult(150) :- integral.
mult(175) :- parcial.

% prazo máximo sem acréscimo da Portaria
prazo_maximo(N) :-
    duracao_minima(D),
    mult(Mult),
    N0 = (D * Mult + 99) / 100,
    N = N0,
    not prograd_acrescimo(_).

% prazo máximo com acréscimo da Portaria ProGrad 566/2022, Art.27
prazo_maximo(N) :-
    duracao_minima(D),
    mult(Mult),
    N0 = (D * Mult + 99) / 100,
    prograd_acrescimo(Inc),
    N = N0 + Inc.

%! prograd | Portaria ProGrad 566/2022, Art.27 | acréscimo de 2 semestres para estudantes matriculados em 2020‑2022
prograd_acrescimo(2) :-
    matricula(_,P),
    Ano = P / 2,
    Ano >= 2020, Ano <= 2022.

%! sem_comp | contagem de semestres já computados excluindo períodos de trancamento (Art.146)
semestres_computados(N) :-
    ingresso(P0),
    periodo_atual(Pa),
    N = #count { Pp : P0 <= Pp, Pp <= Pa, not trancamento(Pp, _) }.

%! sem_rest | cálculo de semestres restantes até o prazo máximo
semestres_restantes(R) :-
    prazo_maximo(PM),
    semestres_computados(SC),
    R = PM - SC.

%! risco_prazo | risco de cancelamento por ultrapassar o prazo máximo (Art.145 VI)
risco_cancelamento(prazo_excedido) :-
    semestres_restantes(R),
    R < 0.

%! total_falha | todas as UCs do período foram reprovadas por frequência
total_falha(P) :-
    periodo(P),
    not existe_uc_nao_reprovada(P).

existe_uc_nao_reprovada(P) :-
    matricula(C,P),
    not reprovado_frequencia(C,P).

%! risco_frequencia | risco de cancelamento por reprovação total por frequência em 2 semestres consecutivos (Art.145 VIII)
risco_cancelamento(reprovacao_total_frequencia) :-
    total_falha(P),
    total_falha(P1),
    P1 = P + 1.