%! art146 | Art. 146 | definição do trancamento (informativa, não gera regras)

%! art147_1 | Art. 147, caput | pode solicitar trancamento regular (até 2 semestres)
%! art147_2 | Art. 147, §1 | total de trancamento regular no curso ≤ 2 semestres (1 ano)
%! art147_3 | Art. 147, §2 | trancamento deve respeitar semestre inteiro (não fracionado)

%! art148_i | Art. 148, I | vedado se estiver no primeiro ano do curso
first_year :-
    ingresso(P0),
    periodo_atual(P),
    Diff = P - P0,
    Diff < 2.

%! art148_ii | Art. 148, II | vedado se foi transferido no mesmo ano corrente
transferido_ano_atual :-
    transferido_no_ano(A),
    ano_atual(A).

%! art148_iii | Art. 148, III | vedado se está respondendo a processo disciplinar
% (processo_disciplinar já é um fato; sua presença impede o trancamento)

%! total_regular | total de períodos já trancados regular
total_regular_trancado(S) :- S = #count { P : trancamento(P, regular) }.

%! pode_trancar | regra principal que determina se o estudante pode pedir trancamento regular agora
pode_trancar :-
    not first_year,
    not processo_disciplinar,
    not transferido_ano_atual,
    total_regular_trancado(S),
    S < 2.