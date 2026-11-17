%! cr_consideracao | Art. 136 | UCs que NÃO devem ser incluídas no cálculo do CR
considerada(C,P) :-
    matricula(C,P),
    periodo_atual(Pa),
    P <= Pa,
    not trancamento(P,_),                     % I – trancamento de matrícula
    not situacao(C,P,cancelado),              % II – cancelamento de matrícula (se houver registro)
    not situacao(C,P,aproveitamento),        % III – aproveitamento de outra instituição
    not natureza(C,tcc),                      % IV – TCC
    not natureza(C,estagio),                 % IV – estágio
    not natureza(C,ac).                       % IV – atividade acadêmico‑cultural

%! cr_nota_efetiva | Art. 135 | Definição da nota a ser usada no cálculo
% Caso a UC esteja em Regime Especial de Recuperação (RER), a nota oficial é mantida
nota_efetiva(C,P,N) :-
    considerada(C,P),
    em_rer(C,P),
    nota10(C,P,N).

% Se a UC não está em RER e o estudante foi reprovado por frequência, a nota vale 0
nota_efetiva(C,P,0) :-
    considerada(C,P),
    not em_rer(C,P),
    reprovado_frequencia(C,P).

% Caso contrário, a nota efetiva é a nota final registrada
nota_efetiva(C,P,N) :-
    considerada(C,P),
    not em_rer(C,P),
    not reprovado_frequencia(C,P),
    nota10(C,P,N).

%! cr_somas | Art. 134 | Soma dos produtos nota×carga e soma das cargas
soma_nota_carga(S) :-
    S = #sum { N*H : C,P,N,H,
               nota_efetiva(C,P,N),
               carga(C,H) }.

soma_carga(T) :-
    T = #sum { H : C,P,H,
               considerada(C,P),
               carga(C,H) }.

%! cr_resultado | Art. 134 | Cálculo do CR acumulado ×1000 (truncado)
cr_x1000(CR) :-
    soma_nota_carga(S),
    soma_carga(T),
    T > 0,
    CR = (S * 100) / T.   % divisão inteira (trunca) → CR ×1000