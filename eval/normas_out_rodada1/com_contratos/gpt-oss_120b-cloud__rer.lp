% ------------------------------------------------------------
% Auxiliares para contagem de reprovações por nota
%! aux_many_grade_fails | Art.124 II | verifica se há ≥2 reprovações por nota
many_grade_fails :- N = #count { C,P : reprovado_nota(C,P) }, N >= 2.

%! aux_one_grade_fail_in_period | Art.130 §5 | exatamente 1 reprovação por nota no período P
one_grade_fail_in_period(P) :-
    reprovado_nota(_,P),                     % garante que P está instanciado
    N = #count { C : reprovado_nota(C,P) },
    N = 1.

%! aux_other_em_rer_in_period | Art.130 §5 | já existe outra UC em RER no mesmo período
other_em_rer_in_period(C,P) :-
    reprovado_nota(C,_),                     % garante que C está instanciado
    period(P),                               % garante que P está instanciado
    em_rer(D,P),
    D != C.

% ------------------------------------------------------------
% 1. Regras para determinar se a UC deve ser cursada presencialmente
%! art124_i | Art.124 I | reprovação por frequência
deve_cursar_presencial(C) :- reprovado_frequencia(C,P).

%! art124_ii | Art.124 II | reprovação por nota em ≥2 UCs
deve_cursar_presencial(C) :- reprovado_nota(C,P), many_grade_fails.

%! art124_iii | Art.124 III | UC que é pré‑requisito de outra e está pendente
deve_cursar_presencial(C) :- prereq(C,_), pendente(C).

%! art124_iv_a | Art.124 IV | UC prática e pendente
deve_cursar_presencial(C) :- pendente(C), uc_pratica(C).

%! art124_iv_b | Art.124 IV | UC vedada ao RER e pendente
deve_cursar_presencial(C) :- pendente(C), rer_vedado(C).

%! art124_v | Art.124 V | UC já matriculada em regime especial de recuperação
deve_cursar_presencial(C) :- em_rer(C,P).

% ------------------------------------------------------------
% 2. Regras para determinar se a UC pode ser cursada em Regime Especial de Recuperação
%! pode_rer_rule | Art.128, Art.129, Art.130 | condições de elegibilidade ao RER
pode_rer(C) :-
    reprovado_nota(C,P),          % Art.128: reprovação por nota
    pendente(C),                  % ainda não cumprida
    not uc_pratica(C),            % Art.129: não prática
    not rer_vedado(C),            % Art.129: não vedada pela comissão
    not em_rer(C,_),              % Art.130 §3: ainda não cursada em RER
    one_grade_fail_in_period(P), % Art.130 §1: única reprovação por nota no período
    not other_em_rer_in_period(C,P). % Art.130 §5: só um RER por semestre