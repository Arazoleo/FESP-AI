%! 124 | Art. 124 | Estudante deve cursar UC presencialmente em certas situações
% Condição I – reprovado por frequência
cond1(C) :- reprovado_frequencia(C,P), pendente(C).

% Condição II – reprovado por nota em duas ou mais UCs
cond2(C) :- pendente(C),
            #count{C2,P: reprovado_nota(C2,P), pendente(C2)} >= 2.

% Condição III – UC é pré-requisito de outra
cond3(C) :- prereq(C,_), pendente(C).

% Condição IV – UC não passível de RER (vedada ou prática)
cond4(C) :- rer_vedado(C), pendente(C).
cond4(C) :- uc_pratica(C), pendente(C).

% Condição V – UC já em RER
cond5(C) :- em_rer(C,P), pendente(C).

% Regra final: deve cursar presencialmente
deve_cursar_presencial(C) :- cond1(C), pendente(C).
deve_cursar_presencial(C) :- cond2(C), pendente(C).
deve_cursar_presencial(C) :- cond3(C), pendente(C).
deve_cursar_presencial(C) :- cond4(C), pendente(C).
deve_cursar_presencial(C) :- cond5(C), pendente(C).

%! 128 | Art. 128 | RER aplica-se apenas à UC reprovada por nota
% (garantido pela regra pode_rer abaixo)

%! 129 | Art. 129 | RER não pode ser aplicado a UC prática ou vedada
% (garantido pela regra pode_rer abaixo)

%! 130 | Art. 130 | Regras para RER
% Pode RER apenas se:
%   • a UC foi reprovada por nota e ainda está pendente
%   • não há matrícula em RER para essa UC em nenhum período
%   • não há matrícula em RER para nenhuma outra UC no mesmo período
%   • a UC não é vedada nem prática
%   • há exatamente uma UC reprovada por nota no período (a própria)
pode_rer(C) :-
    reprovado_nota(C,P),
    pendente(C),
    #count{P2: em_rer(C,P2)} = 0,          % nenhuma RER para essa UC
    #count{C2: em_rer(C2,P)} = 0,          % nenhuma outra UC em RER no mesmo período
    #count{C2: reprovado_nota(C2,P), pendente(C2)} = 1,
    not rer_vedado(C),
    not uc_pratica(C).