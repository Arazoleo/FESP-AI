%! cr_periodo_valido | Art. 133 | Só períodos até o atual são usados
periodo_valido(P) :-
    matricula(_,P),               % P aparece em um fato positivo
    periodo_atual(Pa),
    P <= Pa.

%! cr_excluido | Art. 136 | Exclusões do cálculo do CR
excluido(C,P) :- situacao(C,P,aproveitamento).          % aproveitamento de outra instituição
excluido(C,P) :- natureza(C,tcc),    matricula(C,P).   % trabalho de conclusão de curso
excluido(C,P) :- natureza(C,estagio),matricula(C,P).   % estágio curricular
excluido(C,P) :- natureza(C,ac),     matricula(C,P).   % atividade acadêmico‑científico‑cultural
excluido(C,P) :- trancamento(P,_),  matricula(C,P).   % trancamento de matrícula no período

%! cr_considerado | Art. 135, 136 | UC que entra no cálculo do CR
considerado(C,P) :-
    matricula(C,P),
    periodo_valido(P),
    not excluido(C,P).

%! cr_nota_ajustada | Art. 135 | Nota usada no cálculo (0 se reprovado por frequência)
nota_para_cr(C,P,0) :- reprovado_frequencia(C,P).
nota_para_cr(C,P,N) :-
    not reprovado_frequencia(C,P),
    nota10(C,P,N).

%! cr_total_horas | Art. 134 (denominador)
total_horas(T) :-
    T = #sum { H : considerado(C,P), carga(C,H) }.

%! cr_soma_ponderada | Art. 134 (numerador)
soma_ponderada(S) :-
    S = #sum { N*H : considerado(C,P), carga(C,H), nota_para_cr(C,P,N) }.

%! cr_numerador | auxiliar para garantir que a multiplicação ocorre antes da divisão
numerador(N) :-
    soma_ponderada(S),
    N = S * 100.

%! cr_acumulado | Art. 134 | CR acumulado ×1000 (truncado, três casas decimais)
cr_x1000(X) :-
    total_horas(T), T > 0,
    numerador(N),
    X = N / T.   % nota10 está ×10; (S*100)/T = floor(CR*1000)