%! 146 | Art. 146 | Definition of trancamento: suspension not counted for curricular integration.
% (No explicit rule needed for pode_trancar)

%! 147 | Art. 147 | Regular trancamento up to 2 semesters, total <= 1 year.
total_regular_trancamento(N) :- N = #count{P : trancamento(P, regular)}.

%! 148 | Art. 148 | Prohibited trancamento for first year, transferred same year, disciplinary process.
first_year :- ano_ingresso(A), periodo_atual(P), Y = P / 2, Y = A.
transferred_same_year :- transferido_no_ano(A), ano_ingresso(A), periodo_atual(P), Y = P / 2, Y = A.

%! 149 | Art. 149 | Special trancamento: not counted for future regular trancamento or curricular integration.
% (No explicit rule needed for pode_trancar)

%! 150 | Art. 150 | Administrative trancamento: not counted for curricular integration.
% (No explicit rule needed for pode_trancar)

%! pode_trancar | Determine if student can request regular trancamento now
pode_trancar :-
    not first_year,
    not transferred_same_year,
    not processo_disciplinar,
    total_regular_trancamento(N),
    N < 2.