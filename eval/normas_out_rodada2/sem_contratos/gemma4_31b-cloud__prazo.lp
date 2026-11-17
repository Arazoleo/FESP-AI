%! prazo_base | Art. 151, I e II | Cálculo do prazo base com acréscimo por regime
prazo_base(D + (D * 50) / 100) :- integral, duracao_minima(D).
prazo_base(D + (D * 75) / 100) :- parcial, duracao_minima(D).

%! prazo_portaria | Portaria ProGrad 566/2022, Art. 27 | Acréscimo de 2 semestres para ingressos 2020-2022
bonus_portaria(2) :- ano_ingresso(A), A >= 2020, A <= 2022.
bonus_portaria(0) :- not bonus_portaria(2).

%! prazo_maximo | Art. 151 e Portaria 566/2022 | Prazo final arredondado para cima e com bônus
% O arredondamento para cima (Art. 151 § 2º) é aplicado ao cálculo do prazo base
% Como a aritmética de Clingo é inteira, simulamos o teto do acréscimo:
% Para 50%: (D + (D*50 + 99)/100). Para 75%: (D + (D*75 + 99)/100).
% Simplificando para a regra geral de arredondamento de frações: (A + B - 1) / B.

prazo_maximo(N) :- 
    integral, duracao_minima(D), 
    Base = D + (D * 50 + 99) / 100, 
    bonus_portaria(B), 
    N = Base + B.

prazo_maximo(N) :- 
    parcial, duracao_minima(D), 
    Base = D + (D * 75 + 99) / 100, 
    bonus_portaria(B), 
    N = Base + B.

%! semestres_computados | Art. 146 | Contagem de semestres excluindo trancamentos
% Um período é computado se houve matrícula e não houve trancamento regular/especial/adm
periodo_computado(P) :- 
    periodo(P), 
    not trancamento(P, _).

% O prazo começa a contar do ingresso (Art. 151 § 1º)
semestres_decorridos(S) :- 
    ingresso(P0), 
    periodo_atual(P_atual), 
    S = (P_atual - P0 + 1).

% Ajuste: O Art. 146 diz que o trancamento não é considerado para fins de integralização.
% Portanto, subtraímos os períodos trancados do tempo decorrido desde o ingresso.
trancamentos_totais(T) :- T = #count { P : trancamento(P, _) }.

semestres_restantes(R) :- 
    prazo_maximo(Max), 
    ingresso(P0), 
    periodo_atual(P_atual), 
    trancamentos_totais(T), 
    Decorridos = (P_atual - P0 + 1) - T, 
    R = Max - Decorridos.

%! risco_prazo | Art. 145, VI | Risco de cancelamento por exceder prazo máximo
risco_cancelamento(prazo_excedido) :- 
    semestres_restantes(R), 
    R < 0.

%! reprovacao_total_semestre | Art. 145, VIII | Reprovado por frequência em 100% das UCs do período
% Identifica UCs em que o aluno se matriculou no período P
matriculado_no_periodo(C, P) :- matricula(C, P).

% Conta total de UCs no período
total_ucs_periodo(P, T) :- periodo(P), T = #count { C : matriculado_no_periodo(C, P) }, T > 0.

% Conta UCs reprovadas por frequência no período
reprovados_freq_periodo(P, T) :- periodo(P), T = #count { C : matriculado_no_periodo(C, P), reprovado_frequencia(C, P) }.

% Condição de 100% de reprovação por frequência
reprovacao_total_frequencia_periodo(P) :- 
    total_ucs_periodo(P, T), 
    reprovados_freq_periodo(P, T).

%! risco_reprovacao | Art. 145, VIII | Risco por dois semestres consecutivos de reprovação total freq
risco_cancelamento(reprovacao_total_frequencia) :- 
    periodo_atual(P), 
    reprovacao_total_frequencia_periodo(P), 
    reprovacao_total_frequencia_periodo(P - 1).