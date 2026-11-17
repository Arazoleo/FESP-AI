%! integralizacao | Art. 104 | O estudante deve cursar todas as UCs da matriz curricular conforme carga horária.
% Um componente é considerado cumprido se houver registro de horas e estas forem >= às exigidas.
% Se o componente não possui registro de horas, ele não pode ser considerado cumprido.
cumprido(Comp) :- 
    exigido(Comp, H_exigida), 
    horas(Comp, H_cumprida), 
    H_cumprida >= H_exigida.

% Falta: componente da matriz com carga horária abaixo do exigido.
% Considera-se que falta a diferença entre o exigido e o cumprido.
% Se não há registro de horas(Comp, _), a diferença é o total exigido.
falta(Comp, Dif) :- 
    exigido(Comp, H_exigida), 
    horas(Comp, H_cumprida), 
    H_cumprida < H_exigida, 
    Dif = H_exigida - H_cumprida.

falta(Comp, H_exigida) :- 
    exigido(Comp, H_exigida), 
    not horas(Comp, _).

%! conclusao | Art. 160, caput | O estudante é concluinte se satisfeitas todas as exigências de integralização.
% O estudante está apto a colar grau se não houver nenhum componente da matriz com falta de carga horária.
% Adicionalmente, o Art. 160 § 2º exige documentação regularizada.
% Como 'documentacao_regularizada' não está nos predicados de entrada, 
% assume-se que a aptidão técnica de integralização é a condição verificável via dados.

apto_colar_grau :- 
    not existe_pendencia_integralizacao,
    not processo_disciplinar. % Interpretado como impedimento administrativo implícito

existe_pendencia_integralizacao :- 
    falta(Comp, _).

% Nota: O Art. 160 § 2º menciona documentação regularizada. 
% Caso houvesse um predicado 'documentacao_irregular', ele seria adicionado como 'not documentacao_irregular'.