%! uc | domínio | define conjunto de unidades curriculares conhecidas
uc(C) :- matricula(C,_).
uc(C) :- carga(C,_).

%! freq_min | Art. 109 | frequência mínima aplicável (75% ou superior fixada no PPC)
freq_min(C,Min) :- freq_minima_ppc(C,F), Min = F.
freq_min(C,75)   :- uc(C), not freq_minima_ppc(C,_).

%! reprov_frequencia | Art. 109 | estudante reprovado por frequência insuficiente
reprovado_frequencia(C,P) :-
    matricula(C,P),
    freq(C,P,F),
    freq_min(C,Min),
    F < Min.

%! elegivel | Art. 120 §2 | estudante elegível para avaliação de nota (frequência cumprida)
elegivel(C,P) :- matricula(C,P), not reprovado_frequencia(C,P).

%! final_nota | Art. 122/123 | cálculo da nota final já considerada (com exame)
final_nota(C,P,N) :- nota10(C,P,N), elegivel(C,P).

%! final_nota_exame | Art. 123 | cálculo da nota final a partir de média e exame
final_nota(C,P,N) :-
    media10(C,P,M),
    exame10(C,P,E),
    elegivel(C,P),
    N = (M + E) / 2.

%! media_provisoria | Art. 122 | média antes de eventual exame
media_provisoria(C,P,M) :-
    media10(C,P,M),
    not exame10(C,P,_),
    elegivel(C,P).

%! reprov_sem_exame | Art. 122 I | nota < 3,0 (30) sem direito a exame
reprovado_sem_exame(C,P) :-
    media_provisoria(C,P,M),
    M < 30.

%! deve_fazer_exame | Art. 122 II | nota entre 3,0 e 5,9 (30‑59) requer exame
deve_fazer_exame(C,P) :-
    media_provisoria(C,P,M),
    M >= 30, M <= 59.

%! aprovado_media | Art. 122 III | nota >= 6,0 (60) sem necessidade de exame
aprovado(C,P) :-
    media_provisoria(C,P,M),
    M >= 60.

%! aprovado_nota | Art. 122 III | nota final (com exame) >= 6,0 (60)
aprovado(C,P) :-
    final_nota(C,P,N),
    N >= 60.

%! reprov_nota | Art. 122 | nota final (com exame) < 6,0 (60)
reprovado_nota(C,P) :-
    final_nota(C,P,N),
    N < 60,
    not reprovado_frequencia(C,P).

%! aprovado_situacao | Art. 120 | situação “cumprido” ou “aprovado” já registrada conta como aprovação
aprovado(C,P) :- situacao(C,P,cumprido), elegivel(C,P).
aprovado(C,P) :- situacao(C,P,aprovado), elegivel(C,P).