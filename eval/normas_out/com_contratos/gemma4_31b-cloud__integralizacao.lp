%! integralizacao | Art. 104 | O estudante deve cursar todas as UCs da matriz curricular conforme carga horária.
% Um componente é considerado cumprido se houver registro de horas e estas forem >= às exigidas.
cumprido(Comp) :- 
    exigido(Comp, H_exigida), 
    horas(Comp, H_cumprida), 
    H_cumprida >= H_exigida.

% Falta: componente da matriz com carga horária abaixo do exigido.
% Se o componente não tem registro de horas, a falta é a carga total exigida.
falta(Comp, Diferenca) :- 
    exigido(Comp, H_exigida), 
    horas(Comp, H_cumprida), 
    H_cumprida < H_exigida, 
    Diferenca = H_exigida - H_cumprida.

falta(Comp, H_exigida) :- 
    exigido(Comp, H_exigida), 
    not horas(Comp, _).

%! conclusao | Art. 160, caput | O estudante é concluinte se todas as exigências de integralização forem satisfeitas.
% O estudante satisfaz a integralização se não houver nenhum componente da matriz com falta de horas.
integralizacao_satisfeita :- 
    not existe_falta.

existe_falta :- 
    falta(_, _).

%! aptidao | Art. 160 | O estudante está apto a colar grau se integralizou o curso.
% Nota: O § 2º exige documentação regularizada, porém não há predicado de entrada para tal.
% Conforme a lógica de formalização, a aptidão depende das exigências verificáveis via dados.
apto_colar_grau :- 
    integralizacao_satisfeita.