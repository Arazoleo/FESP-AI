%! uc_excluida | Art. 136 | exclusões gerais do cálculo do CR
uc_excluida(C,P) :-
    matricula(C,P),
    trancamento(P,_).

uc_excluida(C,P) :-
    matricula(C,P),
    situacao(C,P,cancelado).

uc_excluida(C,P) :-
    matricula(C,P),
    situacao(C,P,aproveitamento).

uc_excluida(C,P) :-
    matricula(C,P),
    natureza(C,N),
    ( N = tcc ; N = estagio ; N = ac ).

%! uc_excluida_rer | Art. 135 III | UC vedada para RER não pode ser considerada
uc_excluida(C,P) :-
    matricula(C,P),
    em_rer(C,P),
    rer_vedado(C).

%! uc_considerada | Art. 135 | UC que entra no cômputo do CR
uc_considerada(C,P) :-
    matricula(C,P),
    not uc_excluida(C,P).

%! nota_ajustada | Art. 135 | nota a ser usada no cálculo (zero se reprovado por frequência)
nota_ajustada10(C,P,0) :-
    uc_considerada(C,P),
    reprovado_frequencia(C,P).

nota_ajustada10(C,P,N) :-
    uc_considerada(C,P),
    not reprovado_frequencia(C,P),
    nota10(C,P,N).

%! cr_x1000 | Art. 134 | CR acumulado multiplicado por 1000 (truncado)
cr_x1000(CR) :-
    H = #sum { Hc : uc_considerada(C,P), carga(C,Hc) },
    H > 0,
    S = #sum { N*Hc : uc_considerada(C,P), carga(C,Hc), nota_ajustada10(C,P,N) },
    CR = (S * 100) / H.