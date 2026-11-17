%! freq_minima | Art. 109 | frequência mínima = 75% ou valor maior definido no PPC
freq_minima(C,75) :- not freq_minima_ppc(C,_).
freq_minima(C,R) :- freq_minima_ppc(C,R), R > 75.

%! reprov_frequencia | Art. 109 | estudante reprovado por frequência insuficiente
reprovado_frequencia(C,P) :-
    matricula(C,P),
    freq(C,P,F),
    freq_minima(C,R),
    F < R.

%! freq_ok | Art. 109 | estudante que cumpre frequência mínima
freq_ok(C,P) :-
    matricula(C,P),
    freq(C,P,F),
    freq_minima(C,R),
    F >= R,
    not reprovado_frequencia(C,P).

%! apro_cumprido | Observação | situação cumprido sem nota ⇒ aprovado
aprovado(C,P) :-
    freq_ok(C,P),
    situacao(C,P,cumprido),
    not nota10(C,P,_),
    not media10(C,P,_).

%! apro_nota_reg | Art. 120 | nota final já registrada (já com exame, se houver)
aprovado(C,P) :-
    freq_ok(C,P),
    nota10(C,P,N),
    N >= 60,
    not reprovado_frequencia(C,P).

%! apro_media_alta | Art. 122, III | média ≥ 6,0 ⇒ aprovado direto (sem exame)
aprovado(C,P) :-
    freq_ok(C,P),
    media10(C,P,M),
    M >= 60,
    not exame10(C,P,_),
    not reprovado_frequencia(C,P).

%! final_nota | Art. 123 | cálculo da nota final quando há exame
final_nota(C,P,NF) :-
    media10(C,P,M),
    exame10(C,P,E),
    NF = (M + E) / 2.

%! apro_nota_exame | Art. 122, III (após exame) | nota final ≥ 6,0 ⇒ aprovado
aprovado(C,P) :-
    freq_ok(C,P),
    final_nota(C,P,NF),
    NF >= 60,
    not reprovado_frequencia(C,P).

%! deve_exame | Art. 122, II | 3,0 ≤ média ≤ 5,9 e ainda não fez exame
deve_fazer_exame(C,P) :-
    freq_ok(C,P),
    media10(C,P,M),
    M >= 30, M <= 59,
    not exame10(C,P,_),
    not reprovado_frequencia(C,P).

%! reprov_sem_exame | Art. 122, I | média < 3,0 ⇒ reprovado sem direito a exame
reprovado_sem_exame(C,P) :-
    freq_ok(C,P),
    media10(C,P,M),
    M < 30,
    not exame10(C,P,_),
    not reprovado_frequencia(C,P).

%! reprov_nota_exame | Art. 122, II + Art. 123 | fez exame, nota final < 6,0
reprovado_nota(C,P) :-
    freq_ok(C,P),
    final_nota(C,P,NF),
    NF < 60,
    not reprovado_frequencia(C,P).

%! reprov_nota_reg | Art. 120 | nota final registrada < 6,0 (já com exame, se houver)
reprovado_nota(C,P) :-
    freq_ok(C,P),
    nota10(C,P,N),
    N < 60,
    not reprovado_frequencia(C,P).

%! reprov_nota_media_exame | Art. 122, II | média entre 3,0 e 5,9, exame feito, nota final < 6,0
reprovado_nota(C,P) :-
    freq_ok(C,P),
    media10(C,P,M),
    M >= 30, M <= 59,
    exame10(C,P,_),
    final_nota(C,P,NF),
    NF < 60,
    not reprovado_frequencia(C,P).