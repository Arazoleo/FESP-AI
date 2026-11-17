%! f1 | Art. 109 | frequência mínima padrão 75% ou a fixa no PPC, se superior
freq_min_req(C,75) :- not freq_minima_ppc(C,_).
freq_min_req(C,F) :- freq_minima_ppc(C,F), F > 75.
freq_min_req(C,75) :- freq_minima_ppc(C,F), F =< 75.

%! f2 | Art. 109 | verifica se a frequência do estudante atende ao mínimo
freq_ok(C,P) :- freq(C,P,F), freq_min_req(C,Req), F >= Req.

%! f3 | Art. 109 | estudante reprovado por frequência quando não cumpre o mínimo
reprovado_frequencia(C,P) :- matricula(C,P), not freq_ok(C,P).

%! f4 | Aux | UC utiliza nota quando há nota final ou média pré‑exame
usa_nota(C) :- nota10(C,_,_).
usa_nota(C) :- media10(C,_,_).

%! f5 | Art. 120 | UCs sem nota, mas com situação cumprido, são aprovadas
aprovado(C,P) :- matricula(C,P), freq_ok(C,P),
                 situacao(C,P,cumprido), not usa_nota(C).

%! f6 | Art. 120 | nota final já registrada (já inclui exame, se houver)
nota_final(C,P,N) :- nota10(C,P,N).

%! f7 | Art. 123 | cálculo da nota final quando há média e exame (escala ×10)
nota_final(C,P,Nf) :- media10(C,P,M), exame10(C,P,E), Nf = (M + E) / 2.

%! f8 | Art. 122 I | nota final < 3,0 (30) → reprovado sem direito a exame
reprovado_sem_exame(C,P) :- matricula(C,P), freq_ok(C,P),
                           nota_final(C,P,N), N < 30.

%! f9 | Art. 122 II | nota final entre 3,0 e 5,9 (30‑59) → reprovado por nota (exame já realizado)
reprovado_nota(C,P) :- matricula(C,P), freq_ok(C,P),
                       nota_final(C,P,N), N >= 30, N < 60.

%! f10 | Art. 122 III | nota final ≥ 6,0 (60) → aprovado
aprovado(C,P) :- matricula(C,P), freq_ok(C,P),
                 nota_final(C,P,N), N >= 60.

%! f11 | Art. 122 II (pré‑exame) | média entre 3,0 e 5,9 → deve fazer exame
deve_fazer_exame(C,P) :- matricula(C,P), freq_ok(C,P),
                         media10(C,P,M), M >= 30, M < 60,
                         not exame10(C,P,_), not nota10(C,P,_).

%! f12 | Art. 122 I (pré‑exame) | média < 3,0 → reprovado sem exame
reprovado_sem_exame(C,P) :- matricula(C,P), freq_ok(C,P),
                           media10(C,P,M), M < 30,
                           not exame10(C,P,_), not nota10(C,P,_).

%! f13 | Art. 122 III (pré‑exame) | média ≥ 6,0 → aprovado sem necessidade de exame
aprovado(C,P) :- matricula(C,P), freq_ok(C,P),
                 media10(C,P,M), M >= 60,
                 not exame10(C,P,_), not nota10(C,P,_).