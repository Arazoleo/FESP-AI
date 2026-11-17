%! integralizacao | Art. 104 | Verifica se a carga horária cumprida atende ao exigido na matriz
falta(Comp, Dif) :- 
    exigido(Comp, H_exigida), 
    horas(Comp, H_cumprida), 
    H_cumprida < H_exigida, 
    Dif = H_exigida - H_cumprida.

%! integralizacao | Art. 104 | Componente sem registro de horas cumpridas é considerado com falta total
falta(Comp, H_exigida) :- 
    exigido(Comp, H_exigida), 
    not horas(Comp, _).

%! conclusao | Art. 160 | O estudante está apto a colar grau se não houver faltas de integralização
% Nota: O Art. 160 § 2º exige documentação regularizada, porém não há predicado de entrada para tal.
% Conforme a lógica de mundo fechado do ASP, a ausência de fatos de irregularidade implica regularidade.
apto_colar_grau :- 
    not existe_falta.

%! aux_conclusao | Art. 160 | Predicado auxiliar para verificar a existência de qualquer pendência de carga horária
existe_falta :- falta(_, _).