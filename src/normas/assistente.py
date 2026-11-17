"""
Ponte entre o chat e o planejamento contrafactual com prova.

`responder_e_se` decide se a pergunta "e se eu reprovar em X?" se aplica (X
aterrado no KG e na matriz do curso) e monta a resposta determinística. Com o
histórico da sessão a previsão é do(a) aluno(a); sem ele, é a de quem está em
dia com a grade e cursa X no termo dela, e a resposta diz isso.
"""

from __future__ import annotations

from typing import Dict, List, Optional

from .estado import Aluno, Cursada, aluno_de_historico, periodo_hoje
from . import contrato, progressao as pg

_MOTOR = None
_MATRIZES: Dict = {}


def _motor():
    global _MOTOR
    if _MOTOR is None:
        _MOTOR = pg.motor_planejamento()
    return _MOTOR


def _matriz(kg, curso: str) -> Optional[pg.Matriz]:
    chave = (id(kg), curso)
    if chave not in _MATRIZES:
        _MATRIZES[chave] = pg.matriz_do_kg(kg, curso)
    return _MATRIZES[chave]


def _aluno_em_dia(mat: pg.Matriz, uc: str, atual: int) -> Aluno:
    """Quem está em dia: cursa agora o termo da UC, aprovado(a) nos anteriores."""
    t = mat.termo[uc]
    p0 = atual - (t - 1)
    cursadas = [Cursada(u, p0 + tu - 1, 72, nota=7.0, freq=90, situacao="aprovado")
                for u, tu in mat.termo.items() if tu < t]
    cursadas += [Cursada(u, atual, 72, situacao="em_curso")
                 for u, tu in mat.termo.items() if tu == t]
    return Aluno(ano_ingresso=p0 // 2, semestre_ingresso=p0 % 2 + 1, periodo_atual=atual,
                 duracao_minima=max(mat.termo.values()), cursadas=cursadas)


def _aluno_da_sessao(kg, mat: pg.Matriz, hist: Dict, atual: int):
    aluno = aluno_de_historico(hist, periodo_atual=atual,
                               duracao_minima=max(mat.termo.values()))
    vinculo = pg.vincular_historico(kg, mat, hist)
    # UCs que o(a) aluno(a) declarou cursar agora (conversa) entram em curso
    for d in hist.get("cursando") or []:
        nome = d.get("nome") if isinstance(d, dict) else str(d)
        uid = kg._normalize_text(nome or "")
        if uid in mat.termo and uid not in vinculo.values():
            aluno.cursadas.append(Cursada(uid, atual, 72, situacao="em_curso"))
            vinculo[uid] = uid
    return aluno, vinculo


CURSOS = ("BCT", "BCC", "BMC", "EC", "EB", "EM", "BBT")


def cursos_com_uc(kg, nome_uc: str) -> List[str]:
    """Cursos cuja matriz (UCs fixas) contém a UC."""
    uid = kg._normalize_text(nome_uc)
    return [c for c in CURSOS if (m := _matriz(kg, c)) and uid in m.termo]


def responder_e_se(kg, pergunta: str, curso: str, hist: Optional[Dict] = None,
                   atual: Optional[int] = None) -> Optional[Dict]:
    """{"texto", "afirmacoes", "personalizado"} ou None se não se aplica.
    Sem curso: se a UC é fixa de um curso só, usa esse; se de vários, devolve
    {"texto", "opcoes"} pedindo o curso (o chat mostra as opções clicáveis)."""
    if kg is None:
        return None
    discs: List[str] = kg.disciplinas_mencionadas(pergunta)
    if not discs:
        return None
    if not curso:
        cursos = cursos_com_uc(kg, discs[0])
        if not cursos:
            return None
        if len(cursos) > 1:
            return {"texto": (f"{discs[0]} está na matriz de mais de um curso "
                              f"({', '.join(cursos)}), e o efeito de reprovar depende da "
                              f"grade. Em qual curso você está? (Ou envie seu histórico.)"),
                    "opcoes": [f"{pergunta.rstrip('?. ')} no {c}?" for c in cursos[:3]],
                    "afirmacoes": {}, "personalizado": False}
        curso = cursos[0]
    mat = _matriz(kg, curso)
    if not mat:
        return None
    alvo = next((kg._normalize_text(d) for d in discs if kg._normalize_text(d) in mat.termo), None)
    if alvo is None:
        return None
    atual = atual or periodo_hoje()
    personalizado = bool(hist and hist.get("disciplinas"))
    if personalizado:
        aluno, vinculo = _aluno_da_sessao(kg, mat, hist, atual)
    else:
        aluno, vinculo = _aluno_em_dia(mat, alvo, atual), {u: u for u in mat.termo}
    motor = _motor()
    fatos = pg.fatos_plano(aluno, mat, vinculo)
    base = pg.planejar(motor, fatos)
    cf = pg.e_se_reprovar(motor, fatos, base, mat, alvo)
    out = pg.responder_e_se(cf, mat)
    texto, diag = contrato.responder(out["afirmacoes"], out["texto"])
    cabeca = (f"**Previsão pelo seu histórico** (matriz de {curso}):" if personalizado else
              f"**Para quem está em dia com a grade de {curso}** e cursa "
              f"{mat.nome[alvo]} agora (termo {mat.termo[alvo]}). Envie seu histórico "
              f"para uma previsão sua:")
    rodape = ("\n\n_Regras da reprovação em si (exame, RER, frequência): Res. CONSU "
              "246/2023, Arts. 109-130. Previsão derivada das normas e da matriz no grafo, "
              "com as suposições acima._")
    return {"texto": f"{cabeca}\n\n{texto}{rodape}", "afirmacoes": out["afirmacoes"],
            "personalizado": personalizado, "contrato": diag}
