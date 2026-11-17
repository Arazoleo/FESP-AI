%! art124_i | Art.124 I | Reprovado por frequência
cond_i(C) :- pendente(C), reprovado_frequencia(C,_).

%! art124_ii | Art.124 II | Reprovado por nota em duas ou mais UCs
cond_ii(C) :- pendente(C), #count{U : reprovado_nota(U,_)} >= 2.

%! art124_iii | Art.124 III | UC é pré‑requisito de outra UC que o estudante cursa
cond_iii(C) :- pendente(C), prereq(C,B), matricula(B,_).

%! art124_iv | Art.124 IV | UC não passível de regime especial de recuperação
cond_iv(C) :- pendente(C), uc_pratica(C).
cond_iv(C) :- pendente(C), rer_vedado(C).

%! art124_v | Art.124 V | UC já está em regime especial de recuperação
cond_v(C) :- pendente(C), em_rer(C,_).

%! pres_presencial | Art.124 | UC que deve ser cursada presencialmente
deve_cursar_presencial(C) :- cond_i(C).
deve_cursar_presencial(C) :- cond_ii(C).
deve_cursar_presencial(C) :- cond_iii(C).
deve_cursar_presencial(C) :- cond_iv(C).
deve_cursar_presencial(C) :- cond_v(C).

%! single_fail_in_period | Art.130 §1 | Apenas uma UC reprovada por nota no período
single_fail_in_period(P) :- #count{U : reprovado_nota(U,P)} = 1.

%! other_em_rer | Art.130 §5 | Garante que não haja outro RER no mesmo período
other_em_rer(C,P) :- em_rer(O,P), O != C.

%! rer_permitido | Art.128, Art.129, Art.130 | Condições para poder cursar RER
pode_rer(C) :-
    pendente(C),
    reprovado_nota(C,P),
    single_fail_in_period(P),
    not uc_pratica(C),
    not rer_vedado(C),
    not em_rer(C,P),
    not other_em_rer(C,P).