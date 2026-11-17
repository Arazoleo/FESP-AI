%! 151 | Art. 151 | Base prazo de integralização
base_prazo(PM0) :-
    integral,
    duracao_minima(D),
    PM0 = D + (D + 1) / 2.

base_prazo(PM0) :-
    parcial,
    duracao_minima(D),
    PM0 = D + (3*D + 3) / 4.

%! 27 | Portaria ProGrad 566/2022 | Acréscimo de 2 semestres
portaria_applicable :- ano_ingresso(A), A >= 2020, A <= 2022.

%! 151 | Art. 151 | Prazo máximo de integralização
prazo_maximo(PM) :-
    base_prazo(PM0),
    portaria_applicable,
    PM = PM0 + 2.

prazo_maximo(PM) :-
    base_prazo(PM0),
    not portaria_applicable,
    PM = PM0.

%! 151 | Art. 151 | Semestres restantes
semestres_computados(C) :-
    periodo_atual(P0),
    C = #count{P : matricula(_,P), P <= P0}.

semestres_restantes(R) :-
    prazo_maximo(PM),
    semestres_computados(C),
    R = PM - C.

%! 151 | Art. 151 | Definição de período
period(P) :- matricula(_,P).

%! 145 | Art. 145 | Risco de cancelamento por prazo excedido
risco_cancelamento(prazo_excedido) :-
    semestres_restantes(R),
    R <= 0.

%! 145 | Art. 145 | Risco de cancelamento por reprovação total de frequência
has_uc(P) :- matricula(_,P).

some_uc_not_reprovado(P) :- matricula(C,P), not reprovado_frequencia(C,P).

all_reprovado_semester(P) :- has_uc(P), not some_uc_not_reprovado(P).

risco_cancelamento(reprovacao_total_frequencia) :-
    all_reprovado_semester(P),
    P1 = P + 1,
    period(P1),
    all_reprovado_semester(P1).