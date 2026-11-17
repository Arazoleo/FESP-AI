%! prazo_max | Art. 151, I | prazo máximo de integralização com acréscimos
%! semestres_restantes | Art. 151, I | semestres restantes para integralização
%! risco_cancelamento | Art. 145, VIII | risco de cancelamento por prazo excedido ou reprovação total de frequência

%--- Portaria ProGrad 566/2022: acréscimo de 2 semestres para anos 2020-2022
portaria :- ano_ingresso(A), A >= 2020, A <= 2022.

%--- Prazo máximo de integralização (sem exceções do inciso III)
prazo_maximo(P) :-
    integral,
    duracao_minima(D),
    portaria,
    P = D + (D + 1)/2 + 2.
prazo_maximo(P) :-
    parcial,
    duracao_minima(D),
    portaria,
    P = D + (3*D + 3)/4 + 2.
prazo_maximo(P) :-
    integral,
    duracao_minima(D),
    not portaria,
    P = D + (D + 1)/2.
prazo_maximo(P) :-
    parcial,
    duracao_minima(D),
    not portaria,
    P = D + (3*D + 3)/4.

%--- Semestres já computados para integralização (contando o período atual)
semestres_restantes(R) :-
    prazo_maximo(P),
    periodo_atual(P0),
    Count = #count{P1: matricula(_,P1), P1 <= P0},
    R = P - Count.

%--- Risco de cancelamento por prazo excedido
risco_cancelamento(prazo_excedido) :-
    semestres_restantes(R),
    R < 0.

%--- Risco de cancelamento por reprovação total de frequência em dois semestres consecutivos
has_uc(P) :- matricula(_,P).

exists_uc_not_reprovado(P) :-
    matricula(C,P),
    not reprovado_frequencia(C,P).

all_reprovado(P) :-
    has_uc(P),
    not exists_uc_not_reprovado(P).

consecutive_reprovado(P1,P2) :-
    all_reprovado(P1),
    all_reprovado(P2),
    P2 = P1 + 1.

risco_cancelamento(reprovacao_total_frequencia) :-
    consecutive_reprovado(P1,P2).