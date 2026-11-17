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

%! info_especial | Art. 149 | O trancamento especial é via Pró-reitoria e não conta para o limite regular.
% (O predicado pode_trancar refere-se ao pedido regular conforme solicitado na saída).

%! info_adm | Art. 150 | O trancamento administrativo é efetuado pela Pró-reitoria e não computa para integralização.
% (O predicado pode_trancar refere-se ao pedido regular conforme solicitado na saída).