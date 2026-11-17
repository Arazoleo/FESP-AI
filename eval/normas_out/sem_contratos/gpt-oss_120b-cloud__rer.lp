%! p124_i | Art. 124, I | Falha por frequência em alguma UC pendente
cond_i(C) :- pendente(C), reprovado_frequencia(C,_).

%! p124_ii | Art. 124, II | Falha por nota em duas ou mais UCs pendentes
cond_ii(C) :- pendente(C),
             reprovado_nota(C,_),
             reprovado_nota(D,_),
             D != C.

%! p124_iii | Art. 124, III | UC pendente que é pré‑requisito de outra UC
cond_iii(C) :- pendente(C), prereq(C,_).

%! p124_iv | Art. 124, IV | UC pendente não passível de RER
cond_iv(C) :- pendente(C), not pode_rer(C).

%! p124_v | Art. 124, V | UC pendente já em regime especial de recuperação
cond_v(C) :- pendente(C), em_rer(C,_).

%! p124_pres | Art. 124 | Determina a obrigatoriedade de presencial
deve_cursar_presencial(C) :- cond_i(C).
deve_cursar_presencial(C) :- cond_ii(C).
deve_cursar_presencial(C) :- cond_iii(C).
deve_cursar_presencial(C) :- cond_iv(C).
deve_cursar_presencial(C) :- cond_v(C).

%! p128 | Art. 128 | RER só se a reprovação foi por nota
% (já incorporado em can_be_rer/1)

%! p129 | Art. 129 | Exclui UCs práticas ou vedadas pela comissão
can_be_rer(C) :-
    pendente(C),
    reprovado_nota(C,_),          % reprovação exclusivamente por nota
    not uc_pratica(C),            % não pode ser exclusivamente prática
    not rer_vedado(C),            % não vedada pela comissão
    not em_rer(C,_).              % ainda não está em RER

%! p130_5 | Art. 130, §5 | Só um RER por semestre
outra_rer(C) :-
    can_be_rer(C),                % C é candidato a RER
    em_rer(D, P),                 % alguma outra UC já em RER
    periodo_atual(P),
    D != C.

%! p130_3 | Art. 130, §3 | UC pode ser cursada em RER apenas uma vez
% (garantido por a negação de em_rer(C,_) em can_be_rer/1)

%! p_rer_out | Predicado de saída – elegibilidade ao RER
pode_rer(C) :- can_be_rer(C), not outra_rer(C).