%! art148_i | Art. 148, I | vedado se estudante está no primeiro ano do curso
proibido_primeiro_ano :-
    ingresso(P0),
    periodo_atual(Pc),
    Y0 = P0 / 2,          % ano acadêmico de ingresso
    Yc = Pc / 2,          % ano acadêmico corrente
    Y0 = Yc.

%! art148_ii | Art. 148, II | vedado se estudante foi transferido no mesmo ano corrente
proibido_transferencia :-
    transferido_no_ano(Yt),
    periodo_atual(Pc),
    Yc = Pc / 2,
    Yt = Yc.

%! art148_iii | Art. 148, III | vedado se estudante responde a processo disciplinar
proibido_disciplinar :-
    processo_disciplinar.

%! art147_limite | Art. 147, §1 | total de trancamentos regulares não pode exceder 2 semestres (1 ano)
total_trancado_regular(N) :-
    N = #count { P : trancamento(P, regular) }.

%! pode_trancar | Art. 147, §1 + Art. 148 | estudante pode pedir trancamento regular agora
pode_trancar :-
    not proibido_primeiro_ano,
    not proibido_transferencia,
    not proibido_disciplinar,
    total_trancado_regular(N),
    N < 2.