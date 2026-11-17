%! TRANCAMENTO_REGULAR | Art. 147 | Regular trancamento restrictions

% Current year of study
current_year(Y) :- ano_atual(Y).

% First year of the course
first_year :- current_year(1).

% Student transferred in the same year
transferred_same_year :- transferido_no_ano(Y), current_year(Y).

% Student in disciplinary process
disciplinary_process :- processo_disciplinar.

% Count of regular trancamento semesters already taken
total_regular_semesters(N) :- N = #count{P : trancamento(P, regular)}.

% The student can request a regular trancamento now
pode_trancar :-
    not first_year,
    not transferred_same_year,
    not disciplinary_process,
    total_regular_semesters(N),
    N < 2.