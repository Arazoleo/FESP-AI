%! art132_1 | Art. 132 §1 | CR varia de 0 a 10, três casas decimais, sem arredondamento
% (não há regras específicas; a escala será garantida pelo cálculo abaixo)

%! art135_i | Art. 135 I | Notas de UC não reprovadas por frequência são consideradas
note10_para_uc(C,P,N) :- not reprovado_frequencia(C,P), nota10(C,P,N).

%! art135_ii | Art. 135 II | Notas de UC reprovadas por frequência são zero
note10_para_uc(C,P,0) :- reprovado_frequencia(C,P).

%! art135_iii | Art. 135 III | Notas de UC em Regime Especial de Recuperação são consideradas
% (já incluídas via note10_para_uc/3; nenhuma regra extra necessária)

%! exclui_trancamento | Art. 136 I | Trancamentos de matrícula não são considerados
excluida(C,P) :- situacao(C,P,S), S = trancado.
excluida(C,P) :- situacao(C,P,S), S = trancamento.

%! exclui_cancelamento | Art. 136 II | Cancelamentos de UC não são considerados
excluida(C,P) :- situacao(C,P,S), S = cancelado.

%! exclui_aproveitamento | Art. 136 III | UC cursadas em outras instituições (aproveitamento) não são consideradas
excluida(C,P) :- situacao(C,P,S), S = aproveitamento.

%! exclui_nota | Art. 136 IV | Atividades sem nota (TCC, estágio, AC) não são consideradas
excluida(C,P) :- natureza(C,N), N = tcc,      matricula(C,P).
excluida(C,P) :- natureza(C,N), N = estagio,  matricula(C,P).
excluida(C,P) :- natureza(C,N), N = ac,       matricula(C,P).

%! exclui_rer_vedado | Art. 136 IV | UC vedada ao RER não é considerada quando está em RER
excluida(C,P) :- em_rer(C,P), rer_vedado(C).

%! considera_uc | Art. 135 | UC que passam nas condições acima são consideradas no cálculo
considerada(C,P) :- matricula(C,P), carga(C,_), not excluida(C,P).

%! soma_notas_carga | Art. 134 | Soma de (nota × carga) para as UC consideradas
soma_nota_carga(S) :- S = #sum { N*H : considerada(C,P), note10_para_uc(C,P,N), carga(C,H) }.

%! soma_carga | Art. 134 | Soma das cargas horárias das UC consideradas
soma_carga(T) :- T = #sum { H : considerada(C,P), carga(C,H) }.

%! cr_acumulado | Art. 134 | Cálculo do CR acumulado ×1000 (truncado)
cr_x1000(X) :-
    soma_nota_carga(S),
    soma_carga(T),
    T > 0,
    X = (S * 100) / T.   % divisão inteira → truncamento, três casas decimais sem arredondamento