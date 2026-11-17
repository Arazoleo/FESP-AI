%! uc_calculavel | Art. 135 e 136 | Define se a UC entra no cálculo do CR
uc_calculavel(C, P) :- 
    matricula(C, P),
    not trancada(C, P),
    not cancelada(C, P),
    not aproveitamento(C, P),
    not natureza_excluida(C),
    not nota_nao_aplicavel(C).

%! trancada | Art. 136, I | UC trancada
trancada(C, P) :- matricula(C, P), trancamento(P, _).

%! cancelada | Art. 136, II | UC cancelada
cancelada(C, P) :- situacao(C, P, "cancelado").

%! aproveitamento | Art. 136, III | UC com aproveitamento de estudos
aproveitamento(C, P) :- situacao(C, P, "aproveitamento").

%! natureza_excluida | Art. 136, IV | TCC, Estágio, AC
natureza_excluida(C) :- natureza(C, "tcc").
natureza_excluida(C) :- natureza(C, "estagio").
natureza_excluida(C) :- natureza(C, "ac").

%! nota_nao_aplicavel | Art. 136, IV | UC sem avaliação por nota
nota_nao_aplicavel(C) :- uc_pratica(C), not nota_registrada(C).
nota_registrada(C) :- matricula(C, P), nota10(C, P, _).

%! nota_efetiva | Art. 135 | Define a nota a ser usada (0 se reprovado por freq)
nota_efetiva(C, P, N) :- 
    uc_calculavel(C, P), 
    not reprovado_frequencia(C, P), 
    nota10(C, P, N).

nota_efetiva(C, P, 0) :- 
    uc_calculavel(C, P), 
    reprovado_frequencia(C, P).

%! nota_rer | Art. 135, III | Notas de RER são consideradas
nota_efetiva(C, P, N) :- 
    uc_calculavel(C, P), 
    em_rer(C, P), 
    nota10(C, P, N).

%! soma_ponderada | Art. 133 e 134 | Soma de (Nota * Carga)
% Como Clingo não possui soma agregada simples em versões antigas sem #sum, 
% utilizamos a agregação #sum para calcular o numerador e denominador.
soma_produtos(S) :- S = #sum { N * H, C, P : nota_efetiva(C, P, N), carga(C, H) }.
soma_cargas(H_total) :- H_total = #sum { H, C, P : nota_efetiva(C, P, _) }, carga(C, H).

%! cr_x1000 | Art. 132, §1º e Art. 134 | CR acumulado * 1000 (sem arredondamento)
% Fórmula: CR = (Sum(N * H) / Sum(H))
% Para obter CR * 1000 sem arredondamento: (SomaProdutos * 100 * 1000) / (SomaCargas * 10)
% Nota: nota10 já é N*10. Então SomaProdutos é Sum(N*10 * H).
% CR = Sum(N*10 * H) / (Sum(H) * 10)
% CR * 1000 = (Sum(N*10 * H) * 1000) / (Sum(H) * 10) = (Sum(N*10 * H) * 100) / Sum(H)
cr_x1000(X) :- 
    soma_produtos(S), 
    soma_cargas(H_total), 
    H_total > 0, 
    X = (S * 100) / H_total.

% Caso não haja UCs cursadas
cr_x1000(0) :- not soma_cargas(_).