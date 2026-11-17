%! comp_falta | Art. 104 | registra falta quando não há registro de carga cumprida
falta(Comp, D) :-
    exigido(Comp, Req),
    not horas(Comp, _),
    D = Req.

%! comp_falta | Art. 104 | registra falta quando a carga cumprida é menor que a exigida
falta(Comp, D) :-
    exigido(Comp, Req),
    horas(Comp, Cum),
    Cum < Req,
    D = Req - Cum.

%! comp_cumprido | Art. 104 | componente considerado cumprido quando a carga cumprida atende ou supera a exigida
cumprido(Comp) :-
    exigido(Comp, Req),
    horas(Comp, Cum),
    Cum >= Req.

%! apto_colar_grau | Art. 160 | estudante apto a colar grau quando não há nenhum componente com falta
apto_colar_grau :-
    not falta(_, _).