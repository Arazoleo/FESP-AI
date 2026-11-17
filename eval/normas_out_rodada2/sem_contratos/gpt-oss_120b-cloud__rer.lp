% ------------------------------------------------------------
%  Art. 124 - I | Falha por frequência gera presencial
% ------------------------------------------------------------
deve_cursar_presencial(C) :-
    pendente(C),
    reprovado_frequencia(C,_).

% ------------------------------------------------------------
%  Art. 124 - II | Falha por nota em duas ou mais UCs gera presencial
% ------------------------------------------------------------
deve_cursar_presencial(C) :-
    pendente(C),
    reprovado_nota(C,_),
    N = #count { C2 : pendente(C2), reprovado_nota(C2,_) },
    N >= 2.

% ------------------------------------------------------------
%  Art. 124 - III | UC pendente que é pré‑requisito de outra deve ser presencial
% ------------------------------------------------------------
deve_cursar_presencial(C) :-
    pendente(C),
    prereq(C,_).

% ------------------------------------------------------------
%  Art. 124 - IV | UC não passível de RER (vedada ou prática) gera presencial
% ------------------------------------------------------------
deve_cursar_presencial(C) :-
    pendente(C),
    rer_vedado(C).

deve_cursar_presencial(C) :-
    pendente(C),
    uc_pratica(C).

% ------------------------------------------------------------
%  Art. 124 - V | UC pendente em regime especial de recuperação gera presencial
% ------------------------------------------------------------
deve_cursar_presencial(C) :-
    pendente(C),
    em_rer(C,_).

% ------------------------------------------------------------
%  Auxiliar: verifica se já existe mais de um RER no mesmo período
% ------------------------------------------------------------
outro_rer(P) :-
    em_rer(D,P),
    em_rer(E,P),
    D != E.

% ------------------------------------------------------------
%  Art. 130 - Condições para poder cursar RER
% ------------------------------------------------------------
pode_rer(C) :-
    pendente(C),                     % UC ainda não aprovada
    reprovado_nota(C,P),              % falha por nota no período P
    % apenas uma UC reprovada por nota no mesmo período
    N = #count { C2 : pendente(C2), reprovado_nota(C2,P) },
    N = 1,
    % UC deve ser permitida para RER
    not uc_pratica(C),
    not rer_vedado(C),
    % UC ainda não foi cursada em RER anteriormente
    not em_rer(C,_),
    % não há outra UC já matriculada em RER no mesmo período
    not outro_rer(P).

% ------------------------------------------------------------
%  Art. 130 - §3 | Uma UC pode ser cursada em RER apenas uma vez
% ------------------------------------------------------------
% (garantido por `not em_rer(C,_)` acima)

% ------------------------------------------------------------
%  Art. 130 - §5 | Só um RER por semestre (período)
% ------------------------------------------------------------
% (garantido por `not outro_rer(P)` acima)