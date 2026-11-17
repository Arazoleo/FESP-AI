%! falta_horas | Art. 104 | Detecta déficit de carga horária de componente exigido
falta(Comp, Def) :-
    exigido(Comp, Req),
    horas(Comp, Cum),
    Def = Req - Cum,
    Def > 0.

%! falta_sem_carga | Art. 104 | Quando não há registro de carga cumprida, considera‑se todo o requisito pendente
falta(Comp, Req) :-
    exigido(Comp, Req),
    not horas(Comp, _).

%! apto_integralizacao | Art. 160 | O estudante está apto a colar grau quando não há nenhum déficit de carga horária
apto_colar_grau :-
    not falta(_, _).