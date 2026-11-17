%! art146 | Art. 146 | definição do trancamento (informativa, não gera restrição)

%! art147 | Art. 147 | limite total de trancamento regular a 2 semestres (1 ano)
total_regular_trancado(N) :- N = #count { P : trancamento(P, regular) }.
pode_trancar_reg_limit :- total_regular_trancado(N), N < 2.

%! art148_i | Art. 148 I | vedação se estudante está no primeiro ano do curso
primeiro_ano_vedado :- 
    periodo_atual(P_atual), 
    ingresso(P_ingresso), 
    P_atual < P_ingresso + 2.

%! art148_ii | Art. 148 II | vedação se estudante foi transferido no mesmo ano
transferencia_vedada :- 
    ano_atual(A_atual), 
    transferido_no_ano(A_atual).

%! art148_iii | Art. 148 III | vedação se estudante responde a processo disciplinar
processo_disciplinar_vedado :- processo_disciplinar.

%! pode_trancar | Regra final | estudante pode pedir trancamento regular agora
pode_trancar :- 
    not primeiro_ano_vedado,
    not transferencia_vedada,
    not processo_disciplinar_vedado,
    pode_trancar_reg_limit.