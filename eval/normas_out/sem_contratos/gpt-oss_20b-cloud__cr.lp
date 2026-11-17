%! art132 | Art. 132 | CR acumulado ×1000
%! art133 | Art. 133 | CR calculado com nota final N e carga horária H
%! art135 | Art. 135 | notas consideradas e tratamento de reprovado por frequência
%! art136 | Art. 136 | exclusões do cálculo do CR

% Exclusion predicates
excluded(C,P) :- matricula(C,P), trancamento(P,_).
excluded(C,P) :- matricula(C,P), natureza(C,N), N = tcc.
excluded(C,P) :- matricula(C,P), natureza(C,N), N = estagio.
excluded(C,P) :- matricula(C,P), natureza(C,N), N = ac.
excluded(C,P) :- matricula(C,P), rer_vedado(C).

% UC considered for CR
considered(C,P) :- matricula(C,P), not excluded(C,P), nota10(C,P,_).
considered(C,P) :- matricula(C,P), not excluded(C,P), reprovado_frequencia(C,P).

% Note for each considered UC
note(C,P,N) :- nota10(C,P,N), not reprovado_frequencia(C,P).
note(C,P,0) :- reprovado_frequencia(C,P).

% Numerator: sum of N*H
numerator(N) :- N = #sum{Nuc*H : considered(C,P), note(C,P,Nuc), carga(C,H)}.

% Denominator: sum of H
denominator(D) :- D = #sum{H : considered(C,P), carga(C,H)}.

% CR acumulado ×1000
cr_x1000(CR) :- numerator(N), denominator(D), D > 0, CR = (N * 1000) / D.