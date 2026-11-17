%! tranc_reg | Art. 147 | O estudante pode pedir trancamento regular por até 2 semestres, respeitando o prazo.
% Nota: O "prazo do calendário" é assumido como satisfeito se o pedido é processado agora.
pode_trancar :- 
    not vedado_trancamento_regular,
    not limite_trancamento_atingido.

%! tranc_ved | Art. 148 | Vedações ao trancamento regular.
% I - Matriculado no primeiro ano do curso
vedado_trancamento_regular :- 
    periodo_atual(P), 
    ingresso(P0), 
    P < P0 + 2.

% II - Transferido no mesmo ano em que obteve a transferência
vedado_trancamento_regular :- 
    ano_atual(A), 
    transferido_no_ano(A).

% III - Respondendo a processo disciplinar
vedado_trancamento_regular :- 
    processo_disciplinar.

%! tranc_lim | Art. 147, § 1º | O período total de trancamento regular não pode exceder 1 ano (2 semestres).
limite_trancamento_atingido :- 
    #count { P : trancamento(P, regular) } >= 2.

%! tranc_esp | Art. 149 | Trancamento especial por doença grave ou excepcionalidade.
% O trancamento especial é um ato administrativo da Pró-Reitoria, não depende de 'pode_trancar' (regular).
% Definido como fato de entrada 'trancamento(P, especial)'.

%! tranc_adm | Art. 150 | Trancamento administrativo por falta de oferta ou ENADE irregular.
% O trancamento administrativo é efetuado pela Pró-Reitoria.
% Definido como fato de entrada 'trancamento(P, administrativo)'.

%! integral | Art. 146, 149 § 4º, 150 Parágrafo único | Trancamentos não contam para integralização.
% Esta regra é informativa para o cálculo de integralização (não solicitado como saída, mas formalizada logicamente).
nao_conta_integralizacao(P) :- trancamento(P, regular).
nao_conta_integralizacao(P) :- trancamento(P, especial).
nao_conta_integralizacao(P) :- trancamento(P, administrativo).