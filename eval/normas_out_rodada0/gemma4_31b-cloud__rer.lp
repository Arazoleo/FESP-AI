%! rer_elegibilidade | Art. 128, 129, 130 | Define se uma UC pendente pode ser cursada em RER
pode_rer(C) :- 
    pendente(C),
    reprovado_nota(C, P),
    not uc_pratica(C),
    not rer_vedado(C),
    not ja_cursou_rer(C),
    apenas_uma_reprovacao_nota(P),
    not em_rer_outro_semestre.

%! aux_rer | Art. 130, §3 | Verifica se a UC já foi cursada em RER anteriormente
ja_cursou_rer(C) :- em_rer(C, P).

%! aux_rer | Art. 130 | Verifica se houve apenas uma reprovação por nota no período letivo
apenas_uma_reprovacao_nota(P) :- 
    periodo(P),
    #count { C : reprovado_nota(C, P) } == 1.

%! aux_rer | Art. 130, §5 | Verifica se o estudante já está em RER em outra UC no período atual
em_rer_outro_semestre :- 
    periodo_atual(P),
    em_rer(_, P).

%! presencial_freq | Art. 124, I | Presencial se reprovado por frequência em uma ou mais UCs
deve_cursar_presencial(C) :- 
    pendente(C),
    reprovado_frequencia(C, P).

%! presencial_nota | Art. 124, II | Presencial se reprovado por nota em duas ou mais UCs no mesmo período
deve_cursar_presencial(C) :- 
    pendente(C),
    reprovado_nota(C, P),
    #count { UC : reprovado_nota(UC, P) } >= 2.

%! presencial_prereq | Art. 124, III | Presencial se a UC for pré-requisito de outra
deve_cursar_presencial(C) :- 
    pendente(C),
    prereq(C, _).

%! presencial_vedado_rer | Art. 124, IV | Presencial se a UC não for passível de RER
deve_cursar_presencial(C) :- 
    pendente(C),
    uc_pratica(C).

deve_cursar_presencial(C) :- 
    pendente(C),
    rer_vedado(C).

%! presencial_rer_anterior | Art. 124, V | Presencial se a reprovação ocorreu em regime de RER
deve_cursar_presencial(C) :- 
    pendente(C),
    em_rer(C, P),
    reprovado(C, P).