%! 124 | Art. 124 | O estudante deve cursar presencialmente se reprovado por frequência, por nota em duas ou mais UCs, se for pré-requisito, se não for elegível para RER, ou se em RER (mas RER não exige presença). 

% I – reprovado por frequência
deve_cursar_presencial(C) :-
    reprovado_frequencia(C,P),
    pendente(C),
    not em_rer(C,P).

% II – reprovado por nota em duas ou mais UCs no mesmo período
deve_cursar_presencial(C) :-
    reprovado_nota(C,P),
    pendente(C),
    #count{C1 : reprovado_nota(C1,P)} >= 2,
    not em_rer(C,P).

% III – UC que é pré-requisito de outra
deve_cursar_presencial(C) :-
    reprovado(C,P),
    pendente(C),
    prereq(C,_),
    not em_rer(C,P).

% IV – UC não passível de RER (práticas ou vedadas)
deve_cursar_presencial(C) :-
    reprovado(C,P),
    pendente(C),
    uc_pratica(C),
    not em_rer(C,P).

deve_cursar_presencial(C) :-
    reprovado(C,P),
    pendente(C),
    rer_vedado(C),
    not em_rer(C,P).

%! 128 | Art. 128 | RER aplica-se apenas à UC em que o estudante foi reprovado por nota.
%! 129 | Art. 129 | RER só pode ser aplicado a UCs que não sejam práticas e que a comissão permita.
%! 130 | Art. 130 | RER pode ser aplicado apenas uma vez por UC, uma vez por semestre, e não impede progressão.

pode_rer(C) :-
    reprovado_nota(C,P),
    pendente(C),
    not uc_pratica(C),
    not rer_vedado(C),
    not em_rer(C,_),          % UC não já em RER em nenhum período
    #count{C1 : em_rer(C1,P)} = 0,   % Nenhuma outra UC em RER no mesmo período
    not em_rer(C,P).           % UC não atualmente em RER (redundante, mas explícito).