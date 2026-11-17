%! art147 | Art. 147 | pode solicitar trancamento regular (até 2 semestres, total ≤ 1 ano)
% total de períodos de trancamento regular já realizados
total_regular(N) :- N = #count { P : trancamento(P, regular) }.

%! art148_i | Art. 148 I | vedado se estiver no primeiro ano do curso
primeiro_ano :-
    ingresso(P0),
    periodo_atual(Pa),
    Ano0 = P0 / 2,
    AnoA = Pa / 2,
    Ano0 = AnoA.

%! art148_ii | Art. 148 II | vedado se foi transferido no mesmo ano corrente
transferido_mesmo_ano :-
    transferido_no_ano(A),
    ano_atual(A).

%! art148_iii | Art. 148 III | vedado se estiver respondendo a processo disciplinar
em_processo_disciplinar :- processo_disciplinar.

%! art148 | Art. 148 | conjunto de vedações ao trancamento regular
vedado_art148 :- primeiro_ano.
vedado_art148 :- transferido_mesmo_ano.
vedado_art148 :- em_processo_disciplinar.

%! regra_eligibilidade | Regra que determina se o estudante pode pedir trancamento regular agora
pode_trancar :-
    total_regular(N), N < 2,          % ainda não ultrapassou o limite de 2 semestres acumulados
    not vedado_art148.                % nenhuma das vedações do art. 148 se aplica