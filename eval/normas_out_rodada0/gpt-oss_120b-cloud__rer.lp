%! art124_i | Art. 124 I | Falha por frequência obriga presencial
deve_cursar_presencial(C) :-
    reprovado_frequencia(C,_P),
    pendente(C).

%! art124_ii | Art. 124 II | Falha por nota em duas ou mais UCs obriga presencial
deve_cursar_presencial(C) :-
    reprovado_nota(C,_),
    #count{ C2 : reprovado_nota(C2,_) } >= 2.

%! art124_iii | Art. 124 III | UC que é pré‑requisito de outra obriga presencial
deve_cursar_presencial(C) :-
    prereq(C,_B),
    pendente(C).

%! art124_iv | Art. 124 IV | UC não passível de RER obriga presencial
deve_cursar_presencial(C) :-
    pendente(C),
    ( rer_vedado(C) ; uc_pratica(C) ).

%! art124_v | Art. 124 V | UC já matriculada em RER obriga presencial
deve_cursar_presencial(C) :-
    em_rer(C,_P),
    pendente(C).

%! art130_1 | Art. 130 §1 | RER só se houver exatamente uma reprovação por nota no período
%! art130_3 | Art. 130 §3 | Uma UC só pode ser cursada em RER uma única vez
%! art130_5 | Art. 130 §5 | Só um RER por semestre
pode_rer(C) :-
    reprovado_nota(C,P),
    pendente(C),
    not rer_vedado(C),
    not uc_pratica(C),
    not em_rer(C,_),
    #count{ C2 : reprovado_nota(C2,P) } = 1,
    not em_rer(_,P).