"""
Vigência das normas no tempo e leituras alternativas de um dispositivo.

A Res. CONSU 246/2023 vale desde 2024/1 (Art. 170). Classificar um fato
anterior por ela é anacronismo: o motor registra e rebaixa a crença, salvo se
o registro oficial do histórico confirma. A Portaria 566/2022, Art. 27, tem
duas leituras declaradas; o motor mostra quando a resposta depende delas.

    .venv-normas/bin/python -m pytest test_vigencia.py -q
"""

import sys
from pathlib import Path

ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT / "src"))

from normas import Aluno, Cursada, Motor, periodo as P  # noqa: E402

MOTOR = Motor()


def avaliar(cursadas=(), motor=MOTOR, **kw):
    kw.setdefault("ano_ingresso", 2022)
    kw.setdefault("periodo_atual", P(2024, 2))
    kw.setdefault("duracao_minima", 8)
    return motor.avaliar(Aluno(cursadas=list(cursadas), **kw).fatos())


def atomo(r, nome, *args):
    return next(a for a in r.todos(nome) if all(str(x) == str(y) or getattr(y, "string", None) == x
                                                for x, y in zip(args, a.arguments)))


def test_reprovacao_antes_da_vigencia_e_anacronismo_sem_registro():
    r = avaliar([Cursada("a", P(2023, 1), 72, nota=4.0, freq=90)])
    rep = atomo(r, "reprovado_nota", "a", P(2023, 1))
    assert any(an["atomo"] == rep and an["inicio_rotulo"] == "2024/1" for an in r.anacronismos)
    assert r.crenca[rep] == (0.0, 1.0)
    assert "fora de vigência em 2023/1" in r.explicar(rep)


def test_registro_oficial_confirma_e_mantem_a_crenca():
    r = avaliar([Cursada("a", P(2023, 1), 72, nota=4.0, freq=90, situacao="reprovado")])
    rep = atomo(r, "reprovado_nota", "a", P(2023, 1))
    an = [a for a in r.anacronismos if a["atomo"] == rep]
    assert an and all(a["corroborado"] for a in an)
    assert r.crenca[rep] == (1.0, 1.0)


def test_fato_na_vigencia_nao_e_anacronismo():
    r = avaliar([Cursada("a", P(2024, 1), 72, nota=4.0, freq=90)])
    rep = atomo(r, "reprovado_nota", "a", P(2024, 1))
    assert not any(an["atomo"] == rep for an in r.anacronismos)
    assert r.crenca[rep] == (1.0, 1.0)


def test_direito_presente_herda_a_incerteza_do_fato_antigo():
    """O RER é pedido agora (momento atual, norma vigente), mas se apoia numa
    reprovação de 2023 classificada por norma posterior: a crença cai junto."""
    r = avaliar([Cursada("a", P(2023, 1), 72, nota=4.0, freq=90)])
    cand = atomo(r, "candidato_rer", "a")
    assert not any(an["atomo"] == cand for an in r.anacronismos)
    assert r.crenca[cand][0] == 0.0


def test_vigencia_desligada():
    r = avaliar([Cursada("a", P(2023, 1), 72, nota=4.0, freq=90)], motor=Motor(vigencia=False))
    assert r.anacronismos == []


def test_portaria_566_leituras_divergem_para_ingressante_2018():
    al = Aluno(ano_ingresso=2018, periodo_atual=P(2024, 1), duracao_minima=8)
    por = MOTOR.avaliar_leituras(al.fatos(), "port566")
    assert set(por) == {"literal", "ingressantes"}
    assert por["literal"].valor("prazo_maximo") == 14       # 12 + 2
    assert por["ingressantes"].valor("prazo_maximo") == 12
    div = Motor.divergencia(por, "prazo_maximo")
    assert div == {"literal": ["prazo_maximo(14)"], "ingressantes": ["prazo_maximo(12)"]}
    assert por["ingressantes"].leitura == {"port566": "ingressantes"}
    assert "Portaria 566/2022, Art. 27" in por["literal"].explicar("prazo_maximo(14)")


def test_portaria_566_leituras_concordam_para_ingressante_2021():
    al = Aluno(ano_ingresso=2021, periodo_atual=P(2024, 1), duracao_minima=8)
    por = MOTOR.avaliar_leituras(al.fatos(), "port566")
    assert Motor.divergencia(por, "prazo_maximo") is None


def test_leitura_padrao_e_a_literal():
    r = avaliar(ano_ingresso=2018, periodo_atual=P(2024, 1))
    assert r.leitura == {"port566": "literal"}
