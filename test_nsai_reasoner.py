"""
Testes do raciocinador NSAI (src/nsai_reasoner.py) e das correções do KG.

Precisam do PyReason e da stack completa: rodar no container do backend.
    docker run --rm -w /app -v "$PWD:/app" fespai-backend python -m pytest test_nsai_reasoner.py -q
(~2-3 min: o programa global do PyReason é construído uma vez por módulo.)
"""

import os

import pytest

pr = pytest.importorskip("pyreason")
os.environ.setdefault("FESPAI_NSAI_REGISTRO", "/tmp/regras_nsai_teste.jsonl")

from src.knowledge_graph import KnowledgeGraph  # noqa: E402
from src import nsai_reasoner as nsai  # noqa: E402


@pytest.fixture(scope="module")
def kg():
    g = KnowledgeGraph()
    g.build_from_directories("./markdown_disciplinas", "./markdown_regimentos",
                             "./markdown_docentes", "./markdown_cursos")
    return g


@pytest.fixture(scope="module")
def r(kg):
    rac = nsai.RaciocinadorNSAI(kg).construir()
    assert rac.pronto, rac.erro
    return rac


# ── KG: resolução determinística e siglas ────────────────────────────────────

def test_prereq_resolvido_pelo_nome_nao_pelo_codigo_repetido(kg):
    # Lógica de Programação e Algoritmos em Bioinformática têm o mesmo código
    # (9394) nas fichas; o pré-requisito de LFA tem de cair na UC certa.
    lfa = kg._find_node("Linguagens Formais e Autômatos", "disciplina")
    pres = {kg.graph.nodes[u]["nome"] for u, _, d in kg.graph.in_edges(lfa, data=True)
            if d.get("relacao") == "PREREQUISITO_DE"}
    assert pres == {"Lógica de Programação", "Matemática Discreta"}


def test_lint_aponta_codigo_duplicado(kg):
    dups = kg.lint()["codigos_duplicados"]
    assert any(d.startswith("9394:") for d in dups)
    assert not any("definir" in d for d in dups)


def test_sigla_componente(kg):
    for termo in ("IHC", "ihc", "UX"):
        n = kg._find_node(termo, "disciplina")
        assert n and "Interação Humano-Computador" in kg.graph.nodes[n]["nome"]
    assert kg._find_node("LSC", "disciplina") is None   # ambígua: 3 UCs


# ── 1. crença nativa ─────────────────────────────────────────────────────────

def test_nivel():
    assert nsai.nivel(1.0) == 1.0
    assert nsai.nivel(0.44) == 0.4
    assert nsai.nivel(0.15) is None


def test_dependencia_curada_tem_crenca_1(r):
    assert r.crenca_dependencia("Matemática Discreta", "Compiladores") == 1.0


def test_dependencia_incerta_tem_no_maximo_um_palpite(r):
    incertas = [(a, b) for (a, b), v in r.dep.items() if v < 1.0]
    assert incertas
    for a, b in incertas[:200]:
        passos = r._explicar("dep", a, b, set())
        assert sum("NÃO curado" in p for p in passos) == 1, passos


# ── 2. regras aprendidas calibradas ──────────────────────────────────────────

def test_calibracao_e_inferencias(r):
    assert r.regras, "nenhuma regra minerada"
    for g in r.regras:
        assert 0 <= g["confianca_calibrada"] <= 1
        assert g["ativa"] == (g["previsoes_holdout"] >= nsai.MIN_PREDICOES
                              and g["confianca_calibrada"] >= nsai.PISO_REGRA)
    ativas = {nsai._chave_regra(g): g["confianca_calibrada"] for g in r.regras if g["ativa"]}
    for inf in r.inferidas[:100]:
        assert inf["regra"] in ativas
        assert inf["bound"][0] == pytest.approx(ativas[inf["regra"]], abs=1e-3)
        assert inf["bound"][0] < 1.0      # aprendido nunca vira fato duro


# ── 3. tempo ─────────────────────────────────────────────────────────────────

def test_projecao_respeita_prerequisitos_e_paridade(r, kg):
    p = r.projetar(["Lógica de Programação"], "Compiladores")
    quando = {d: s["semestre"] for s in p["semestres"] for d in s["disciplinas"]}
    ordem = [quando["Matemática Discreta"], quando["Linguagens Formais e Autômatos"],
             quando["Compiladores"]]
    assert ordem == sorted(ordem) and len(set(ordem)) == 3
    termos = nsai._termos(kg)
    for nome, sem in quando.items():
        par = nsai._paridade(termos[kg._find_node(nome, "disciplina")])
        if par is not None:
            assert int(sem.split("/")[1]) == par, (nome, sem)
    assert p["alvo_concluido_em"] == quando["Compiladores"]


def test_projecao_considera_prerequisitos_implicitos(r):
    p = r.projetar(["Linguagens Formais e Autômatos"], "Compiladores")
    assert set(p["implicitas"]) == {"Lógica de Programação", "Matemática Discreta"}
    assert [d for s in p["semestres"] for d in s["disciplinas"]] == ["Compiladores"]


def test_projecao_alvo_inexistente(r):
    assert r.projetar([], "Disciplina Que Não Existe XYZ") is None


# ── 4. prova ─────────────────────────────────────────────────────────────────

def test_prova_cadeia_curada(r):
    passos = r.explicar_dependencia("Matemática Discreta", "Compiladores")
    assert len(passos) == 2
    assert "Linguagens Formais e Autômatos" in passos[0] and "curado" in passos[0]


# ── 5. inconsistência entre fontes ───────────────────────────────────────────

def test_inconsistencias_de_oferta_ficam_em_aberto(r):
    ofertas = [i for i in r.inconsistencias if i["tipo"] == "oferta"]
    for i in ofertas:
        assert i["bound_final"] == [0.0, 1.0]          # nenhuma fonte venceu
        assert len(i["fontes"]) == 2
        assert "Conflicting bounds" in i["pyreason"]


def test_fato_static_esconderia_o_conflito():
    import networkx as nx

    def rodar(static):
        pr.reset(); pr.reset_rules(); pr.reset_settings()
        pr.settings.verbose = False
        pr.settings.atom_trace = True
        pr.settings.persistent = True
        g = nx.DiGraph(); g.add_node("u")
        pr.load_graph(g)
        pr.add_fact(pr.Fact("ofertada(u)", "matriz", 0, 0, static=static))
        pr.add_fact(pr.Fact("ofertada(u):[0,0]", "agenda", 0, 0, static=static))
        pr.add_rule(pr.Rule("nada2(x) <-0 nada(x)", "dummy"))
        it = pr.reason(timesteps=1)
        return [list(d.to_dict("records")[0]["ofertada"]) for d in pr.filter_and_sort_nodes(it, ["ofertada"])][-1]

    with nsai.PYREASON_LOCK:
        assert rodar(True) == [0.0, 0.0]       # a última fonte vence em silêncio
        assert rodar(False) == [0.0, 1.0]      # conflito detectado: fica em aberto


def test_impressao_estavel_entre_reconstrucoes(kg):
    g2 = KnowledgeGraph()
    g2.build_from_directories("./markdown_disciplinas", "./markdown_regimentos",
                              "./markdown_docentes", "./markdown_cursos")
    assert nsai.impressao(g2) == nsai.impressao(kg)
