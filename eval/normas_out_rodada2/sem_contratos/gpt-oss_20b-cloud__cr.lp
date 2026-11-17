%! cr | Art. 133 | CR calculado ao final de cada período com base em nota final e carga horária.
%! cr | Art. 135 | notas de UC reprovado por frequência = 0; notas de UC em RER consideradas.
%! cr | Art. 136 | UCs excluídas: trancamento, cancelamento, outras instituições, tcc, estagio, ac, UC sem nota.

% Nota efetiva na UC
note_value(C,P,N) :- nota10(C,P,N), not reprovado_frequencia(C,P).
note_value(C,P,0) :- reprovado_frequencia(C,P).

% UC considerada para o cálculo do CR
considered(C,P) :-
    matricula(C,P),
    not trancamento(P,_),
    not natureza(C,N),
    N != tcc,
    N != estagio,
    N != ac,
    (nota10(C,P,N0) ; reprovado_frequencia(C,P)).

% Soma ponderada das notas
total_weighted(TW) :-
    TW = #sum{N*H : considered(C,P), note_value(C,P,N), carga(C,H)}.

% Soma das cargas horárias
total_hours(TH) :-
    TH = #sum{H : considered(C,P), carga(C,H)}.

% CR acumulado ×1000
cr_x1000(X) :-
    total_weighted(TW),
    total_hours(TH),
    TH > 0,
    X = (TW * 100) // TH.

cr_x1000(0) :-
    total_hours(0).