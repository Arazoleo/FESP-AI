%! art109 | Art. 109 | Frequência mínima de 75% ou superior definido no PPC
% Se existir frequência mínima no PPC e for maior que 75%
freq_minima(C, F) :- freq_minima_ppc(C, F), F > 75.
% Se existir frequência mínima no PPC e for 75% ou menos
freq_minima(C, 75) :- freq_minima_ppc(C, F), F <= 75.
% Se não houver frequência mínima no PPC, a mínima é 75%
freq_minima(C, 75) :- not freq_minima_ppc(C, _), matricula(C, _).

%! art120 | Art. 120 | Reprovação por falta de frequência mínima
reprovado_frequencia(C, P) :-
    freq(C, P, F),
    freq_minima(C, Fmin),
    F < Fmin.

%! art122 | Art. 122 | Reprovação ou exame por nota
% Reprovado sem exame (nota < 30)
reprovado_sem_exame(C, P) :-
    nota10(C, P, N),
    N < 30,
    not reprovado_frequencia(C, P).

% Deve fazer exame (30 <= nota <= 59)
deve_fazer_exame(C, P) :-
    nota10(C, P, N),
    N >= 30,
    N <= 59,
    not reprovado_frequencia(C, P).

% Aprovado (nota >= 60)
aprovado(C, P) :-
    nota10(C, P, N),
    N >= 60,
    not reprovado_frequencia(C, P).

% Reprovado por nota (nota < 30) mas com frequência mínima
reprovado_nota(C, P) :-
    nota10(C, P, N),
    N < 30,
    not reprovado_frequencia(C, P).

%! art123 | Art. 123 | Aprovação após exame
nota_final(C, P, NF) :-
    media10(C, P, M),
    exame10(C, P, E),
    NF = (M + E) / 2.

% Aprovado após exame
aprovado(C, P) :-
    nota_final(C, P, NF),
    NF >= 60,
    not reprovado_frequencia(C, P).

% Reprovado por nota após exame (nota final < 30)
reprovado_nota(C, P) :-
    nota_final(C, P, NF),
    NF < 30,
    not reprovado_frequencia(C, P).

%! art123 | Art. 123 | UC sem nota mas situação cumprido => aprovado
aprovado(C, P) :-
    situacao(C, P, cumprido),
    not nota10(C, P, _),
    not reprovado_frequencia(C, P).