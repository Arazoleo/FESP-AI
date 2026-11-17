%! 104 | Art. 104 | Students must complete all required components with required hours

% Auxiliary predicate: component with its completed hours
completo(Comp, H) :- horas(Comp, H).

% If a required component has no completed hours, it is considered missing
falta(Comp, D) :-
    exigido(Comp, Req),
    not completo(Comp, _),
    D = Req.

% If a required component is completed but with insufficient hours
falta(Comp, D) :-
    exigido(Comp, Req),
    completo(Comp, H),
    H < Req,
    D = Req - H.

%! 160 | Art. 160 | Student is eligible to graduate if all integralization requirements are met

apto_colar_grau :-
    not falta(_, _).