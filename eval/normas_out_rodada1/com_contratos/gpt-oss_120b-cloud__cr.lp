%! considera_uc | Art. 135 | UC são consideradas se não forem excluídas nem trancadas.
considera(C,P) :-
    matricula(C,P),
    carga(C,_),
    not excluida(C),
    not trancada_periodo(P).

%! exclui_natureza | Art. 136 I‑III | TCC, estágio e atividades sem nota são excluídas.
excluida(C) :- natureza(C,tcc).
excluida(C) :- natureza(C,estagio).
excluida(C) :- natureza(C,ac).

%! trancada_periodo | Art. 136 I | Períodos com trancamento de matrícula são ignorados.
trancada_periodo(P) :- trancamento(P,_).

%! nota_uso | Art. 135 I‑III | Nota 0 se reprovado por frequência; caso contrário a nota registrada ×10.
nota_uso(C,P,0)      :- reprovado_frequencia(C,P).
nota_uso(C,P,N10)    :- not reprovado_frequencia(C,P), nota10(C,P,N10).

%! soma_nota_h | Art. 134 | Soma (nota×10) × carga horária das UC consideradas.
soma_nota_h(SN) :-
    SN = #sum { N10*H : considera(C,P), nota_uso(C,P,N10), carga(C,H) }.

%! soma_carga | Art. 134 | Soma das cargas horárias das UC consideradas.
soma_carga(SC) :-
    SC = #sum { H : considera(C,P), carga(C,H) }.

%! cr_acumulado | Art. 134 | CR acumulado ×1000 (truncado) limitado ao intervalo 0..10000.
cr_x1000(X) :-
    soma_nota_h(SN),
    soma_carga(SC),
    SC > 0,
    X = (SN * 100) / SC,   % divisão inteira (trunca) → CR×1000
    X >= 0,
    X <= 10000.