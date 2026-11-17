%! 109 | Art. 109 | Frequência mínima de 75% ou superior definido no PPC
% Define a frequência mínima para cada UC: valor do PPC se existir, senão 75
min_freq(C,Fmin) :- freq_minima_ppc(C,Fmin).

% Garante que todas as UC que aparecem em matricula ou em freq_minima_ppc
% tenham um predicado de domínio
all_uc(C) :- freq_minima_ppc(C,_).
all_uc(C) :- matricula(C,_).

% Se não houver frequência mínima definida no PPC, usa 75%
min_freq(C,75) :- all_uc(C), not freq_minima_ppc(C,_).

% Reprovado por frequência: frequência menor que o mínimo exigido
reprovado_frequencia(C,P) :-
    freq(C,P,F),
    min_freq(C,Fmin),
    F < Fmin.

%! 122 | Art. 122 | Critérios de aprovação por nota
% Reprovado sem direito a exame: nota < 3.0 (30) e frequência mínima cumprida
reprovado_sem_exame(C,P) :-
    nota10(C,P,N),
    N < 30,
    not reprovado_frequencia(C,P).

% Deve fazer exame: nota entre 3.0 (30) e 5.9 (59) e frequência mínima cumprida
deve_fazer_exame(C,P) :-
    nota10(C,P,N),
    N >= 30,
    N <= 59,
    not reprovado_frequencia(C,P).

% Aprovado por nota: nota >= 6.0 (60) e frequência mínima cumprida
aprovado(C,P) :-
    nota10(C,P,N),
    N >= 60,
    not reprovado_frequencia(C,P).

% Aprovado quando não há nota, mas a situação oficial indica "cumprido"
% e a frequência mínima foi cumprida
aprovado(C,P) :-
    situacao(C,P,cumprido),
    not reprovado_frequencia(C,P),
    not nota10(C,P,_).

% Reprovado por nota (com frequência mínima cumprida)
reprovado_nota(C,P) :-
    nota10(C,P,N),
    N < 30,
    not reprovado_frequencia(C,P).