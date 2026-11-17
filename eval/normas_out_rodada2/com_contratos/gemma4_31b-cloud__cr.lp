%! uc_calculavel | Art. 135 e 136 | Define quais UCs entram no cálculo do CR
% Art. 136: Não são considerados trancamentos, cancelamentos, aproveitamentos e naturezas específicas
% Art. 135: Considera RER e UCs onde não houve reprovação por frequência
uc_calculavel(C, P) :- 
    matricula(C, P),
    not situacao(C, P, aproveitamento),
    not natureza(C, tcc),
    not natureza(C, estagio),
    not natureza(C, ac),
    not situacao(C, P, cancelado), % Inferido de "cancelamentos de UCs"
    not situacao(C, P, trancado).   % Inferido de "trancamentos de matrícula"

%! nota_efetiva | Art. 135, I e II | Define a nota a ser usada (0 se reprovado por frequência)
% Art. 135, II: Nota = 0 se reprovado por frequência
nota_efetiva(C, P, 0) :- 
    uc_calculavel(C, P), 
    reprovado_frequencia(C, P).

% Art. 135, I e III: Nota final se não reprovado por frequência (inclui RER)
nota_efetiva(C, P, N) :- 
    uc_calculavel(C, P), 
    nota10(C, P, N), 
    not reprovado_frequencia(C, P).

%! soma_produtos | Art. 133 e 134 | Calcula a soma de (Nota * Carga)
% O CR é a média ponderada: sum(N * H) / sum(H)
% Como nota10 é N*10, a soma será sum(N*10 * H)
soma_produtos(S) :- 
    S = #sum { N * H, C, P : nota_efetiva(C, P, N), carga(C, H), uc_calculavel(C, P) }.

%! soma_cargas | Art. 133 e 134 | Calcula a soma das cargas horárias das UCs computadas
soma_cargas(H_total) :- 
    H_total = #sum { H, C, P : uc_calculavel(C, P), carga(C, H) }.

%! cr_x1000 | Art. 132, §1º e Art. 134 | Calcula o CR acumulado x1000 sem arredondamento
% Fórmula: CR = (sum(N * H) / sum(H))
% Para obter CR * 1000:
% CR_real = (SomaProdutos / 10) / SomaCargas
% CR_x1000 = (SomaProdutos * 100) / SomaCargas
% Exemplo: Nota 7.333 -> nota10=73. SomaProdutos = 73 * 100h = 7300. SomaCargas = 100.
% (7300 * 100) / 100 = 7300. (7.3 * 1000 = 7300).
% O Art. 132 §1º exige 3 casas decimais sem arredondamento (truncamento).
cr_x1000(X) :- 
    soma_produtos(S), 
    soma_cargas(H), 
    H > 0, 
    X = (S * 100) / H.

% Caso não haja UCs cursadas, CR é 0
cr_x1000(0) :- 
    not soma_cargas(_).