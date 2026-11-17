%! uc_computavel | Art. 135 e 136 | Define quais UCs entram no cálculo do CR
% Art. 136: Não são considerados trancamentos, cancelamentos, aproveitamentos e naturezas específicas
% Art. 135: Considera RER e UCs onde não houve reprovação por frequência
uc_computavel(C, P) :- 
    matricula(C, P),
    not situacao(C, P, aproveitamento),
    not natureza(C, tcc),
    not natureza(C, estagio),
    not natureza(C, ac),
    not situacao(C, P, cancelado),
    not trancada(C, P).

% Auxiliar para trancamento de UC
trancada(C, P) :- matricula(C, P), trancamento(P, _).

%! nota_efetiva | Art. 135, I e II | Define a nota a ser usada (0 se reprovado por frequência)
% Art. 135, II: Nota igual a 0 se reprovado por frequência
nota_efetiva(C, P, 0) :- 
    uc_computavel(C, P), 
    reprovado_frequencia(C, P).

% Art. 135, I e III: Nota final se não reprovado por frequência (inclui RER)
nota_efetiva(C, P, N) :- 
    uc_computavel(C, P), 
    not reprovado_frequencia(C, P), 
    nota10(C, P, N).

%! soma_produtos | Art. 133 e 134 | Calcula a soma de (Nota * Carga)
soma_produtos(S) :- 
    S = #sum { (N * H), C, P : nota_efetiva(C, P, N), carga(C, H), uc_computavel(C, P) }.

%! soma_cargas | Art. 133 e 134 | Calcula a soma das cargas horárias das UCs computáveis
soma_cargas(H_total) :- 
    H_total = #sum { H, C, P : uc_computavel(C, P), carga(C, H) }.

%! tem_carga_positiva | Auxiliar | Verifica se existe carga horária para evitar divisão por zero
tem_carga_positiva() :- 
    soma_cargas(H), 
    H > 0.

%! cr_x1000 | Art. 132, §1º e Art. 134 | Calcula o CR acumulado x1000 sem arredondamento
% CR = (sum(N * H) / sum(H))
% Como nota_efetiva usa N*10, a soma_produtos já é 10 * sum(N * H)
% CR * 1000 = (SomaProdutos / SomaCargas) * 100
cr_x1000(X) :- 
    tem_carga_positiva(),
    soma_produtos(S), 
    soma_cargas(H), 
    X = (S * 100) / H.

% Caso não haja UCs computáveis ou carga zero, o CR é 0
cr_x1000(0) :- 
    not tem_carga_positiva().