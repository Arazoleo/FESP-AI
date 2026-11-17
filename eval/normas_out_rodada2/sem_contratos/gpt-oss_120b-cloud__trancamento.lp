%! art148_i | Art. 148 I | vedação ao trancamento no primeiro ano
primeiro_ano :- 
    periodo_atual(Pa), 
    ingresso(Pi), 
    D = Pa - Pi, 
    D < 2.

%! art148_ii | Art. 148 II | vedação ao trancamento se transferido no mesmo ano
transferido_mesmo_ano :- 
    transferido_no_ano(Y), 
    ano_atual(Y).

%! art148_iii | Art. 148 III | vedação ao trancamento durante processo disciplinar
% (processo_disciplinar já é um fato, basta referenciá‑lo)

%! art147_limite | Art. 147 §1 | total de trancamentos regulares não pode exceder 2 semestres
proibido_trancar_total :- 
    N = #count { P : trancamento(P, regular) },
    N >= 2.

%! art148_vedacoes | Art. 148 | conjunto de vedações ao trancamento regular
proibido_trancar :- 
    primeiro_ano
    ; transferido_mesmo_ano
    ; processo_disciplinar
    ; proibido_trancar_total.

%! pode_trancar | definição de possibilidade de solicitar trancamento regular agora
pode_trancar :- not proibido_trancar.