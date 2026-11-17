%! faltas | Art. 104 | verifica carga faltante de cada componente exigido
% Se o componente exigido não tem registro de horas cumpridas, considera‑se toda a carga como faltante.
falta(Comp, Req) :- exigido(Comp, Req), not horas(Comp, _).

% Se há registro de horas, calcula a diferença quando a carga cumprida é menor que a exigida.
falta(Comp, Dif) :- 
    exigido(Comp, Req), 
    horas(Comp, Cum), 
    Cum < Req, 
    Dif = Req - Cum, Dif > 0.

%! apto | Art. 160 | verifica integralização completa do curso
% O estudante está apto a colar grau quando não há nenhum componente com falta de carga.
apto_colar_grau :- not falta(_, _).