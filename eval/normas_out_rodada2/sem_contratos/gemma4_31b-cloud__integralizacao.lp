%! integralizacao | Art. 104 | Verifica se a carga horária exigida por componente foi cumprida
% Um componente tem falta se a carga cumprida for menor que a exigida.
% Se não houver registro de horas(Comp, _), o componente não é considerado cumprido.
falta(Comp, Dif) :- 
    exigido(Comp, H_exigida), 
    horas(Comp, H_cumprida), 
    H_cumprida < H_exigida, 
    Dif = H_exigida - H_cumprida.

falta(Comp, Dif) :- 
    exigido(Comp, H_exigida), 
    not horas(Comp, _), 
    Dif = H_exigida.

%! conclusao | Art. 160, caput | Define se o estudante satisfez as exigências de integralização
% O estudante satisfaz a integralização se não houver nenhum componente com falta.
integralizacao_satisfeita :- 
    not existe_falta.

existe_falta :- 
    falta(_, _).

%! aptidao | Art. 160, caput e § 2º | Define a aptidão para colar grau
% O estudante está apto se a integralização estiver satisfeita.
% A regularidade documental (§ 2º) é pressuposta como verdadeira na ausência de fatos contrários,
% mas como não há predicado de entrada para irregularidade, a condição de integralização é a determinante.
apto_colar_grau :- 
    integralizacao_satisfeita.