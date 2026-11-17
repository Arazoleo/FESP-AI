%! art146 | Definição de trancamento | Suspensão das atividades acadêmicas por período determinado
trancamento_regular(P) :- trancamento(P, regular).

%! art147 | Limite total de trancamento regular | Não pode exceder 1 ano (2 semestres) no total
total_regular_trancado(N) :- N = #count { P : trancamento(P, regular) }.

%! art148_I | Vedação: estudante no primeiro ano
primeiro_ano :- periodo_atual(Pa), ingresso(P0), Pa <= P0 + 1.

%! art148_II | Vedação: transferência no mesmo ano
transferido_mesmo_ano :- transferido_no_ano(Y), ano_atual(Y).

%! art148_III | Vedação: processo disciplinar
proibido_trancar :- processo_disciplinar.

%! art148 | Conjunto de vedações
proibido :- primeiro_ano.
proibido :- transferido_mesmo_ano.
proibido :- proibido_trancar.

%! art147 | Possibilidade de solicitar trancamento regular agora
pode_trancar :- 
    not proibido,
    total_regular_trancado(N),
    N < 2.