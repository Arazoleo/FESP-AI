%! art124_i | Art. 124, I | Falha por frequência obriga presencial
deve_cursar_presencial(C) :-
    pendente(C),
    reprovado_frequencia(C,_),
    not pode_rer(C).

%! art124_ii | Art. 124, II | Falha por nota em duas ou mais UCs obriga presencial
many_nota_falhas :- 2 <= #count{ C : reprovado_nota(C,_) }.
deve_cursar_presencial(C) :-
    pendente(C),
    reprovado_nota(C,_),
    many_nota_falhas,
    not pode_rer(C).

%! art124_iii | Art. 124, III | UC que é pré‑requisito de outra obriga presencial
deve_cursar_presencial(C) :-
    pendente(C),
    prereq(C,_),
    not pode_rer(C).

%! art124_iv | Art. 124, IV | UC não passível de RER obriga presencial
nao_passivel_rer(C) :- rer_vedado(C).
nao_passivel_rer(C) :- uc_pratica(C).
deve_cursar_presencial(C) :-
    pendente(C),
    nao_passivel_rer(C),
    not pode_rer(C).

%! art124_v | Art. 124, V | UC cursada em RER obriga presencial
deve_cursar_presencial(C) :-
    em_rer(C,_),
    not pode_rer(C).

% ----------------------------------------------------------------------
%! art128 | Art. 128 | RER só para reprovação por nota
% (usado implicitamente nas condições de pode_rer/1)

%! art129 | Art. 129 | UC prática ou vedada não pode ser RER
nao_elegivel_rer(C) :- uc_pratica(C).
nao_elegivel_rer(C) :- rer_vedado(C).

%! art130_3 | Art. 130 §3 | UC pode ser cursada em RER no máximo uma vez
ja_em_rer(C) :- em_rer(C,_).

% ----------------------------------------------------------------------
%! pode_rer | Art. 128‑130 | Condições para poder cursar UC em RER
% 1) UC pendente e reprovada por nota
% 2) Falha por nota única no seu período (exatamente uma UC reprovada por nota naquele período)
% 3) UC não prática e não vedada
% 4) Ainda não foi cursada em RER
% 5) Não há outro RER matriculado no semestre corrente

% única falha por nota no período P
unica_falha_nota(C,P) :-
    reprovado_nota(C,P),
    1 = #count{ C2 : reprovado_nota(C2,P) }.

pode_rer(C) :-
    pendente(C),
    unica_falha_nota(C,_),          % a UC tem a única reprovação por nota no seu período
    not nao_elegivel_rer(C),        % não é prática nem vedada
    not ja_em_rer(C),               % ainda não está em RER
    periodo_atual(P_atual),
    0 = #count{ C2 : em_rer(C2,P_atual), C2 != C }.   % nenhum outro RER no semestre corrente