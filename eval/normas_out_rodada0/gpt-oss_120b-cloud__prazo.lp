%! art151_i | Art. 151, I | cálculo do acréscimo de 50 % para cursos integrais
inc_max_integral(D,Inc) :-
    duracao_minima(D),
    Inc = (D * 50 + 99) / 100.

%! art151_ii | Art. 151, II | cálculo do acréscimo de 75 % para cursos parciais
inc_max_parcial(D,Inc) :-
    duracao_minima(D),
    Inc = (D * 75 + 99) / 100.

%! regime | identifica o regime do curso a partir dos fatos fornecidos
regime(integral) :- integral.
regime(parcial)  :- parcial.

%! prazo_base | prazo máximo base (sem acréscimo da Portaria)
prazo_base(N) :-
    duracao_minima(D),
    regime(integral),
    inc_max_integral(D,Inc),
    N = D + Inc.
prazo_base(N) :-
    duracao_minima(D),
    regime(parcial),
    inc_max_parcial(D,Inc),
    N = D + Inc.

%! extra_portaria | acréscimo de dois semestres para ingressantes de 2020‑2022 (Portaria 566/2022)
extra_portaria(2) :- ano_ingresso(A), A >= 2020, A <= 2022.
extra_portaria(0) :- not extra_portaria(2).

%! prazo_maximo | prazo máximo de integralização já com acréscimos da Portaria
prazo_maximo(N) :-
    prazo_base(Base),
    extra_portaria(Extra),
    N = Base + Extra.

%! periodo_ingresso | período de ingresso do estudante
periodo_ingresso(P0) :- ingresso(P0).

%! trancado | períodos de trancamento (não contam para integralização – Art. 146)
trancado(P) :- trancamento(P,_).

%! semestres_ate_atual | semestres decorridos desde o ingresso, descontando trancamentos
semestres_ate_atual(N) :-
    periodo_ingresso(P0),
    periodo_atual(Pa),
    Total = Pa - P0 + 1,
    Ntranc = #count{Pt : trancado(Pt), Pt >= P0, Pt <= Pa},
    N = Total - Ntranc.

%! semestres_restantes | prazo máximo menos semestres já computados
semestres_restantes(R) :-
    prazo_maximo(Max),
    semestres_ate_atual(Ja),
    R = Max - Ja.

%! risco_prazo | risco de cancelamento por exceder o prazo máximo (Art. 145, VI)
risco_cancelamento(prazo_excedido) :-
    semestres_restantes(R),
    R < 0.

%! total_uc | número total de UCs matriculadas em um período
total_uc(P,N) :-
    periodo(P),
    N = #count{C : matricula(C,P)}.

%! reprov_frequencia_uc | número de UCs reprovadas por frequência em um período
reprov_frequencia_uc(P,N) :-
    periodo(P),
    N = #count{C : matricula(C,P), reprovado_frequencia(C,P)}.

%! dois_semestres_consecutivos | verifica reprovação total por frequência em dois semestres consecutivos (Art. 145, VIII)
dois_semestres_consecutivos :-
    periodo_atual(Pa),
    P1 = Pa - 1,
    periodo(P1),
    total_uc(P1,T1), T1 > 0,
    total_uc(Pa,T2), T2 > 0,
    reprov_frequencia_uc(P1,R1), R1 = T1,
    reprov_frequencia_uc(Pa,R2), R2 = T2.

%! risco_frequencia | risco de cancelamento por reprovação total por frequência (inciso VIII)
risco_cancelamento(reprovacao_total_frequencia) :-
    dois_semestres_consecutivos.