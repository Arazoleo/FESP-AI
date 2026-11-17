%! uc_computavel | Art. 135 e 136 | Define quais UCs entram no cálculo do CR
% Art. 136: Não são considerados trancamentos, cancelamentos, aproveitamentos e naturezas específicas
% Art. 135: Considera RER e UCs onde não houve reprovação por frequência
uc_computavel(C, P) :- 
    matricula(C, P),
    not situacao(C, P, aproveitamento),
    not natureza(C, tcc),
    not natureza(C, estagio),
    not natureza(C, ac),
    not situacao(C, P, cancelado), % Inferido de "cancelamentos de UCs"
    not situacao(C, P, trancado),  % Inferido de "trancamentos de matrícula"
    not avaliacao_sem_nota(C, P).

% Art. 136, IV: UC cuja avaliação não tenha sido realizada por meio de nota
avaliacao_sem_nota(C, P) :- matricula(C, P), situacao(C, P, cumprido), not nota10(C, P, _).

%! nota_efetiva | Art. 135, I e II | Define a nota a ser usada (0 se reprovado por frequência)
% Art. 135, II: Nota igual a 0 se reprovado por frequência
nota_efetiva(C, P, 0) :- 
    uc_computavel(C, P), 
    reprovado_frequencia(C, P).

% Art. 135, I e III: Nota final se não reprovado por frequência (inclui RER)
nota_efetiva(C, P, N) :- 
    uc_computavel(C, P), 
    nota10(C, P, N), 
    not reprovado_frequencia(C, P).

%! soma_produtos | Art. 133 e 134 | Calcula a soma de (Nota * Carga)
% O CR é a média ponderada: Sum(Nota * Carga) / Sum(Carga)
% Como nota10 é N*10, a soma será Sum(N*10 * H)
soma_produtos(S) :- 
    S = #sum { N * H, C, P : nota_efetiva(C, P, N), carga(C, H), uc_computavel(C, P) }.

%! soma_cargas | Art. 133 e 134 | Calcula a soma das cargas horárias
soma_cargas(H_total) :- 
    H_total = #sum { H, C, P : uc_computavel(C, P), carga(C, H) }.

%! cr_x1000 | Art. 132, §1º e Art. 134 | Calcula o CR acumulado x1000 sem arredondamento
% Fórmula: CR = Sum(N * H) / Sum(H)
% CR_x1000 = (Sum(N_10 * H) * 100) / Sum(H)
% Exemplo: Nota 5.9 (N=59), Carga 60. Sum(N*H) = 3540. Sum(H) = 60.
% (3540 * 100) / 60 = 354000 / 60 = 5900. 
% Como o resultado final deve ser CR * 1000, e N já é Nota * 10:
% CR = (Sum(N_10 * H) / 10) / Sum(H) = Sum(N_10 * H) / (10 * Sum(H))
% CR * 1000 = Sum(N_10 * H) * 100 / Sum(H)
cr_x1000(CR1000) :- 
    soma_produtos(S), 
    soma_cargas(H), 
    H > 0, 
    CR1000 = (S * 100) / H.

% Caso não haja UCs computáveis, CR é 0
cr_x1000(0) :- 
    not soma_cargas(_).