%! base_max | Art. 151 I,II | cálculo do prazo máximo sem acréscimos (regime integral ou parcial)
base_max(N) :- duracao_minima(D), integral,   N = (D*3 + 1) / 2.   % 50 % de acréscimo → ceil(D*3/2)
base_max(N) :- duracao_minima(D), parcial,    N = (D*7 + 3) / 4.   % 75 % de acréscimo → ceil(D*7/4)

%! ingresso_2020_2022 | Portaria ProGrad 566/2022 Art.27 | identifica estudantes ingressantes 2020‑2022
ingresso_2020_2022 :- ano_ingresso(A), A >= 2020, A <= 2022.

%! acrescimo_portaria | Portaria ProGrad 566/2022 Art.27 | +2 semestres para ingressantes 2020‑2022
acrescimo_portaria(2) :- ingresso_2020_2022.
acrescimo_portaria(0) :- not ingresso_2020_2022.

%! prazo_maximo | Art. 151 + Portaria | prazo máximo de integralização (sem exceção do inciso III)
prazo_maximo(N) :- base_max(B), acrescimo_portaria(Ac), N = B + Ac.

%! semestres_ate_atual | contagem de semestres desde o ingresso, excluindo períodos de trancamento (Art. 146)
semestres_ate_atual(N) :-
    ingresso(P0),
    periodo_atual(Pa),
    Tr = #count { Pi : periodo(Pi), Pi >= P0, Pi <= Pa, trancamento(Pi,_) },
    N = (Pa - P0 + 1) - Tr.

%! semestres_restantes | prazo máximo menos semestres já computados
semestres_restantes(R) :- prazo_maximo(PM), semestres_ate_atual(SA), R = PM - SA.

%! risco_prazo_excedido | Art. 145 VII | estudante excedeu o prazo máximo
risco_cancelamento(prazo_excedido) :- semestres_restantes(R), R < 0.

%! matricula_nao_reprovado | auxilia: há matrícula que não foi reprovada por frequência
matricula_nao_reprovado(P) :- matricula(C,P), not reprovado_frequencia(C,P).

%! reprovado_total_frequencia | todas as UCs matriculadas no semestre foram reprovadas por frequência
reprovado_total_frequencia(P) :- periodo(P), not matricula_nao_reprovado(P).

%! risco_reprovacao_frequencia | Art. 145 VIII | reprovação total por frequência em dois semestres consecutivos
risco_cancelamento(reprovacao_total_frequencia) :-
    reprovado_total_frequencia(P),
    P1 = P + 1,
    reprovado_total_frequencia(P1).