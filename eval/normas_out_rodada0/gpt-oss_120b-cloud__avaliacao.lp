%! art109 | frequência mínima | define a frequência mínima exigida (máx entre 75% e a fixa no PPC)
freq_minima(C,Req) :- freq_minima_ppc(C,F), F > 75, Req = F.
freq_minima(C,75)   :- not freq_minima_ppc(C,_).
freq_minima(C,75)   :- freq_minima_ppc(C,F), F =< 75.

%! art109 | reprovação por frequência | estudante reprovado se sua frequência está abaixo da mínima
reprovado_frequencia(C,P) :-
    matricula(C,P),
    freq(C,P,F),
    freq_minima(C,Req),
    F < Req.

%! aux | nota final já registrada | usa nota10 quando disponível
final_note(C,P,N) :- nota10(C,P,N).

%! aux | nota final calculada | combina média e exame quando ambos existirem
final_note(C,P,N) :-
    not nota10(C,P,_),
    media10(C,P,M),
    exame10(C,P,E),
    N = (M + E) / 2.

%! aux | indica presença de avaliação por nota
tem_nota(C,P) :- nota10(C,P,_).
tem_nota(C,P) :- media10(C,P,_).

%! art122 I | reprovado sem exame | nota (ou média) inferior a 3,0 (30)
reprovado_sem_exame(C,P) :-
    matricula(C,P),
    not reprovado_frequencia(C,P),
    media10(C,P,M),
    M < 30.
reprovado_sem_exame(C,P) :-
    matricula(C,P),
    not reprovado_frequencia(C,P),
    nota10(C,P,N),
    N < 30.

%! art122 II | deve fazer exame | nota entre 3,0 e 5,9 (30‑59) e ainda não há exame
deve_fazer_exame(C,P) :-
    matricula(C,P),
    not reprovado_frequencia(C,P),
    media10(C,P,M),
    M >= 30, M =< 59,
    not exame10(C,P,_).

%! art122 III | aprovado automaticamente | nota final ≥ 6,0 (60) ou situação cumprido sem nota
aprovado(C,P) :-
    matricula(C,P),
    not reprovado_frequencia(C,P),
    final_note(C,P,N),
    N >= 60.
aprovado(C,P) :-
    matricula(C,P),
    not reprovado_frequencia(C,P),
    media10(C,P,M),
    M >= 60.
aprovado(C,P) :-
    matricula(C,P),
    not reprovado_frequencia(C,P),
    situacao(C,P,cumprido),
    not tem_nota(C,P).

%! art120 §2 | reprovado por nota | frequência atendida, nota final entre 3,0 e 5,9 (30‑59)
reprovado_nota(C,P) :-
    matricula(C,P),
    not reprovado_frequencia(C,P),
    final_note(C,P,N),
    N >= 30, N < 60,
    not reprovado_sem_exame(C,P).

%! art120 §1 | respeita situação oficial já registrada
aprovado(C,P)          :- situacao(C,P,aprovado).
reprovado_frequencia(C,P) :- situacao(C,P,reprovado), freq(C,P,F), freq_minima(C,Req), F < Req.
reprovado_nota(C,P)   :- situacao(C,P,reprovado), not reprovado_frequencia(C,P), tem_nota(C,P), not aprovado(C,P).

%! coerência | impede múltiplas classificações simultâneas
:- reprovado_frequencia(C,P), aprovado(C,P).
:- reprovado_frequencia(C,P), reprovado_sem_exame(C,P).
:- reprovado_frequencia(C,P), deve_fazer_exame(C,P).
:- reprovado_frequencia(C,P), reprovado_nota(C,P).
:- reprovado_sem_exame(C,P), aprovado(C,P).
:- reprovado_sem_exame(C,P), deve_fazer_exame(C,P).
:- reprovado_sem_exame(C,P), reprovado_nota(C,P).
:- deve_fazer_exame(C,P), aprovado(C,P).
:- deve_fazer_exame(C,P), reprovado_nota(C,P).