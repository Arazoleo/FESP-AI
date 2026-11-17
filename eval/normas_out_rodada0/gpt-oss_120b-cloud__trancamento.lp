%! art146 | Art. 146 | definição do trancamento (informativa, não gera restrição)

%! art147_limite | Art. 147 | limite total de trancamento regular (máx 2 semestres)
trancamento_regular_usado(N) :- N = #count { P : trancamento(P, regular) }.
pode_usar_trancamento_regular :- trancamento_regular_usado(N), N < 2.

%! art148_i | Art. 148 I | vedação se estiver no primeiro ano do curso
primeiro_ano :- 
    ingresso(P0),
    periodo_atual(Pa),
    Semestres = Pa - P0,
    Semestres < 2.

%! art148_ii | Art. 148 II | vedação se foi transferido no mesmo ano civil
transferido_no_ano_atual :- 
    ano_atual(A),
    transferido_no_ano(A).

%! art148_iii | Art. 148 III | vedação se houver processo disciplinar
em_processo_disciplinar :- processo_disciplinar.

%! art148_vedacoes | Art. 148 | conjunto de vedações ao trancamento regular
vedado_art148 :- primeiro_ano.
vedado_art148 :- transferido_no_ano_atual.
vedado_art148 :- em_processo_disciplinar.

%! pode_trancar | Art. 147 e Art. 148 | decisão final se o estudante pode pedir trancamento regular agora
pode_trancar :- 
    pode_usar_trancamento_regular,
    not vedado_art148.