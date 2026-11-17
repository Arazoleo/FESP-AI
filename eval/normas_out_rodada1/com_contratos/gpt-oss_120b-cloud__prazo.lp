%! base_max | Art.151 I,II | calcula o prazo máximo básico (sem exceções)
base_max(N) :- duracao_minima(D), integral,   Extra = (D + 1) / 2,   N = D + Extra.
base_max(N) :- duracao_minima(D), parcial,   Extra = (D * 75 + 99) / 100, N = D + Extra.

%! prograd_extra | Portaria ProGrad 566/2022 | acréscimo de 2 semestres para ingressos 2020‑2022
prograd_extra(2) :- ingresso(_), ano_ingresso(A), A >= 2020, A <= 2022.
prograd_extra(0) :- not prograd_extra(2).

%! prazo_maximo | Art.151 + Portaria | prazo máximo definitivo (sem o caso excepcional III)
prazo_maximo(N) :- base_max(B), prograd_extra(E), N = B + E.

%! trancados_contagem | Art.146 | número de períodos de trancamento entre ingresso e atual
trancados_contagem(T) :-
    ingresso(P0), periodo_atual(Pa),
    T = #count{ P : trancamento(P,_) , P0 <= P, P <= Pa }.

%! elapsed_semestres | cálculo dos semestres já computados (descontando trancamentos)
elapsed_semestres(E) :-
    ingresso(P0), periodo_atual(Pa), trancados_contagem(T),
    E = (Pa - P0) + 1 - T.

%! semestres_restantes | prazo máximo menos o já computado
semestres_restantes(R) :- prazo_maximo(N), elapsed_semestres(E), R = N - E.

%! risco_prazo_excedido | Art.145 VI | risco por ultrapassar o prazo máximo
risco_cancelamento(prazo_excedido) :- semestres_restantes(R), R < 0.

%! existe_not_reprovado | auxiliares para Art.145 VIII
existe_not_reprovado(P) :- matricula(C,P), not reprovado_frequencia(C,P).

%! total_frequencia_reprovado | Art.145 VIII | semestre em que todas as UCs foram reprovadas por frequência
total_frequencia_reprovado(P) :- matricula(_,P), not existe_not_reprovado(P).

%! risco_reprovacao_total | Art.145 VIII | duas ocorrências consecutivas
risco_cancelamento(reprovacao_total_frequencia) :-
    total_frequencia_reprovado(P),
    total_frequencia_reprovado(P1),
    P1 = P + 1.