%! tranc_reg | Art. 147 | O estudante pode pedir trancamento regular se respeitar prazos e limites.
% Nota: O "prazo do calendário" é assumido como satisfeito se o pedido é processado agora.
pode_trancar :- 
    not vedado_trancamento_regular,
    not limite_trancamento_atingido.

%! ved_1 | Art. 148, I | Vedado trancamento no primeiro ano do curso.
vedado_trancamento_regular :- 
    ano_ingresso(A), 
    ano_atual(AA), 
    AA = A.

%! ved_2 | Art. 148, II | Vedado trancamento no mesmo ano da transferência.
vedado_trancamento_regular :- 
    transferido_no_ano(A), 
    ano_atual(A).

%! ved_3 | Art. 148, III | Vedado trancamento se responder a processo disciplinar.
vedado_trancamento_regular :- 
    processo_disciplinar.

%! lim_sem | Art. 147 | Trancamento regular limitado a dois semestres letivos.
% Conta quantos períodos de trancamento 'regular' já existem.
total_semestres_trancados(N) :- 
    N = #count { P : trancamento(P, regular) }.

limite_trancamento_atingido :- 
    total_semestres_trancados(N), 
    N >= 2.

%! lim_ano | Art. 147, § 1º | O período total de trancamento não pode exceder 1 ano.
% No contexto acadêmico de semestres, 1 ano = 2 semestres.
% A regra acima já cobre a limitação de 2 semestres, mas formaliza-se a soma.
limite_trancamento_atingido :- 
    total_semestres_trancados(N), 
    N >= 2.

%! info_especial | Art. 149 | Trancamento especial é via Pró-reitoria e não conta para o regular.
% O predicado 'trancamento(P, especial)' é entrada, mas a norma diz que ele não 
% é considerado para fins de solicitação posterior de trancamento regular.
% Portanto, ele não é contado no 'total_semestres_trancados' acima.

%! info_adm | Art. 150 | Trancamento administrativo é efetuado pela Pró-reitoria.
% O parágrafo único deixa claro que ele não computa para o limite do trancamento regular.
% Portanto, 'trancamento(P, administrativo)' também não é contado no 'total_semestres_trancados'.