%! freq_min_req | Art. 109 | frequência mínima (75 % ou valor definido no PPC)
freq_min_req(C,Req) :- freq_minima_ppc(C,Req).
freq_min_req(C,75)    :- not freq_minima_ppc(C,_).

%! freq_ok | Art. 109 | frequência suficiente para avaliação
freq_ok(C,P) :- matricula(C,P), freq(C,P,F), freq_min_req(C,Req), F >= Req.

%! reprovado_frequencia | Art. 120 §2 | reprovação por frequência insuficiente
reprovado_frequencia(C,P) :-
    matricula(C,P),
    freq(C,P,F),
    freq_min_req(C,Req),
    F < Req.

%! nota_final | Art. 123 | cálculo da nota final (já com exame, se houver)
nota_final(C,P,NF) :- nota10(C,P,NF).                                            % nota já registrada
nota_final(C,P,NF) :- not nota10(C,P,_), media10(C,P,M), not exame10(C,P,_), NF = M.
nota_final(C,P,NF) :- not nota10(C,P,_), media10(C,P,M), exame10(C,P,E), NF = (M + E) / 2.

%! reprovado_sem_exame | Art. 122 I | nota < 3,0 sem direito a exame
reprovado_sem_exame(C,P) :-
    freq_ok(C,P),
    nota_final(C,P,NF),
    NF < 30,
    not reprovado_frequencia(C,P).

%! deve_fazer_exame | Art. 122 II | nota entre 3,0 e 5,9, ainda sem exame
deve_fazer_exame(C,P) :-
    freq_ok(C,P),
    media10(C,P,M),
    M >= 30, M <= 59,
    not exame10(C,P,_),
    not reprovado_frequencia(C,P),
    not reprovado_sem_exame(C,P).

%! reprovado_nota | Art. 122 I (após exame) | nota final entre 3,0 e 5,9
reprovado_nota(C,P) :-
    freq_ok(C,P),
    nota_final(C,P,NF),
    NF >= 30, NF < 60,
    not reprovado_frequencia(C,P),
    not reprovado_sem_exame(C,P),
    not deve_fazer_exame(C,P).

%! aprovado | Art. 122 III + Art. 123 | aprovação automática ou por nota final ≥ 6,0
aprovado(C,P) :-
    freq_ok(C,P),
    nota_final(C,P,NF),
    NF >= 60,
    not reprovado_frequencia(C,P),
    not reprovado_sem_exame(C,P),
    not deve_fazer_exame(C,P),
    not reprovado_nota(C,P).

%! aprovado | Situacao cumprido | histórico indica cumprimento sem nota
aprovado(C,P) :-
    freq_ok(C,P),
    situacao(C,P,cumprido),
    not reprovado_frequencia(C,P),
    not reprovado_sem_exame(C,P),
    not deve_fazer_exame(C,P),
    not reprovado_nota(C,P).

%! aprovado | Situacao aprovado | registro oficial de aprovação
aprovado(C,P) :-
    freq_ok(C,P),
    situacao(C,P,aprovado),
    not reprovado_frequencia(C,P),
    not reprovado_sem_exame(C,P),
    not deve_fazer_exame(C,P),
    not reprovado_nota(C,P).