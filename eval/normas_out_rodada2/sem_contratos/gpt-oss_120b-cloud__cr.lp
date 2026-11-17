%! effective_note | Art. 135 | nota efetiva: 0 se reprovado por frequência, senão nota registrada; RER usa a nota registrada
effective_note10(C,P,N) :- em_rer(C,P), nota10(C,P,N).
effective_note10(C,P,0) :- reprovado_frequencia(C,P), not em_rer(C,P).
effective_note10(C,P,N) :- nota10(C,P,N), not reprovado_frequencia(C,P), not em_rer(C,P).

%! excluido_uc | Art. 136 | condições que excluem a UC do cálculo do CR (todas precisam de C e P)
excluido(C,P) :- situacao(C,P,aproveitamento).          % aproveitamento (transferência)
excluido(C,P) :- situacao(C,P,cancelado).              % cancelamento da UC (se houver)
excluido(C,P) :- matricula(C,P), natureza(C,tcc).       % trabalho de conclusão de curso
excluido(C,P) :- matricula(C,P), natureza(C,estagio).   % estágio curricular
excluido(C,P) :- matricula(C,P), natureza(C,ac).        % atividade acadêmico‑cultural
excluido(C,P) :- matricula(C,P), trancamento(P,_).      % trancamento de matrícula no período

%! uc_valida | Art. 136 | UC válida para o cálculo do CR
valid_uc(C,P) :- matricula(C,P), carga(C,_), not excluido(C,P).

%! total_nh | Art. 134 | soma dos produtos (nota×10)·carga
total_nh(NH) :-
    NH = #sum{Prod : 
                valid_uc(C,P),
                effective_note10(C,P,N10),
                carga(C,H),
                Prod = N10 * H}.

%! total_h | Art. 134 | soma das cargas horárias das UC válidas
total_h(Hsum) :-
    Hsum = #sum{H : valid_uc(C,P), carga(C,H)}.

%! cr_acumulado | Art. 134 | cálculo do CR acumulado ×1000 (três casas decimais, truncado)
cr_x1000(X) :-
    total_h(H), H > 0,
    total_nh(NH),
    X = (NH * 100) / H.