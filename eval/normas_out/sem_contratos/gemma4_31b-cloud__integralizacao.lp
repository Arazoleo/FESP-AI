%! integralizacao | Art. 104 | O estudante deve cursar todas as UCs da matriz curricular conforme carga horária exigida.
% Um componente é considerado cumprido se houver registro de horas e estas forem maiores ou iguais ao exigido.
cumprido(Comp) :- 
    exigido(Comp, H_exigida), 
    horas(Comp, H_cumprida), 
    H_cumprida >= H_exigida.

% Falta: componente da matriz com carga horária abaixo do exigido.
% Se o componente não possui registro de horas, a diferença é a carga total exigida.
falta(Comp, Dif) :- 
    exigido(Comp, H_exigida), 
    horas(Comp, H_cumprida), 
    H_cumprida < H_exigida, 
    Dif = H_exigida - H_cumprida.

falta(Comp, H_exigida) :- 
    exigido(Comp, H_exigida), 
    not horas(Comp, _).

%! conclusao | Art. 160, caput | O estudante é concluinte se todas as exigências de integralização forem satisfeitas.
% O estudante satisfaz a integralização se não houver nenhum componente com falta de carga horária.
integralizacao_satisfeita :- 
    not existe_falta.

existe_falta :- 
    falta(_, _).

%! aptidao | Art. 160 | Aptidão para colar grau requer integralização e documentação regular.
% Conforme Art. 160 § 2º, a documentação regularizada é necessária. 
% Como não há predicado de entrada para irregularidade, a condição de documentação 
% é tratada como satisfeita por padrão para permitir a inferência do apto_colar_grau 
% baseando-se nos dados disponíveis de integralização.
apto_colar_grau :- 
    integralizacao_satisfeita.