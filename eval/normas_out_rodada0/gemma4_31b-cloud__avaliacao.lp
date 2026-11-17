%! freq_min | Art. 109 e Art. 120, §1º | Define a frequência mínima exigida (PPC ou 75%)
frequencia_exigida(C, F) :- freq_minima_ppc(C, F).
frequencia_exigida(C, 75) :- matricula(C, P), not freq_minima_ppc(C, _).

%! reprov_freq | Art. 120, §2º | Reprovado se não cumprir a frequência mínima
reprovado_frequencia(C, P) :- 
    matricula(C, P), 
    freq(C, P, F), 
    frequencia_exigida(C, Fmin), 
    F < Fmin.

%! freq_ok | Auxiliar | Estudante cumpriu a frequência mínima
cumpre_frequencia(C, P) :- 
    matricula(C, P), 
    freq(C, P, F), 
    frequencia_exigida(C, Fmin), 
    F >= Fmin.

%! reprov_sem_ex | Art. 122, I | Reprovado sem exame se nota < 3.0 e freq ok
reprovado_sem_exame(C, P) :- 
    cumpre_frequencia(C, P), 
    nota10(C, P, N), 
    N < 30.

%! deve_exame | Art. 122, II | Deve fazer exame se nota entre 3.0 e 5.9 e freq ok
deve_fazer_exame(C, P) :- 
    cumpre_frequencia(C, P), 
    nota10(C, P, N), 
    N >= 30, 
    N < 60, 
    not aprovado_final_exame(C, P).

%! aprov_auto | Art. 122, III | Aprovado automaticamente se nota >= 6.0 e freq ok
aprovado(C, P) :- 
    cumpre_frequencia(C, P), 
    nota10(C, P, N), 
    N >= 60.

%! aprov_exame | Art. 123 | Aprovado via exame se (media + exame)/2 >= 6.0
% Nota final registrada no histórico (nota10) já reflete o cálculo do Art. 123
aprovado_final_exame(C, P) :- 
    cumpre_frequencia(C, P), 
    nota10(C, P, N), 
    N >= 60, 
    deve_fazer_exame_hipotetico(C, P).

% Auxiliar para identificar que houve exame (média original era < 60)
deve_fazer_exame_hipotetico(C, P) :- 
    media10(C, P, M), 
    M >= 30, 
    M < 60.

aprovado(C, P) :- aprovado_final_exame(C, P).

%! reprov_nota | Art. 122 e 123 | Reprovado por nota mesmo com frequência mínima
reprovado_nota(C, P) :- 
    cumpre_frequencia(C, P), 
    nota10(C, P, N), 
    N < 60, 
    not reprovado_sem_exame(C, P).

%! aprov_cumprido | Obs. Dados | UCs sem nota com situação 'cumprido' são aprovadas
aprovado(C, P) :- 
    situacao(C, P, cumprido), 
    not nota10(C, P, _).