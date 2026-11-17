%! integralizacao | Art. 104 | O estudante deve cursar todas as UCs da matriz curricular conforme carga horária exigida.
% Um componente é considerado cumprido se houver registro de horas e estas forem >= às exigidas.
cumprido(Comp) :- 
    exigido(Comp, H_exigida), 
    horas(Comp, H_cumprida), 
    H_cumprida >= H_exigida.

% falta(Comp, D): componente da matriz com D horas abaixo do exigido.
falta(Comp, D) :- 
    exigido(Comp, H_exigida), 
    horas(Comp, H_cumprida), 
    H_cumprida < H_exigida, 
    D = H_exigida - H_cumprida.

falta(Comp, D) :- 
    exigido(Comp, H_exigida), 
    not horas(Comp, _), 
    D = H_exigida.

%! conclusao | Art. 160, caput | O estudante é concluinte se todas as exigências de integralização do PPC forem satisfeitas.
integralizacao_satisfeita :- 
    not existe_falta.

existe_falta :- 
    falta(_, _).

%! aptidao | Art. 160 | O estudante está apto a colar grau se a integralização estiver satisfeita e a documentação regularizada.
% Conforme Art. 160 § 2º, a documentação regularizada é requisito. 
% Como não há predicado de entrada para irregularidade, a condição de documentação é tratada como satisfeita 
% a menos que fosse fornecido um fato contrário.
apto_colar_grau :- 
    integralizacao_satisfeita.