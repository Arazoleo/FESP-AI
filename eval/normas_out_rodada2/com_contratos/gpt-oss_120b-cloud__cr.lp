%! conta_cr | Art. 135, 136 | UC considerada no cálculo do CR
conta_cr(C,P) :-
    matricula(C,P),
    carga(C,_),
    not excluido(C,P),
    not trancamento(P,_).

%! excluido | Art. 136 | UC excluída do cálculo do CR (aproveitamento, TCC, estágio, AC)
excluido(C,P) :-
    situacao(C,P,aproveitamento).          % aproveitamento (transferência)

excluido(C,P) :-
    natureza(C,tcc),
    matricula(C,P).                       % trabalho de conclusão de curso

excluido(C,P) :-
    natureza(C,estagio),
    matricula(C,P).                       % estágio curricular

excluido(C,P) :-
    natureza(C,ac),
    matricula(C,P).                       % atividade acadêmico‑cultural

%! nota_final10 | Art. 133 | nota final usada no cálculo (×10)
nota_final10(C,P,N) :- nota10(C,P,N).

nota_final10(C,P,N) :-
    not nota10(C,P,_),
    media10(C,P,M),
    exame10(C,P,E),
    N = (M + E + 1) / 2.          % média arredondada para cima (inteira)

nota_final10(C,P,N) :-
    not nota10(C,P,_),
    not exame10(C,P,_),
    media10(C,P,N).               % caso só exista a média preliminar

%! nota_usada10 | Art. 135 | nota considerada (zero se reprovado por frequência)
nota_usada10(C,P,0) :-                     % Art. 135, II
    conta_cr(C,P),
    reprovado_frequencia(C,P).

nota_usada10(C,P,N) :-                     % Art. 135, I e III
    conta_cr(C,P),
    not reprovado_frequencia(C,P),
    nota_final10(C,P,N).

%! cr_x1000 | Art. 134 | CR acumulado ×1000 (truncado na 3ª casa decimal)
cr_x1000(X) :-
    % soma das cargas horárias das UC consideradas
    Htotal = #sum { H,C,P : conta_cr(C,P), carga(C,H) },
    Htotal > 0,
    % soma dos produtos (nota ×10) * carga
    Sum = #sum { Pts,C,P : conta_cr(C,P), carga(C,H), nota_usada10(C,P,N), Pts = N * H },
    % CR ×1000 = floor( (Sum * 100) / Htotal )
    X = (Sum * 100) / Htotal.