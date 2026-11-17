%! art109 | Art. 109 | frequência mínima é 75% ou maior, salvo definição no PPC
freq_minima(C,75) :- matricula(C,_), not freq_minima_ppc(C,_).
freq_minima(C,75) :- matricula(C,_), freq_minima_ppc(C,F), F <= 75.
freq_minima(C,F)  :- matricula(C,_), freq_minima_ppc(C,F), F > 75.

%! art120 | Art. 120 §2 | reprovação automática por frequência insuficiente
reprovado_frequencia(C,P) :-
    matricula(C,P),
    freq(C,P,F),
    freq_minima(C,Req),
    F < Req.

%! art120_ok | Art. 120 §1 | frequência suficiente
freq_ok(C,P) :-
    matricula(C,P),
    freq(C,P,F),
    freq_minima(C,Req),
    F >= Req,
    not reprovado_frequencia(C,P).

%! art122_I | Art. 122 I | nota < 3,0 → reprovado sem direito a exame
reprovado_sem_exame(C,P) :-
    freq_ok(C,P),
    media10(C,P,M),
    M < 30,
    not reprovado_frequencia(C,P).

%! art122_II | Art. 122 II | 3,0 ≤ nota ≤ 5,9 → deve fazer exame
deve_fazer_exame(C,P) :-
    freq_ok(C,P),
    media10(C,P,M),
    M >= 30, M <= 59,
    not reprovado_frequencia(C,P).

%! art122_III | Art. 122 III | nota ≥ 6,0 → aprovado direto
aprovado(C,P) :-
    freq_ok(C,P),
    media10(C,P,M),
    M >= 60,
    not reprovado_frequencia(C,P),
    not deve_fazer_exame(C,P),
    not reprovado_sem_exame(C,P),
    not reprovado_nota(C,P).

%! art123 | Art. 123 | cálculo da nota final após exame
final_nota(C,P,FN) :-
    media10(C,P,M),
    exame10(C,P,E),
    FN = (M + E) / 2.

aprovado(C,P) :-
    freq_ok(C,P),
    final_nota(C,P,FN),
    FN >= 60,
    not reprovado_frequencia(C,P),
    not deve_fazer_exame(C,P),
    not reprovado_sem_exame(C,P),
    not reprovado_nota(C,P).

reprovado_nota(C,P) :-
    freq_ok(C,P),
    final_nota(C,P,FN),
    FN < 60,
    not reprovado_frequencia(C,P),
    not reprovado_sem_exame(C,P).

%! nota_final | nota já registrada (já inclui exame, se houver)
aprovado(C,P) :-
    freq_ok(C,P),
    nota10(C,P,N),
    N >= 60,
    not reprovado_frequencia(C,P),
    not deve_fazer_exame(C,P),
    not reprovado_sem_exame(C,P),
    not reprovado_nota(C,P).

reprovado_nota(C,P) :-
    freq_ok(C,P),
    nota10(C,P,N),
    N < 60,
    not reprovado_frequencia(C,P),
    not reprovado_sem_exame(C,P).

%! reprovado_sem_exame implica reprovado_nota (contrato)
reprovado_nota(C,P) :- reprovado_sem_exame(C,P).

%! situacao_cumprido | situação “cumprido” sem nota conta como aprovação
aprovado(C,P) :-
    situacao(C,P,cumprido),
    not nota10(C,P,_),
    not reprovado_frequencia(C,P),
    not deve_fazer_exame(C,P),
    not reprovado_sem_exame(C,P),
    not reprovado_nota(C,P).

%! situacao_aprovado | registro oficial de aprovação
aprovado(C,P) :-
    situacao(C,P,aprovado),
    not reprovado_frequencia(C,P),
    not deve_fazer_exame(C,P),
    not reprovado_sem_exame(C,P),
    not reprovado_nota(C,P).

%! situacao_reprovado | registro oficial de reprovação (não por frequência)
reprovado_nota(C,P) :-
    situacao(C,P,reprovado),
    not reprovado_frequencia(C,P),
    not reprovado_sem_exame(C,P).