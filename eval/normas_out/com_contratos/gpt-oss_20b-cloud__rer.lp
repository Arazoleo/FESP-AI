%! 124 | Art. 124 | O estudante deve cursar UC reprovada e pendente presencialmente sob certas condições

% Reprovado por frequência ou nota
reprovado(C,P) :- reprovado_frequencia(C,P).
reprovado(C,P) :- reprovado_nota(C,P).

% Aprovado (informação oficial)
aprovado(C,P) :- situacao(C,P,aprovado).

% UC ainda pendente (reprovada e não aprovada)
pendente(C) :- reprovado(C,P), not aprovado(C,P).

% Condição de frequência
cond_frequencia(C) :- reprovado_frequencia(C,P), pendente(C).

% Condição de nota em duas ou mais UCs no mesmo período
cond_nota_duas(C) :-
    reprovado_nota(C,P),
    pendente(C),
    #count{C2: reprovado_nota(C2,P)} >= 2.

% Condição de pré-requisito (C é pré-requisito de outra UC)
cond_prereq(C) :- prereq(C,_), pendente(C).

% Condição de UC não passível de RER (vedada ou prática)
cond_nov_rer(C) :- rer_vedado(C), pendente(C).
cond_nov_rer(C) :- uc_pratica(C), pendente(C).

% Condição combinada para presencial
cond_presencial(C) :- cond_frequencia(C).
cond_presencial(C) :- cond_nota_duas(C).
cond_presencial(C) :- cond_prereq(C).
cond_presencial(C) :- cond_nov_rer(C).

% Deve cursar presencialmente
deve_cursar_presencial(C) :- pendente(C), cond_presencial(C).

%! 128 | Art. 128 | RER aplica-se exclusivamente à UC em que o estudante foi reprovado por nota
%! 129 | Art. 129 | RER só para UCs que não são práticas e não são vedadas
%! 130 | Art. 130 | Condições para matrícula em RER

% Pode cursar em RER
pode_rer(C) :-
    reprovado_nota(C,P),
    pendente(C),
    not rer_vedado(C),
    not uc_pratica(C),
    not em_rer(C,_),
    #count{C2: reprovado_nota(C2,P)} = 1.