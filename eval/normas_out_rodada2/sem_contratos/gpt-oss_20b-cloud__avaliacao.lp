%! art109 | Art. 109 | Frequência mínima de 75% ou maior se definido no PPC
freq_minima(C,Fmin) :- freq_minima_ppc(C,Fmin).
freq_minima(C,75) :- freq(C,P,_), not freq_minima_ppc(C,_).

%! art120 | Art. 120 | Reprovado por frequência mínima
reprovado_frequencia(C,P) :- freq(C,P,F), freq_minima(C,Fmin), F < Fmin.

%! art122 | Art. 122 | Reprovado sem exame (nota < 3.0)
reprovado_sem_exame(C,P) :- freq(C,P,F), freq_minima(C,Fmin), F >= Fmin,
                            nota10(C,P,N), N < 30.

%! art122 | Art. 122 | Deve fazer exame (nota entre 3.0 e 5.9)
deve_fazer_exame(C,P) :- freq(C,P,F), freq_minima(C,Fmin), F >= Fmin,
                         nota10(C,P,N), N >= 30, N <= 59.

%! art122 | Art. 122 | Aprovado (nota >= 6.0)
aprovado(C,P) :- freq(C,P,F), freq_minima(C,Fmin), F >= Fmin,
                 nota10(C,P,N), N >= 60.

%! art122 | Art. 122 | Reprovado por nota (com frequência mínima)
reprovado_nota(C,P) :- freq(C,P,F), freq_minima(C,Fmin), F >= Fmin,
                       nota10(C,P,N), N < 30.

%! art123 | Art. 123 | UCs sem nota com situacao(cumprido) contam como aprovadas
aprovado(C,P) :- freq(C,P,F), freq_minima(C,Fmin), F >= Fmin,
                 situacao(C,P,cumprido), not nota10(C,P,_).