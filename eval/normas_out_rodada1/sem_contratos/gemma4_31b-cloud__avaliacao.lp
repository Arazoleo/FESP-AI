%! freq_min | Art. 109 e 120 | Define a frequência mínima exigida (PPC ou 75%)
frequencia_exigida(C, F) :- freq_minima_ppc(C, F).
frequencia_exigida(C, 75) :- matricula(C, _), not freq_minima_ppc(C, _).

%! reprov_freq | Art. 120, § 2º | Reprovado se não cumprir a frequência mínima
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

%! reprov_sem_ex | Art. 122, I | Reprovado sem exame se nota < 3.0 e freq ok
reprovado_sem_exame(C, P) :- 
    frequencia_ok(C, P), 
    nota10(C, P, N), 
    N < 30.

%! deve_exame | Art. 122, II | Deve fazer exame se nota entre 3.0 e 5.9 e freq ok
deve_fazer_exame(C, P) :- 
    frequencia_ok(C, P), 
    nota10(C, P, N), 
    N >= 30, 
    N < 60, 
    not aprovado_final_exame(C, P).

%! aprov_final_exame | Art. 123 | Cálculo da nota final após exame (M+E)/2 >= 6.0
aprovado_final_exame(C, P) :- 
    frequencia_ok(C, P), 
    media10(C, P, M), 
    exame10(C, P, E), 
    (M + E) / 2 >= 60.

%! aprov_auto | Art. 122, III | Aprovado automaticamente se nota >= 6.0 e freq ok
aprovado_automatico(C, P) :- 
    frequencia_ok(C, P), 
    nota10(C, P, N), 
    N >= 60.

%! aprovado | Art. 120, 122, 123 | Aprovado por nota, exame ou situação "cumprido"
aprovado(C, P) :- aprovado_automatico(C, P).
aprovado(C, P) :- aprovado_final_exame(C, P).
aprovado(C, P) :- situacao(C, P, cumprido).

%! reprov_nota | Art. 122, 123 | Reprovado por nota (com freq ok) se não aprovado
reprovado_nota(C, P) :- 
    frequencia_ok(C, P), 
    nota10(C, P, _), 
    not aprovado(C, P).