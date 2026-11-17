%! pmax_base | Art.151 I,II | cálculo do prazo máximo sem exceções
prazo_maximo_base(N) :-
    integral,
    duracao_minima(D),
    % acréscimo de 50 % arredondado para cima
    Extra = (D + 1) / 2,
    N = D + Extra.

prazo_maximo_base(N) :-
    parcial,
    duracao_minima(D),
    % acréscimo de 75 % arredondado para cima
    Extra = (3*D + 3) / 4,
    N = D + Extra.

%! pmax_portaria | Portaria ProGrad 566/2022 | acrescimo de 2 semestres para ingressantes 2020‑2022
extra_portaria(2) :-
    ano_ingresso(A),
    A >= 2020,
    A <= 2022.

%! pmax_final | Art.151 + Portaria | prazo máximo final (sem exceção do inciso III)
prazo_maximo(N) :-
    prazo_maximo_base(B),
    extra_portaria(E),
    N = B + E.

prazo_maximo(N) :-
    prazo_maximo_base(N),
    not extra_portaria(_).

%! sem_compt | Art.146 | períodos de trancamento não contam para integralização
semestres_computados(Cnt) :-
    ingresso(P0),                % período de ingresso do estudante
    periodo_atual(PA),           % período corrente
    Cnt = #count { P : periodo(P), P >= P0, P <= PA, not trancamento(P,_) }.

%! sem_rest | cálculo de semestres restantes
semestres_restantes(R) :-
    prazo_maximo(PM),
    semestres_computados(SC),
    R = PM - SC.

%! risco_prazo | Art.145 VI | estudante excedeu o prazo máximo
risco_cancelamento(prazo_excedido) :-
    semestres_restantes(R),
    R < 0.

%! ok_uc | auxiliar – existe UC não reprovada por frequência no período
ok_uc(P) :-
    matricula(C,P),
    not reprovado_frequencia(C,P).

%! total_falha | auxiliar – todas as UCs do período foram reprovadas por frequência
total_falha(P) :-
    periodo(P),
    not ok_uc(P).

%! risco_frequencia | Art.145 VIII | reprovação total por frequência em 2 semestres consecutivos
risco_cancelamento(reprovacao_total_frequencia) :-
    total_falha(P),
    P1 = P + 1,
    total_falha(P1).