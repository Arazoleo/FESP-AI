%! prazo_max | Art. 151 | calcula prazo máximo de integralização com acréscimos
inc_integral(D,I) :- duracao_minima(D), I = (D * 50) / 100.
inc_parcial(D,I) :- duracao_minima(D), I = (D * 75) / 100.
portaria(2) :- ano_ingresso(A), A >= 2020, A <= 2022.
portaria(0) :- not portaria(2).
prazo_maximo(N) :-
    duracao_minima(D),
    integral,
    inc_integral(D,I),
    N0 = D + I,
    portaria(A),
    N = N0 + A.
prazo_maximo(N) :-
    duracao_minima(D),
    parcial,
    inc_parcial(D,I),
    N0 = D + I,
    portaria(A),
    N = N0 + A.

%! semestres_restantes | Art. 151 | calcula semestres restantes
count_semestres(C) :- C = #count{P: matricula(_,P), P <= periodo_atual}.
semestres_restantes(R) :-
    prazo_maximo(N),
    count_semestres(C),
    R = N - C.

%! risco_cancelamento | Art. 145 | risco de cancelamento por prazo excedido
risco_cancelamento(prazo_excedido) :-
    semestres_restantes(R),
    R < 0.

%! risco_cancelamento | Art. 145 | risco de cancelamento por reprovação total de frequência
some_uc_not_reprovado(P) :- matricula(C,P), not reprovado_frequencia(C,P).
risco_cancelamento(reprovacao_total_frequencia) :-
    periodo(P),
    P1 = P + 1,
    periodo(P1),
    matricula(_,P),
    matricula(_,P1),
    not some_uc_not_reprovado(P),
    not some_uc_not_reprovado(P1).