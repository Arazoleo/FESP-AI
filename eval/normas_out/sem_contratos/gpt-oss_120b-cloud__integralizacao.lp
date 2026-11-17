%! d1 | Art. 104 | Domínio de componentes da matriz (exigidos ou com carga registrada)
comp(Comp) :- exigido(Comp,_).
comp(Comp) :- horas(Comp,_).

%! d2 | Art. 104 | Soma da carga horária cumprida por componente
horas_cumpridas(Comp, Hcum) :-
    comp(Comp),
    Hcum = #sum { H : horas(Comp, H) }.

%! d3 | Art. 104 | Detecta déficit de carga horária em componentes da matriz curricular
% D = horas exigidas - horas cumpridas (apenas quando há déficit)
falta(Comp, D) :-
    exigido(Comp, Hreq),
    horas_cumpridas(Comp, Hcum),
    Hcum < Hreq,
    D = Hreq - Hcum.

%! d4 | Art. 160 | Verifica se o estudante está apto a colar grau
% O estudante está apto quando não existe nenhum componente com falta de carga horária
apto_colar_grau :- not falta(_, _).