%! integralizacao | Art. 104 | O estudante deve cursar todas as UCs da matriz curricular conforme carga horária exigida.
% Um componente é considerado cumprido se houver registro de horas e estas forem >= à exigida.
% Se o componente não possui registro de horas, ele não pode ser considerado cumprido.
cumprido(Comp) :- 
    exigido(Comp, H_exigida), 
    horas(Comp, H_cumprida), 
    H_cumprida >= H_exigida.

% Falta: componente da matriz com D horas abaixo do exigido.
% D = H_exigida - H_cumprida.
% Se não houver registro de horas, considera-se que cumpriu 0 horas.
falta(Comp, D) :- 
    exigido(Comp, H_exigida), 
    not horas(Comp, _), 
    D = H_exigida.

falta(Comp, D) :- 
    exigido(Comp, H_exigida), 
    horas(Comp, H_cumprida), 
    H_cumprida < H_exigida, 
    D = H_exigida - H_cumprida.

%! conclusao | Art. 160, caput | O estudante é concluinte se todas as exigências de integralização estiverem satisfeitas.
% O estudante está apto a colar grau se não houver nenhum componente da matriz com falta de horas.
% Adicionalmente, o Art. 160 § 2º exige documentação regularizada.
% Como 'documentacao_regularizada' não consta nos predicados de entrada, 
% assume-se que a verificação de aptidão baseia-se nas exigências de integralização verificáveis via dados.

apto_colar_grau :- 
    not existe_pendencia_integralizacao.

existe_pendencia_integralizacao :- 
    falta(Comp, _).

% Nota: O Art. 160 § 2º menciona documentação regularizada. 
% Caso houvesse um predicado 'documentacao_irregular', a regra seria:
% apto_colar_grau :- not existe_pendencia_integralizacao, not documentacao_irregular.