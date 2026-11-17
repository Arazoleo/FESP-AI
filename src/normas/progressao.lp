% Progressão na matriz e planejamento contrafactual ("e se eu reprovar em X?").
%
% Carregado JUNTO com regras/res246_2023.lp: a conclusão de uma UC vem das
% normas de aprovação (Arts. 109-123) sobre o histórico, então a prova vai do
% artigo do regulamento até o semestre previsto de formatura.
%
% Entradas (além do vocabulário de estado.py), montadas por progressao.py:
%   uc_matriz(U, T)        UC U da matriz do curso, no termo T
%   uc_codigo(Cod, U)      código do histórico que corresponde à UC U
%   prereq(A, B)           A é pré-requisito de B (KG), entre UCs da matriz
%   inicio_plano(P)        primeiro período ainda planejável
% Hipóteses ("e se"):
%   hipotese_reprova(U)    a UC U, em curso, termina reprovada
%   hipotese_nao_cursa(U, P)  o(a) estudante não cursa U no período P
%   hipotese_tranca(P)     trancamento no período P (nenhuma UC)
%
% O que NÃO é norma entra como premissa, com dispositivo entre parênteses, e
% aparece na resposta como suposição: oferta anual pelo termo da matriz, UC
% em curso termina aprovada, segue a grade (não adianta UC de termo futuro), sem
% teto de UCs por semestre nem choque de horário.

%! plan_concluida | Arts. 120-123 (via histórico) | UC da matriz já concluída: aprovação derivada das normas sobre o registro do histórico.
concluida(U) :- uc_codigo(Cod, U), aprovado_alguma_vez(Cod).

%! plan_em_curso | (premissa: UC em curso termina aprovada) | UC matriculada no período atual conta como concluída, salvo hipótese de reprovação.
em_curso(U) :- uc_codigo(Cod, U), situacao(Cod, P, em_curso), periodo_atual(P).
concluida(U) :- em_curso(U), not hipotese_reprova(U).

%! plan_a_cursar | Art. 104 | Para integralizar, toda UC da matriz ainda não concluída tem de ser cursada.
a_cursar(U) :- uc_matriz(U, _), not concluida(U).

%! plan_slot | (premissa: horizonte de planejamento) | Períodos planejáveis a partir do próximo, exceto os trancados por hipótese.
slot(P) :- inicio_plano(P0), P = P0..P0 + 19, not hipotese_tranca(P).

%! plan_oferta | (premissa: oferta anual pelo termo da matriz) | A UC do termo T é ofertada no semestre de mesma paridade do termo (ímpar no 1º semestre, par no 2º).
oferta_anual(U, P) :- a_cursar(U), uc_matriz(U, T), slot(P), (P + T) \ 2 == 1.

%! plan_ideal | (premissa: segue a grade, sem adiantar UC de termo futuro) | A UC não é cursada antes do semestre ideal da turma (ingresso + termo - 1).
ofertada(U, P) :- oferta_anual(U, P), uc_matriz(U, T), ingresso(P0), P >= P0 + T - 1.

%! plan_bloqueio | Art. 104; pré-requisitos do PPC (KG) | A UC fica bloqueada no período enquanto houver pré-requisito ainda não cursado antes dele.
feita_antes(U, P) :- cursa(U, Q), slot(P), Q < P.
bloqueada(U, P, B) :- a_cursar(U), slot(P), prereq(B, U), a_cursar(B), not feita_antes(B, P).
tem_bloqueio(U, P) :- bloqueada(U, P, _).

%! plan_cursa | (premissa: sem teto de UCs por semestre nem choque de horário) | A UC é cursada no primeiro período em que é ofertada e não está bloqueada.
pronta(U, P) :- ofertada(U, P), not tem_bloqueio(U, P), not hipotese_nao_cursa(U, P).
cursa(U, P) :- pronta(U, P), not feita_antes(U, P).

%! plan_inviavel | (planejamento) | UC que não cabe no horizonte: ciclo de pré-requisitos ou falta de oferta.
planejada(U) :- cursa(U, _).
nao_planejavel(U) :- a_cursar(U), not planejada(U).

%! plan_formatura | Art. 104; Art. 160 | As UCs da matriz se completam no último período em que se cursa uma UC pendente.
tem_a_cursar :- a_cursar(_).
formatura_matriz(P) :- tem_a_cursar, P = #max { Q, U : cursa(U, Q) }, not tem_nao_planejavel.
formatura_matriz(P) :- not tem_a_cursar, periodo_atual(P).
tem_nao_planejavel :- nao_planejavel(_).

%! plan_prazo | Art. 151; Art. 145, VI | A formatura prevista estoura o prazo máximo se passar do último semestre permitido.
% semestres_restantes não conta o atual; trancamento não conta no prazo (Art. 146)
ultimo_semestre_permitido(P + R + N) :- periodo_atual(P), semestres_restantes(R),
                                        N = #count { Q : hipotese_tranca(Q) }.
estoura_prazo(P) :- formatura_matriz(P), ultimo_semestre_permitido(L), P > L.
