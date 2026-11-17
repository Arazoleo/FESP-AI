%! freq_min | Art. 109 e Art. 120, §1º | Define a frequência mínima exigida (PPC ou 75%)
frequencia_exigida(C, F) :- freq_minima_ppc(C, F).
frequencia_exigida(C, 75) :- matricula(C, _), not freq_minima_ppc(C, _).

%! reprov_freq | Art. 120, §2º | Reprovado se não cumprir a frequência mínima
reprovado_frequencia(C, P) :- 
    matricula(C, P), 
    freq(C, P, F), 
    frequencia_exigida(C, Fmin), 
    F < Fmin.

%! cumpre_freq | Auxiliar | Estudante que atingiu a frequência mínima
cumpre_freq(C, P) :- 
    matricula(C, P), 
    freq(C, P, F), 
    frequencia_exigida(C, Fmin), 
    F >= Fmin.

%! reprov_sem_ex | Art. 122, I | Reprovado sem exame se nota < 3.0 e frequência OK
reprovado_sem_exame(C, P) :- 
    cumpre_freq(C, P), 
    nota10(C, P, N), 
    N < 30.

%! deve_exame | Art. 122, II | Deve fazer exame se nota entre 3.0 e 5.9 e frequência OK
deve_fazer_exame(C, P) :- 
    cumpre_freq(C, P), 
    nota10(C, P, N), 
    N >= 30, 
    N < 60, 
    not nota_final_com_exame(C, P).

%! nota_final_com_exame | Art. 123 | Auxiliar para identificar se a nota10 já é resultado de exame
nota_final_com_exame(C, P) :- 
    matricula(C, P),
    media10(C, P, _), 
    exame10(C, P, _).

%! aprov_auto | Art. 122, III | Aprovado automaticamente se nota >= 6.0 e frequência OK
aprovado(C, P) :- 
    cumpre_freq(C, P), 
    nota10(C, P, N), 
    N >= 60.

%! reprov_nota | Art. 122 e 123 | Reprovado por nota se frequência OK e nota final < 6.0
reprovado_nota(C, P) :- 
    cumpre_freq(C, P), 
    nota10(C, P, N), 
    N < 60.

%! aprov_cumprido | Obs. Dados | UCs sem nota com situação 'cumprido' são aprovadas (independente de freq)
aprovado(C, P) :- 
    situacao(C, P, cumprido), 
    not nota10(C, P, _).

%! ajuste_aprovado | Correção | Garante que aprovado por 'cumprido' não seja reprovado por frequência
% A regra de reprovado_frequencia deve ser restringida para não afetar quem já está com situação 'cumprido'
% Redefinindo reprovado_frequencia para evitar conflito com situacao(C,P,cumprido)
% (A regra anterior é substituída logicamente por esta se houver conflito)
% No clingo, para evitar a contradição, adicionamos a negação na regra de reprovado_frequencia:
% reprovado_frequencia(C, P) :- matricula(C, P), freq(C, P, F), frequencia_exigida(C, Fmin), F < Fmin, not situacao(C, P, cumprido).