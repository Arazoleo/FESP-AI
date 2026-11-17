%! art109 | Art. 109 | Frequência mínima
% Frequência mínima padrão 75% se não houver valor no PPC
freq_minima(C,75) :- matricula(C,_), not freq_minima_ppc(C,_).
% Se houver valor no PPC e for maior que 75%, usa esse valor
freq_minima(C,Fmin) :- freq_minima_ppc(C,F), F > 75, Fmin = F.
% Se houver valor no PPC e for 75% ou menos, usa 75%
freq_minima(C,75) :- freq_minima_ppc(C,F), F <= 75.

%! art120 | Art. 120 | Reprovado por frequência
reprovado_frequencia(C,P) :-
    freq(C,P,F),
    freq_minima(C,Fmin),
    F < Fmin.

%! art122 | Art. 122 | Reprovado sem exame, deve fazer exame, aprovado
% Nota final já registrada (nota10)
final_note(C,P,Nf) :- nota10(C,P,Nf).
% Nota final calculada a partir de média e exame
final_note(C,P,Nf) :-
    media10(C,P,M),
    exame10(C,P,E),
    Nf = (M + E + 1) / 2.

% Reprovado sem exame: nota final < 30, sem exame, frequência ok
reprovado_sem_exame(C,P) :-
    final_note(C,P,Nf),
    Nf < 30,
    not exame10(C,P,_),
    freq(C,P,F),
    freq_minima(C,Fmin),
    F >= Fmin,
    not reprovado_frequencia(C,P).

% Deve fazer exame: 30 <= nota final <= 59, sem exame, frequência ok
deve_fazer_exame(C,P) :-
    final_note(C,P,Nf),
    Nf >= 30,
    Nf <= 59,
    not exame10(C,P,_),
    freq(C,P,F),
    freq_minima(C,Fmin),
    F >= Fmin,
    not reprovado_frequencia(C,P).

% Reprovado por nota: nota final < 60, frequência ok, não reprovado sem exame
reprovado_nota(C,P) :-
    final_note(C,P,Nf),
    Nf < 60,
    freq(C,P,F),
    freq_minima(C,Fmin),
    F >= Fmin,
    not reprovado_frequencia(C,P),
    not reprovado_sem_exame(C,P).

% Aprovado: nota final >= 60, frequência ok
aprovado(C,P) :-
    final_note(C,P,Nf),
    Nf >= 60,
    freq(C,P,F),
    freq_minima(C,Fmin),
    F >= Fmin,
    not reprovado_frequencia(C,P).

% Aprovado por situação "cumprido" sem nota (UC sem nota com situação cumprido conta como aprovada)
aprovado(C,P) :-
    situacao(C,P,cumprido),
    not nota10(C,P,_),
    freq(C,P,F),
    freq_minima(C,Fmin),
    F >= Fmin,
    not reprovado_frequencia(C,P).