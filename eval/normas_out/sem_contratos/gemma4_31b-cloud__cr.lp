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
    not situacao(C, P, trancado),   % Inferido de "trancamentos de matrícula"
    not uc_sem_nota(C).

% Predicado auxiliar para UCs cuja avaliação não seja por nota (Art. 136, IV)
uc_sem_nota(C) :- natureza(C, tcc).
uc_sem_nota(C) :- natureza(C, estagio).
uc_sem_nota(C) :- natureza(C, ac).

%! nota_efetiva | Art. 135, I e II | Define a nota a ser usada (0 se reprovado por freq)
% Art. 135, I e III: Nota final se não reprovado por freq ou se em RER
nota_efetiva(C, P, N) :- 
    uc_calculavel(C, P), 
    nota10(C, P, N), 
    not reprovado_frequencia(C, P).

nota_efetiva(C, P, N) :- 
    uc_calculavel(C, P), 
    nota10(C, P, N), 
    em_rer(C, P).

% Art. 135, II: Nota zero se reprovado por frequência (e não estiver em RER, pois RER prevalece no inciso III)
nota_efetiva(C, P, 0) :- 
    uc_calculavel(C, P), 
    reprovado_frequencia(C, P), 
    not em_rer(C, P).

%! soma_produtos | Art. 133 e 134 | Calcula a soma de (Nota * Carga)
% O CR é a média ponderada: sum(N * H) / sum(H)
% Como nota10 é N*10, a soma será sum(N*10 * H)
soma_produtos(S) :- 
    S = #sum { N * H, C, P : nota_efetiva(C, P, N), carga(C, H), uc_calculavel(C, P) }.

%! soma_cargas | Art. 133 e 134 | Calcula a soma das cargas horárias
soma_cargas(H_total) :- 
    H_total = #sum { H, C, P : uc_calculavel(C, P), carga(C, H) }.

%! cr_x1000 | Art. 132, §1º e Art. 134 | Calcula o CR acumulado x1000
% Fórmula: (Soma(N*H) / Soma(H))
% Para obter CR * 1000:
% CR = (Soma(N*10 * H) / Soma(H)) / 10
% CR * 1000 = (Soma(N*10 * H) * 100) / Soma(H)
% O Art. 132 §1º exige 3 casas decimais sem arredondamento (truncamento da divisão inteira).
cr_x1000(X) :- 
    soma_produtos(S), 
    soma_cargas(H_total), 
    H_total > 0, 
    X = (S * 100) / H_total.

% Caso o estudante não tenha UCs cursadas, o CR é 0
cr_x1000(0) :- 
    not soma_cargas(_).