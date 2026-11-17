%! base_prazo | Art.151 I | duração mínima do curso (semestres)
base_prazo(D) :- duracao_minima(D).

%! extensao_percentual | Art.151 I/II | acréscimo percentual (ceil)
extensao_percentual(E) :- integral, base_prazo(D), E = (D*50 + 99) / 100.
extensao_percentual(E) :- parcial,  base_prazo(D), E = (D*75 + 99) / 100.

%! extra_portaria | Portaria ProGrad 566/2022 | +2 semestres para ingresso 2020‑2022
extra_portaria(2) :- ano_ingresso(Y), Y >= 2020, Y <= 2022.
extra_portaria(0) :- not extra_portaria(2).

%! prazo_max | Art.151 | prazo máximo já com acréscimos (exclui exceção III)
prazo_maximo(N) :- base_prazo(D), extensao_percentual(E), extra_portaria(Ep), N = D + E + Ep.

%! periodo_atividade | períodos com matrícula que não são trancamentos
periodo_atividade(P) :- matricula(_,P), not trancamento(P,_).
periodo_atividade(P) :- periodo_atual(P), not trancamento(P,_).

%! semestres_cumpridos | número de períodos já computados até o atual (inclui o corrente)
semestres_cumpridos(SC) :- periodo_atual(PA), #count { P : periodo_atividade(P), P <= PA } = SC.

%! sem_rest | cálculo de semestres restantes
semestres_restantes(R) :- prazo_maximo(N), semestres_cumpridos(SC), R = N - SC.

%! risco_prazo | Inciso VI do Art.145 | prazo máximo excedido
risco_cancelamento(prazo_excedido) :- semestres_restantes(R), R < 0.

%! tem_uc | existência de ao menos uma UC em um período
tem_uc(P) :- matricula(_,P).

%! existe_uc_nao_reprovado | UC que NÃO foi reprovada por frequência no período
existe_uc_nao_reprovado(P) :- matricula(C,P), not reprovado_frequencia(C,P).

%! uc_todos_reprovado | todas as UCs do período foram reprovadas por frequência
uc_todos_reprovado(P) :- tem_uc(P), not existe_uc_nao_reprovado(P).

%! period | conjunto de períodos conhecidos (para segurança)
period(P) :- matricula(_,P).
period(P) :- periodo_atual(P).
period(P) :- trancamento(P,_).

%! consecutive | pares de períodos consecutivos (seguro)
consecutive(P,Q) :- period(P), Q = P + 1, period(Q).

%! risco_frequencia | Inciso VIII do Art.145 | reprovação total por frequência em 2 semestres consecutivos
risco_cancelamento(reprovacao_total_frequencia) :- consecutive(P,Q), uc_todos_reprovado(P), uc_todos_reprovado(Q).