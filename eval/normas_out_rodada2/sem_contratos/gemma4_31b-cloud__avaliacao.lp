%! freq_min | Art. 109 e 120 | Define a frequência mínima exigida para a UC
frequencia_exigida(C, F) :- freq_minima_ppc(C, F).
frequencia_exigida(C, 75) :- matricula(C, P), not freq_minima_ppc(C, _).

%! reprov_freq | Art. 120, § 2º | Reprovado por não cumprir a frequência mínima
reprovado_frequencia(C, P) :- 
    matricula(C, P), 
    freq(C, P, F), 
    frequencia_exigida(C, Fmin), 
    F < Fmin.

%! freq_ok | Auxiliar | Estudante cumpriu a frequência mínima
frequencia_ok(C, P) :- 
    matricula(C, P), 
    freq(C, P, F), 
    frequencia_exigida(C, Fmin), 
    F >= Fmin.

%! reprov_sem_ex | Art. 122, I | Reprovado sem exame por nota < 3.0
reprovado_sem_exame(C, P) :- 
    frequencia_ok(C, P), 
    nota10(C, P, N), 
    N < 30.

%! deve_exame | Art. 122, II | Deve fazer exame se nota entre 3.0 e 5.9
deve_fazer_exame(C, P) :- 
    frequencia_ok(C, P), 
    nota10(C, P, N), 
    N >= 30, 
    N < 60, 
    not aprovado_final_exame(C, P).

%! aux_exame_aprov | Art. 123 | Verifica se a nota final após exame é >= 6.0
aprovado_final_exame(C, P) :- 
    frequencia_ok(C, P), 
    media10(C, P, M), 
    exame10(C, P, E), 
    (M + E) / 2 >= 60.

%! reprov_nota | Art. 122 e 123 | Reprovado por nota (com freq ok)
reprovado_nota(C, P) :- 
    frequencia_ok(C, P), 
    nota10(C, P, N), 
    N < 30.
reprovado_nota(C, P) :- 
    frequencia_ok(C, P), 
    deve_fazer_exame(C, P), 
    not aprovado_final_exame(C, P).

%! aprovado | Art. 122, III e 123 | Aprovado por nota >= 6.0 ou via exame
aprovado(C, P) :- 
    frequencia_ok(C, P), 
    nota10(C, P, N), 
    N >= 60.
aprovado(C, P) :- 
    frequencia_ok(C, P), 
    aprovado_final_exame(C, P).
aprovado(C, P) :- 
    situacao(C, P, cumprido).