%! int_falta | Art. 104 | Detecta componentes da matriz que ainda não atingiram a carga exigida
% Se não há registro de carga cumprida, considera‑se carga 0.
falta(Comp, D) :-
    exigido(Comp, Req),
    not horas(Comp, _),
    D = Req.

% Se há registro de carga cumprida, verifica o déficit.
falta(Comp, D) :-
    exigido(Comp, Req),
    horas(Comp, Cum),
    Cum < Req,
    D = Req - Cum.

%! apto_colar_grau | Art. 160 | O estudante está apto a colar grau quando não há nenhum déficit
apto_colar_grau :-
    not falta(_, _).