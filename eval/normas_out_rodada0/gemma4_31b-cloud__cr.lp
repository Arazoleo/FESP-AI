%! uc_computavel | Art. 135 e 136 | Define quais UCs entram no cálculo do CR
uc_computavel(C, P) :- 
    matricula(C, P),
    not trancada(C, P),
    not cancelada(C, P),
    not aproveitamento(C, P),
    not natureza_excluida(C),
    not nota_nao_aplicavel(C).

%! trancada | Art. 136, I | Identifica UC trancada no período
trancada(C, P) :- matricula(C, P), trancamento(P, _).

%! cancelada | Art. 136, II | Identifica UC cancelada
cancelada(C, P) :- situacao(C, P, "cancelado").

%! aproveitamento | Art. 136, III | Identifica UC com aproveitamento de estudos
aproveitamento(C, P) :- situacao(C, P, "aproveitamento").

%! natureza_excluida | Art. 136, IV | UCs de TCC, Estágio, AC
natureza_excluida(C) :- natureza(C, "tcc").
natureza_excluida(C) :- natureza(C, "estagio").
natureza_excluida(C) :- natureza(C, "ac").

%! nota_nao_aplicavel | Art. 136, IV | UCs sem avaliação por nota
nota_nao_aplicavel(C) :- situacao(C, P, "cumprido"), not nota10(C, P, _).

%! nota_efetiva | Art. 135 | Define a nota a ser usada (0 se reprovado por freq)
nota_efetiva(C, P, N) :- 
    uc_computavel(C, P), 
    not reprovado_frequencia(C, P), 
    nota10(C, P, N).

nota_efetiva(C, P, 0) :- 
    uc_computavel(C, P), 
    reprovado_frequencia(C, P).

%! soma_produtos | Art. 133 e 134 | Calcula a soma de (Nota * Carga)
% Como ASP não possui somatórios dinâmicos em versões básicas sem agregados, 
% assume-se o uso de #sum para a implementação do cálculo do CR.
soma_produtos(S) :- S = #sum { N * H, C, P : nota_efetiva(C, P, N), carga(C, H) }.

%! soma_cargas | Art. 133 e 134 | Calcula a soma das cargas horárias
soma_cargas(H_total) :- H_total = #sum { H, C, P : nota_efetiva(C, P, _), carga(C, H) }.

%! cr_x1000 | Art. 132, §1º e Art. 134 | CR acumulado x1000 sem arredondamento
% Fórmula: CR = (Sum(N * H) / Sum(H))
% Para obter CR * 1000 com notas N (que já são nota*10):
% CR_real = (Sum(N/10 * H) / Sum(H)) = Sum(N*H) / (10 * Sum(H))
% CR_x1000 = (Sum(N*H) * 1000) / (10 * Sum(H)) = (Sum(N*H) * 100) / Sum(H)
cr_x1000(X) :- 
    soma_produtos(S), 
    soma_cargas(H), 
    H > 0, 
    X = (S * 100) / H.

% Caso não haja UCs computáveis, o CR é 0
cr_x1000(0) :- not soma_cargas(_).