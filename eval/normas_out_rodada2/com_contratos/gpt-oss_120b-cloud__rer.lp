%=====================================================================
%! art124_i | Art. 124, I | Falha por frequência obriga presencial
deve_cursar_presencial(C) :-
    pendente(C),
    reprovado_frequencia(C,_).

%=====================================================================
%! art124_ii | Art. 124, II | Falha por nota em duas ou mais UCs obriga presencial
total_falhas_nota(N) :- N = #count { C : reprovado_nota(C,_) }.
deve_cursar_presencial(C) :-
    pendente(C),
    reprovado_nota(C,_),
    total_falhas_nota(N),
    N >= 2.

%=====================================================================
%! art124_iii | Art. 124, III | UC que é pré‑requisito de outra obriga presencial
deve_cursar_presencial(C) :-
    pendente(C),
    prereq(C,_).

%=====================================================================
%! art124_iv | Art. 124, IV | UC não passível de RER obriga presencial
cond_veto(C) :- rer_vedado(C).
cond_veto(C) :- uc_pratica(C).
deve_cursar_presencial(C) :-
    pendente(C),
    cond_veto(C).

%=====================================================================
%! art124_v | Art. 124, V | Falha em regime especial de recuperação obriga presencial
deve_cursar_presencial(C) :-
    pendente(C),
    em_rer(C,_).

%=====================================================================
%! art130_1 | Art. 130, §1 | Só pode haver RER se houver única falha por nota no período
grade_fails_period(P,N) :- 
    periodo(P),
    N = #count { C : reprovado_nota(C,P) }.
unica_falha_nota(P) :- grade_fails_period(P,1).

%=====================================================================
%! outro_rer | Auxiliar | Detecta outro RER no mesmo período
outro_rer(C,P) :- 
    em_rer(C2,P),
    C2 != C,
    pendente(C).

%=====================================================================
%! pode_rer | Art. 128‑130 | Condições para poder cursar UC em RER
pode_rer(C) :-
    reprovado_nota(C,P),          % falha por nota
    pendente(C),                  % ainda não cumprida
    unica_falha_nota(P),          % única falha por nota no período
    not uc_pratica(C),            % não é prática
    not rer_vedado(C),            % não é vedada pela comissão
    not em_rer(C,_),              % ainda não está em RER
    not outro_rer(C,P).           % nenhum outro RER no mesmo período