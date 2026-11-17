%! art109 | Art. 109 | frequência mínima padrão 75% ou maior se fixada no PPC
freq_minima(C,75) :- not freq_minima_ppc(C,_).
freq_minima(C,F) :- freq_minima_ppc(C,F), F > 75.

%! art109_reprov | Art. 109 | reprovação por frequência insuficiente
reprovado_frequencia(C,P) :-
    matricula(C,P),
    freq(C,P,F),
    freq_minima(C,Min),
    F < Min.

%! art122_I | Art. 122 I | nota < 3,0 → reprovado sem direito a exame
reprovado_sem_exame(C,P) :-
    matricula(C,P),
    not reprovado_frequencia(C,P),
    media10(C,P,M),
    not exame10(C,P,_),
    not nota10(C,P,_),
    M < 30.

%! art122_II | Art. 122 II | nota entre 3,0 e 5,9 → deve fazer exame
deve_fazer_exame(C,P) :-
    matricula(C,P),
    not reprovado_frequencia(C,P),
    media10(C,P,M),
    not exame10(C,P,_),
    not nota10(C,P,_),
    M >= 30, M <= 59.

%! art122_III | Art. 122 III | nota >= 6,0 → aprovado automaticamente (sem exame)
aprovado(C,P) :-
    matricula(C,P),
    not reprovado_frequencia(C,P),
    media10(C,P,M),
    not exame10(C,P,_),
    not nota10(C,P,_),
    M >= 60.

%! art123_calc | Art. 123 | cálculo da nota final após exame
final_nota(C,P,Nf) :-
    matricula(C,P),
    not reprovado_frequencia(C,P),
    media10(C,P,M),
    exame10(C,P,E),
    Nf = (M + E) / 2.

%! art123_aprovado | Art. 123 | aprovação após exame se nota final >= 6,0
aprovado(C,P) :-
    final_nota(C,P,Nf),
    Nf >= 60.

%! art123_reprovado | Art. 123 | reprovação após exame se nota final < 6,0
reprovado_nota(C,P) :-
    final_nota(C,P,Nf),
    Nf < 60.

%! nota_final | nota final já registrada (pode já incluir exame)
aprovado(C,P) :-
    matricula(C,P),
    not reprovado_frequencia(C,P),
    nota10(C,P,N),
    N >= 60.

reprovado_nota(C,P) :-
    matricula(C,P),
    not reprovado_frequencia(C,P),
    nota10(C,P,N),
    N < 60.

%! situacao_cumprido | situação “cumprido” sem nota final → aprovado
aprovado(C,P) :-
    matricula(C,P),
    not reprovado_frequencia(C,P),
    situacao(C,P,cumprido),
    not nota10(C,P,_).