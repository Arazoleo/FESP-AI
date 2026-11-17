%! comp_falta | Art. 104 | calcula horas faltantes para cada componente exigido
% Se o componente não tem registro de horas cumpridas, considera‑se 0 hora cumprida.
falta(Comp, D) :- 
    exigido(Comp, Req), 
    not horas(Comp, _),          % nenhum registro de carga cumprida
    D = Req,                     % todas as horas exigidas faltam
    D > 0.

% Se há registro de carga cumprida, calcula a diferença positiva.
falta(Comp, D) :- 
    exigido(Comp, Req), 
    horas(Comp, Cum), 
    D = Req - Cum, 
    D > 0.

%! apto_colar_grau | Art. 160 | verifica se não há faltas de carga horária
% Quando não existe nenhum fato falta/2, todas as exigências de integralização
% foram satisfeitas e o estudante está apto a colar grau.
apto_colar_grau :- not falta(_, _).