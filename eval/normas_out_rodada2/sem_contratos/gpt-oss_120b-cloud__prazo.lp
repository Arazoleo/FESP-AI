%! duracao_minima | Art. 151, I‑II | duração mínima do curso em semestres (PPC)
dur_min(D) :- duracao_minima(D).

%! extra_percentual | Art. 151, I‑II | percentual de acréscimo segundo o regime
extra_percentual(integral, 50) :- integral.
extra_percentual(parcial, 75)  :- parcial.

%! extra_semestres | Art. 151, I‑II | número de semestres de acréscimo (arredondado para cima)
extra_semestres(Regime, Extra) :-
    dur_min(D),
    extra_percentual(Regime, Pct),
    Numer = D * Pct,
    Extra = (Numer + 99) / 100.          % ceil(D*Pct/100)

%! extra_ano_ingresso | Portaria ProGrad 566/2022, Art. 27º | +2 semestres para ingressantes 2020‑2022
extra_ano_ingresso(2) :- ano_ingresso(A), A >= 2020, A <= 2022.
extra_ano_ingresso(0) :- ano_ingresso(A), not (A >= 2020, A <= 2022).

%! prazo_maximo | Art. 151, I‑II + Portaria | prazo máximo de integralização (sem exceções do inciso III)
prazo_maximo(N) :-
    dur_min(D),
    (integral ; parcial),                % garante que um dos regimes está definido
    (integral -> Regime = integral ; Regime = parcial),
    extra_semestres(Regime, ExtraPct),
    extra_ano_ingresso(ExtraAno),
    N = D + ExtraPct + ExtraAno.

%! trancado | Art. 146 | períodos de trancamento não contam para integralização
trancado(P) :- trancamento(P,_).

%! elapsed_semestres | número de semestres decorridos desde o ingresso (contando o atual)
elapsed_semestres(E) :-
    periodo_atual(Pa),
    ingresso(P0),
    E = Pa - P0 + 1.

%! trancados_contagem | total de semestres de trancamento entre ingresso e atual
trancados_contagem(T) :-
    periodo_atual(Pa),
    ingresso(P0),
    T = #count{P : trancado(P), P >= P0, P <= Pa}.

%! semestres_computados | semestres efetivamente contabilizados para integralização
semestres_computados(C) :-
    elapsed_semestres(E),
    trancados_contagem(T),
    C = E - T.

%! semestres_restantes | prazo máximo menos semestres já computados (contando o período atual)
semestres_restantes(R) :-
    prazo_maximo(N),
    semestres_computados(C),
    R = N - C.

%! risco_cancelamento_prazo | Art. 145, VI – exceder prazo máximo de integralização
risco_cancelamento(prazo_excedido) :-
    semestres_restantes(R),
    R < 0.

%! total_enrolled | número de UCs matriculadas em um período
total_enrolled(P, E) :-
    E = #count{C : matricula(C,P)}.

%! total_reprov_frequencia | número de UCs reprovadas por frequência em um período
total_reprov_frequencia(P, R) :-
    R = #count{C : reprovado_frequencia(C,P)}.

%! total_frequencia_reprovado | 100 % das UCs matriculadas foram reprovadas por frequência
total_frequencia_reprovado(P) :-
    total_enrolled(P, E),
    total_reprov_frequencia(P, R),
    E > 0,
    E = R.

%! risco_cancelamento_frequencia | Art. 145, VIII – reprovação total por frequência em 2 semestres consecutivos
risco_cancelamento(reprovacao_total_frequencia) :-
    total_frequencia_reprovado(P),
    P1 = P + 1,
    total_frequencia_reprovado(P1).