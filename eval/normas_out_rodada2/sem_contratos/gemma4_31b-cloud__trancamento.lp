%! tranc_reg | Art. 147 | O estudante pode pedir trancamento regular se não houver vedações e respeitar limites.
pode_trancar :- 
    not vedado_trancamento_regular,
    not limite_trancamento_atingido.

%! ved_1 | Art. 148, I | Vedado trancamento no primeiro ano do curso.
vedado_trancamento_regular :- 
    periodo_atual(P), 
    ingresso(P0), 
    P < P0 + 2.

%! ved_2 | Art. 148, II | Vedado trancamento no mesmo ano em que obteve a transferência.
vedado_trancamento_regular :- 
    ano_atual(A), 
    transferido_no_ano(A).

%! ved_3 | Art. 148, III | Vedado trancamento se estiver respondendo a processo disciplinar.
vedado_trancamento_regular :- 
    processo_disciplinar.

%! lim_1 | Art. 147, § 1º | O período total de trancamento regular não pode exceder 1 ano (2 semestres).
limite_trancamento_atingido :- 
    #count { P : trancamento(P, regular) } >= 2.

%! info_tranc | Art. 146, 149 § 4º, 150 Parágrafo único | Definição de que trancamentos não contam para integralização.
% (Nota: A lógica de integralização curricular não foi solicitada como predicado de saída, 
% mas a norma estabelece que trancamento(P, regular), trancamento(P, especial) 
% e trancamento(P, administrativo) não computam tempo de integralização).