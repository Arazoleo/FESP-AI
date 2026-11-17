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

%! lim_sem | Art. 147 | Trancamento regular limitado a dois semestres letivos.
limite_trancamento_atingido :- 
    #count { P : trancamento(P, regular) } >= 2.

%! lim_ano | Art. 147, § 1º | O período total de trancamento regular não pode exceder 1 ano (2 semestres).
% Nota: Como o §2º veda o fracionamento, 2 semestres = 1 ano.
limite_trancamento_atingido :- 
    #count { P : trancamento(P, regular) } >= 2.

%! tranc_esp | Art. 149 | Trancamento especial por doença grave/excepcionalidade (não computado para regular).
% O trancamento especial é um fato de entrada 'trancamento(P, especial)', 
% mas a norma deixa claro que ele não impede nem conta para o trancamento regular.
% Portanto, não adicionamos 'trancamento(P, especial)' ao cálculo de 'limite_trancamento_atingido'.

%! tranc_adm | Art. 150 | Trancamento administrativo por falta de oferta ou ENADE (não computado para regular).
% O trancamento administrativo é um fato de entrada 'trancamento(P, administrativo)',
% e o Parágrafo Único explicitamente diz que ele não é computado para o direito de trancamento regular.
% Portanto, não adicionamos 'trancamento(P, administrativo)' ao cálculo de 'limite_trancamento_atingido'.