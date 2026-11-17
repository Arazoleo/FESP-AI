"""
Testes do planejamento contrafactual com prova (src/normas/progressao.py).

Matriz sintética pequena (resultado conferível à mão) + um caso com a matriz
real do BCC vinda do KG. Executa sem Ollama:

    .venv-normas/bin/python -m pytest test_progressao.py -q
"""

import importlib.util
import os
import sys
import types
from pathlib import Path

import pytest

ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT / "src"))

from normas import Aluno, Cursada, periodo as P, rotulo_periodo  # noqa: E402
from normas import progressao as pg  # noqa: E402

MOTOR = pg.motor_planejamento()

# A(t1) -> B(t2) -> C(t3); D(t4) sem pré-requisito. Curso de 4 termos.
MATRIZ = pg.Matriz("TESTE", {"a": 1, "b": 2, "c": 3, "d": 4},
                   {"a": "A", "b": "B", "c": "C", "d": "D"},
                   [("a", "b"), ("b", "c")])
VINCULO = {"a": "a", "b": "b", "c": "c", "d": "d"}


def aluno(cursadas, **kw):
    kw.setdefault("ano_ingresso", 2024)
    kw.setdefault("periodo_atual", P(2024, 2))
    kw.setdefault("duracao_minima", 4)
    return Aluno(cursadas=cursadas, **kw)


def no_trilho(**kw):
    """A aprovada em 2024/1, B em curso em 2024/2."""
    return aluno([Cursada("a", P(2024, 1), 72, nota=7.0, freq=90, situacao="aprovado"),
                  Cursada("b", P(2024, 2), 72, situacao="em_curso")], **kw)


def plano(al, hip=()):
    fatos = pg.fatos_plano(al, MATRIZ, VINCULO)
    return fatos, pg.planejar(MOTOR, fatos + list(hip))


def test_plano_base_segue_a_grade():
    _, p = plano(no_trilho())
    assert p.cursa == {"c": P(2025, 1), "d": P(2025, 2)}
    assert p.formatura == P(2025, 2)
    assert not p.nao_planejavel


def test_reprovar_em_curso_atrasa_pela_oferta_anual_e_explica_a_cadeia():
    fatos, base = plano(no_trilho())
    cf = pg.e_se_reprovar(MOTOR, fatos, base, MATRIZ, "b")
    assert cf.efeito == "atrasa" and cf.atraso == 1
    assert cf.hipotese.cursa["b"] == P(2025, 2)        # termo 2: só no 2º semestre
    assert cf.hipotese.cursa["c"] == P(2026, 1)
    cadeia = pg.cadeia_critica(cf.hipotese, MATRIZ)
    assert [(u, m) for u, _, m, _ in cadeia] == [("c", "prereq"), ("b", "reprova_em_curso")]
    texto = pg.responder_e_se(cf, MATRIZ)["texto"]
    assert "2025/2 para 2026/1" in texto and "C (2026/1) depende de B" in texto


def test_reprovar_uc_futura_sem_dependentes():
    fatos, base = plano(no_trilho())
    cf = pg.e_se_reprovar(MOTOR, fatos, base, MATRIZ, "d")
    assert cf.atraso == 2                               # próxima oferta do termo 4: +1 ano
    assert pg.cadeia_critica(cf.hipotese, MATRIZ)[0][2] == "hipotese"


def test_uc_ja_concluida_nao_se_aplica():
    fatos, base = plano(no_trilho())
    assert pg.e_se_reprovar(MOTOR, fatos, base, MATRIZ, "a").efeito == "ja_concluida"


def test_reprovacao_antiga_sem_registro_gera_aviso():
    al = aluno([Cursada("a", P(2023, 2), 72, nota=4.0, freq=90)],
               ano_ingresso=2023, periodo_atual=P(2024, 2))
    fatos, base = plano(al)
    cf = pg.e_se_reprovar(MOTOR, fatos, base, MATRIZ, "b")
    out = pg.responder_e_se(cf, MATRIZ)
    assert out["afirmacoes"]["anacronismos"] == ["2023/2"]
    assert "anteriores à Res. 246/2023" in out["texto"]


def test_reprovacao_do_historico_vem_das_normas():
    """Nota 9,5 com 70% de frequência: o Art. 120 § 2º reprova, então A
    volta a ser pendente e o plano inteiro escorrega."""
    al = aluno([Cursada("a", P(2024, 1), 72, nota=9.5, freq=70, situacao="reprovado")])
    _, p = plano(al)
    r = p.resultado
    assert r.tem("a_cursar", "a")
    assert p.cursa["a"] == P(2025, 1) and p.cursa["b"] == P(2025, 2)
    assert p.formatura == P(2026, 1)
    prova = r.explicar(r.todos("a_cursar")[0])
    assert "Art. 104" in prova
    alvo = next(a for a in r.todos("reprovado") if a.arguments[0].string == "a")
    assert "Art. 120, § 2º" in r.explicar(alvo)


def test_trancamento_hipotetico_empurra_o_que_cairia_no_periodo():
    fatos, base = plano(no_trilho())
    h = pg.planejar(MOTOR, fatos + [f"hipotese_tranca({P(2025, 1)})"])
    assert h.cursa["c"] == P(2026, 1) and h.formatura == P(2026, 1)


def test_estoura_prazo_maximo():
    # duração mínima 2 → prazo 3 semestres (Art. 151, I); a matriz pede 4
    _, p = plano(no_trilho(duracao_minima=2))
    assert p.estoura_prazo


def test_premissas_aparecem_na_resposta():
    fatos, base = plano(no_trilho())
    cf = pg.e_se_reprovar(MOTOR, fatos, base, MATRIZ, "b")
    out = pg.responder_e_se(cf, MATRIZ)
    assert "oferta anual pelo termo da matriz" in out["afirmacoes"]["premissas"]
    assert "Supondo:" in out["texto"]


def test_folgas_identificam_ucs_criticas():
    fatos, base = plano(no_trilho())
    f = pg.folgas(MOTOR, fatos, base)
    assert f == {"c": 1, "d": 2}       # C escorrega 1 ano mas D já fecha em 2025/2


@pytest.fixture(scope="module")
def kg():
    os.chdir(ROOT)
    if "src" not in sys.modules:
        pkg = types.ModuleType("src")
        pkg.__path__ = [str(ROOT / "src")]
        sys.modules["src"] = pkg
    spec = importlib.util.spec_from_file_location("src.knowledge_graph",
                                                  ROOT / "src/knowledge_graph.py")
    mod = importlib.util.module_from_spec(spec)
    mod.__package__ = "src"
    sys.modules["src.knowledge_graph"] = mod
    spec.loader.exec_module(mod)
    g = mod.KnowledgeGraph()
    g.build_from_directories(disciplinas_dir="./markdown_disciplinas",
                             regimentos_dir="./markdown_regimentos",
                             docentes_dir="./markdown_docentes",
                             cursos_dir="./markdown_cursos")
    return g


def test_bcc_real_matematica_discreta_cascata(kg):
    """Matriz real do BCC: reprovar MD (termo 2, em curso em 2025/2) empurra
    Linguagens Formais e Compiladores, mas não a formatura (o TCC II fecha)."""
    mat = pg.matriz_do_kg(kg, "BCC")
    md = "matematica discreta"
    assert md in mat.termo and ("matematica discreta", "linguagens formais automatos") in mat.prereqs
    cur = [Cursada(u, P(2024, 1) + t - 1, 72, nota=7.0, freq=90, situacao="aprovado")
           for u, t in mat.termo.items() if t <= 3 and u != md]
    cur.append(Cursada(md, P(2025, 2), 72, situacao="em_curso"))
    al = Aluno(ano_ingresso=2024, periodo_atual=P(2025, 2), duracao_minima=8, cursadas=cur)
    fatos = pg.fatos_plano(al, mat, {u: u for u in mat.termo})
    base = pg.planejar(MOTOR, fatos)
    cf = pg.e_se_reprovar(MOTOR, fatos, base, mat, md)
    out = pg.responder_e_se(cf, mat)
    mudam = {u for u, _, _ in out["afirmacoes"]["cascata"]}
    assert "Linguagens Formais e Autômatos" in mudam and "Compiladores" in mudam
    assert rotulo_periodo(base.formatura) == "2027/2"


# ------------------------------------------------- contrato de resposta (C)

from normas import contrato  # noqa: E402


def _cf_b():
    fatos, base = plano(no_trilho())
    cf = pg.e_se_reprovar(MOTOR, fatos, base, MATRIZ, "b")
    return pg.responder_e_se(cf, MATRIZ)


def test_texto_deterministico_satisfaz_o_proprio_contrato():
    out = _cf_b()
    assert contrato.verificar(out["afirmacoes"], out["texto"]) == {"ok": True, "violacoes": []}


def test_reescrita_fiel_e_aceita():
    out = _cf_b()
    fiel = ("Se você reprovar em B, sua conclusão das obrigatórias vai de 2025/2 para 2026/1, "
            "um atraso de 1 semestre, porque C depende de B. Supondo oferta anual pela matriz.")
    texto, diag = contrato.responder(out["afirmacoes"], out["texto"], lambda _t: fiel)
    assert texto == fiel and diag["reescrita"]


def test_reescrita_com_periodo_inventado_volta_ao_deterministico():
    out = _cf_b()
    errada = ("Se reprovar em B você só termina em 2026/2, atraso de 2 semestres. "
              "Supondo oferta anual.")
    texto, diag = contrato.responder(out["afirmacoes"], out["texto"], lambda _t: errada)
    assert texto == out["texto"] and not diag["ok"]
    assert "período sem prova: 2026/2" in diag["violacoes"]
    assert "número de semestres sem prova: 2" in diag["violacoes"]


def test_reescrita_que_some_com_as_suposicoes_e_rejeitada():
    out = _cf_b()
    sem = "Se reprovar em B, você passa de 2025/2 para 2026/1: atraso de 1 semestre."
    _, diag = contrato.responder(out["afirmacoes"], out["texto"], lambda _t: sem)
    assert diag["violacoes"] == ["omitiu as suposições"]


# --------------------------------------- ponte com o chat (assistente.py)

from normas import assistente  # noqa: E402

FIXTURE_HIST = """Curso: INTERDISCIPLINAR EM CIÊNCIA E TECNOLOGIA - INTEGRAL
Situação Acadêmica: EM CURSO Coeficiente de Rendimento (CR) Geral: 6.6
ANO/SEM | 2023/1 Coeficiente de Rendimento (CR): 7.5
Unidade Curricular Cod.
Grupo Tipo UC CH CHEXT Crédito Freq.
(%) Conceito Situação
9394 - LÓGICA DE PROGRAMAÇÃO
Docente: FULANA DE TAL Titulação: Doutorado 121 DF 72 - 4 94 8,0 APROVADO
ANO/SEM | 2023/2 Coeficiente de Rendimento (CR): 4.8
2832 - ALGORITMOS E ESTRUTURAS DE DADOS I
Docente: CICLANA SOUZA Titulação: Doutorado 121 DF 72 - 4 97 4,8 REPROVADO
RESUMO
Totais de carga horária por tipo de UC
FIXAS 72
Total de horas cumpridas pelo estudante (teórica + prática) 72
"""


def test_assistente_sem_historico_responde_para_quem_esta_em_dia(kg):
    # em dia, MD (termo 2) refeita em 2026/2 ainda chega antes de LFA (termo 5)
    out = assistente.responder_e_se(kg, "se eu reprovar em matemática discreta quanto atraso?",
                                    "BCC", None, atual=P(2025, 2))
    assert out and not out["personalizado"]
    assert "em dia com a grade de BCC" in out["texto"] and out["contrato"]["ok"]
    assert out["afirmacoes"]["efeito"] == "nao_atrasa"
    # ...mas Projeto e Análise de Algoritmos (MD é pré-requisito) escorrega um ano
    assert ("Projeto e Análise de Algoritmos", "2026/2", "2027/2") in out["afirmacoes"]["cascata"]
    # AED I (termo 2) segura AED II (termo 3) e quem depende dela: cascata
    out = assistente.responder_e_se(kg, "se eu reprovar em algoritmos e estruturas de dados i?",
                                    "BCC", None, atual=P(2025, 2))
    mudam = {u for u, _, _ in out["afirmacoes"]["cascata"]}
    assert "Algoritmos e Estruturas de Dados II" in mudam


def test_assistente_com_historico_da_sessao(kg):
    spec = importlib.util.spec_from_file_location("historico_t", ROOT / "src/historico.py")
    h = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(h)
    dados = h.parsear_historico(FIXTURE_HIST)
    out = assistente.responder_e_se(
        kg, "e se eu reprovar de novo em algoritmos e estruturas de dados i?", "BCC",
        dados, atual=P(2024, 1))
    assert out and out["personalizado"]
    af = out["afirmacoes"]
    assert af["uc"] == "Algoritmos e Estruturas de Dados I" and af["efeito"] == "atrasa"
    # reprovação de 2023/2 é anterior à Res. 246, mas o histórico confirma: sem
    # aviso (o CR de 2023 também é anacrônico, mas não mexe no plano)
    assert "anacronismos" not in af


def test_assistente_nao_se_aplica_sem_uc_da_matriz(kg):
    assert assistente.responder_e_se(kg, "se eu reprovar quanto atraso?", "BCC", None) is None
    # sem curso: Teoria dos Grafos só é fixa do BCC → usa o BCC
    out = assistente.responder_e_se(kg, "se eu reprovar em teoria dos grafos?", "", None)
    assert out and "grade de BCC" in out["texto"]
    # Compiladores é fixa do BCC e da EC → pergunta o curso
    out = assistente.responder_e_se(kg, "se eu reprovar em compiladores?", "", None)
    assert out["opcoes"] == ["se eu reprovar em compiladores no BCC?",
                             "se eu reprovar em compiladores no EC?"]
    # UC fixa de vários cursos → pergunta o curso com opções
    out = assistente.responder_e_se(kg, "se eu reprovar em lógica de programação?", "", None)
    assert out and out.get("opcoes") and "Em qual curso" in out["texto"]
    # AED I não é UC fixa do BCT: não inventa previsão, segue o fluxo normal
    assert assistente.responder_e_se(kg, "se eu reprovar em algoritmos e estruturas de dados i?",
                                     "BCT", None) is None
