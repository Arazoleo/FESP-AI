% Helper: current year from ano_atual
current_year(A) :- ano_atual(A).

%! art146 | Art. 146 | Trancamento suspende atividades acadêmicas, não considerado para integralização
% (Nenhuma regra explícita necessária para este dispositivo no contexto atual)

%! art147 | Art. 147 | Trancamento regular: até 2 semestres, total <= 1 ano, não fracionado
regular_trancamento_count(N) :- N = #count { P : trancamento(P,regular) }.

%! art148 | Art. 148 | Vedações ao trancamento
first_year :- current_year(1).
transferred_same_year :- transferido_no_ano(A), current_year(A).

%! art149 | Art. 149 | Trancamento especial: permitido, não conta para integralização
% (Nenhuma regra explícita necessária para este dispositivo no contexto atual)

%! art150 | Art. 150 | Trancamento administrativo: pode ser aplicado mesmo após regular
% (Nenhuma regra explícita necessária para este dispositivo no contexto atual)

%! art148 | Art. 148 | Condição para solicitar trancamento regular
pode_trancar :- not first_year,
                not transferred_same_year,
                not processo_disciplinar,
                regular_trancamento_count(N),
                N < 2.