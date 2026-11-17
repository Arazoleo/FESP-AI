%! 104 | Art. 104 | integralização: todas as UC da matriz devem ser cursadas com carga horária exigida
horas_cumpridas(Comp, H) :- horas(Comp, H).
horas_cumpridas(Comp, 0) :- exigido(Comp, _), not horas(Comp, _).

falta(Comp, D) :- exigido(Comp, E), horas_cumpridas(Comp, H), H < E, D = E - H.

%! 160 | Art. 160 | apto_colar_grau: todas as exigências de integralização verificáveis estão cumpridas
passed(Comp, P) :- situacao(Comp, P, S), S = aprovado.
passed(Comp, P) :- situacao(Comp, P, S), S = cumprido.
passed(Comp, P) :- situacao(Comp, P, S), S = aproveitamento.

integralizado(Comp) :- exigido(Comp, _), matricula(Comp, P), passed(Comp, P).
not_integralizado(Comp) :- exigido(Comp, _), not integralizado(Comp).

apto_colar_grau :- not falta(_, _), not not_integralizado(_).