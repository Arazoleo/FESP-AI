%! 104 | Art. 104 | Estudantes devem cursar todas as UC da matriz curricular com carga horária exigida.

% Carga cumprida: se houver fato horas(C, H) usamos esse valor.
horas_cumpridas(C, H) :- horas(C, H).

% Se não houver fato horas(C, _), assumimos 0, mas só para componentes exigidos.
horas_cumpridas(C, 0) :- exigido(C, _), not horas(C, _).

%! 104 | Art. 104 | Calcula a falta de horas para cada UC exigida.
% Se a carga cumprida for menor que a exigida, geramos falta(Comp, D),
% onde D é a diferença entre a exigida e a cumprida.
falta(C, D) :-
    exigido(C, H_req),
    horas_cumpridas(C, H),
    H < H_req,
    D = H_req - H.

%! 160 | Art. 160 | Estudante apto a colar grau se não houver falta de horas.
% O estudante está apto a colar grau apenas quando não há nenhuma falta registrada.
apto_colar_grau :- not falta(_, _).