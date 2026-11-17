%! freq_min | Art. 109 e 120 | Define a frequência mínima exigida (PPC ou 75%)
frequencia_exigida(C, F) :- freq_minima_ppc(C, F).
frequencia_exigida(C, 75) :- matricula(C, P), not freq_minima_ppc(C, _).

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
    not aprovado_final(C, P).

% Auxiliar para evitar conflito entre nota final e média inicial
aprovado_final(C, P) :- nota10(C, P, N), N >= 60.

%! aprov_auto | Art. 122, III | Aprovado automaticamente se nota >= 6.0 e freq ok
aprovado(C, P) :- 
    frequencia_ok(C, P), 
    nota10(C, P, N), 
    N >= 60.

%! reprov_nota | Art. 123 | Reprovado por nota se após exame nota final < 6.0
reprovado_nota(C, P) :- 
    frequencia_ok(C, P), 
    nota10(C, P, N), 
    N < 60, 
    not reprovado_sem_exame(C, P).

%! aprov_cumprido | Obs. Dados | UCs sem nota com situação 'cumprido' são aprovadas
aprovado(C, P) :- 
    situacao(C, P, cumprido), 
    not nota10(C, P, _).

%! aprov_exame | Art. 123 | Aprovado se nota final (com exame) >= 6.0
% Nota: nota10 já é a nota final conforme observação de dados.
aprovado(C, P) :- 
    frequencia_ok(C, P), 
    nota10(C, P, N), 
    N >= 60.