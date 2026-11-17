%! CR1 | Art. 132 | Coeficiente de Rendimento acumulado
%! CR2 | Art. 133 | Indicadores N e H
%! CR3 | Art. 135 | Considerações de notas
%! CR4 | Art. 136 | Exclusões
%! CR5 | Art. 134 | Fórmula de cálculo

% UC considerada para o cálculo do CR acumulado
trancado(P) :- trancamento(P,T).

disallowed_nature(Nc) :- Nc = tcc.
disallowed_nature(Nc) :- Nc = estagio.
disallowed_nature(Nc) :- Nc = ac.

considered(C,P) :-
    matricula(C,P),
    ingresso(P0),
    P >= P0,
    not trancado(P),
    not situacao(C,P,aproveitamento),
    nota10(C,P,N),
    natureza(C,Nc),
    not disallowed_nature(Nc).

% Nota final usada no cálculo
nota_final(C,P,0) :-
    reprovado_frequencia(C,P),
    considered(C,P).

nota_final(C,P,Nf) :-
    not reprovado_frequencia(C,P),
    considered(C,P),
    nota10(C,P,Nf).

% CR acumulado ×1000 (inteiro)
cr_x1000(X) :-
    W = #sum{Nf*H : considered(C,P), nota_final(C,P,Nf), carga(C,H)},
    H = #sum{H : considered(C,P), carga(C,H)},
    H > 0,
    X = (100 * W) / H.

cr_x1000(0) :-
    H = #sum{H : considered(C,P), carga(C,H)},
    H = 0.