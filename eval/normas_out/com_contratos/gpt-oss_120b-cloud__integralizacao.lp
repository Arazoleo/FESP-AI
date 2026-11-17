%! faltas_horas | Art. 104 | componente da matriz com carga cumprida insuficiente
falta(Comp, D) :- exigido(Comp, He), not horas(Comp, _), D = He.
falta(Comp, D) :- exigido(Comp, He), horas(Comp, Hc), Hc < He, D = (He - Hc).

%! apto_colar_grau | Art. 160 | estudante apto a colar grau quando não há faltas
apto_colar_grau :- not falta(_, _).