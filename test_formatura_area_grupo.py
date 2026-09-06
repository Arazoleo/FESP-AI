"""
Testes de regressão das capacidades adicionadas em set/2026:

1. Orientação de FORMATURA para os 7 cursos (detecção ampla de intenção de
   integralização + grounding do curso + resposta com os critérios oficiais).
2. Ponte APRENDIDA conceito→área (NSAI): materialização de PERTENCE_A no KG e a
   consulta disciplinas_da_area (com casamento insensível a acento).
3. Contato/disciplinas de GRUPO de docentes (anáfora "eles" sobre a lista já
   aterrada): grounding decide grupo × docente nomeado; iteração no grafo.

Sem Ollama: usa o KG dos markdowns e monkeypatch da intenção semântica.
"""

import sys
import importlib.util
import types as _types
from pathlib import Path

ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT))


def _bootstrap_src_package():
    if "src" not in sys.modules:
        pkg = _types.ModuleType("src")
        pkg.__path__ = [str(ROOT / "src")]
        pkg.__package__ = "src"
        pkg.__spec__ = importlib.util.spec_from_file_location(
            "src", ROOT / "src/__init__.py",
            submodule_search_locations=[str(ROOT / "src")],
        )
        sys.modules["src"] = pkg


def _import_module(name: str, path: str):
    _bootstrap_src_package()
    full = f"src.{name}"
    spec = importlib.util.spec_from_file_location(full, ROOT / path)
    mod = importlib.util.module_from_spec(spec)
    mod.__package__ = "src"
    sys.modules[full] = mod
    spec.loader.exec_module(mod)
    return mod


GREEN, RED, BOLD, RESET = "\033[92m", "\033[91m", "\033[1m", "\033[0m"
_passed, _failed = 0, 0


def check(desc, cond, detail=""):
    global _passed, _failed
    if cond:
        _passed += 1
        print(f"{GREEN}✓{RESET} {desc}")
    else:
        _failed += 1
        print(f"{RED}✗ {desc}{RESET}" + (f" - {detail}" if detail else ""))


kg_mod = _import_module("knowledge_graph", "src/knowledge_graph.py")
progresso = _import_module("progresso", "src/progresso.py")
contatos = _import_module("contatos_docentes", "src/contatos_docentes.py")

kg = kg_mod.KnowledgeGraph()
kg.build_from_directories(
    disciplinas_dir="./markdown_disciplinas",
    regimentos_dir="./markdown_regimentos",
    docentes_dir="./markdown_docentes",
    cursos_dir="./markdown_cursos",
)

# ── 1. Orientação de formatura (7 cursos) ────────────────────────────────────
print(f"\n{BOLD}── formatura: detecção de intenção (natural/informal) ──{RESET}")
FORMATURA = [
    "to me formando em ciencia da computacao, o que preciso pra colar grau?",
    "quais os requisitos pra me formar em engenharia de computacao?",
    "como faco pra concluir o curso de biotecnologia?",
    "quais as exigencias pra formatura em engenharia biomedica?",
    "to quase acabando engenharia de materiais, o que preciso garantir pra formar?",
    "o que preciso pra concluir o BCT?",
]
for f in FORMATURA:
    check(f"detecta formatura: {f[:45]}…", progresso.is_requisitos_request(f))

print(f"\n{BOLD}── formatura: NÃO confunde com outras perguntas ──{RESET}")
NAO_FORMATURA = [
    "qual a ementa de banco de dados?",
    "quais disciplinas do termo 3 de bcc?",
    "quero fazer IC na area de otimizacao",
    "quem leciona banco de dados?",
    "como faco pra trancar uma materia?",
]
for f in NAO_FORMATURA:
    check(f"não dispara formatura: {f[:45]}", not progresso.is_requisitos_request(f))

print(f"\n{BOLD}── formatura: grounding do curso + critérios oficiais ──{RESET}")
CURSOS = {
    "ciencia da computacao": "BCC", "engenharia de computacao": "EC",
    "matematica computacional": "BMC", "biotecnologia": "BBT",
    "engenharia biomedica": "EB", "engenharia de materiais": "EM",
    "concluir o BCT": "BCT",
}
for texto, sig in CURSOS.items():
    check(f"aterra curso {sig} em {texto!r}",
          progresso.extrair_curso_requisitos(texto) == sig)
    resp = progresso.responder_requisitos(sig, texto)
    check(f"{sig}: responde integralização (cita horas)",
          bool(resp) and "horas" in resp.lower(), (resp or "")[:60])

# ── 2. Ponte APRENDIDA conceito→área (NSAI) ──────────────────────────────────
print(f"\n{BOLD}── NSAI: ponte conceito→área materializada ──{RESET}")
n_pa = kg.aprender_conceito_area(min_crenca=0.35)
check("materializa arestas PERTENCE_A no grafo", n_pa > 50, str(n_pa))
pa_edges = [(u, v, d) for u, v, d in kg.graph.edges(data=True)
            if d.get("relacao") == "PERTENCE_A"]
check("toda PERTENCE_A tem crença em (0,1] e proveniência aprendido=True",
      all(0 < d.get("confidence", 0) <= 1 and d.get("aprendido") for _, _, d in pa_edges))
check("idempotente (rodar de novo não duplica)",
      kg.aprender_conceito_area(min_crenca=0.35) == n_pa)

print(f"\n{BOLD}── NSAI: disciplinas_da_area (consumidor da ponte) ──{RESET}")
ds_ot = kg.disciplinas_da_area("Otimização")
check("área bem povoada retorna disciplinas ranqueadas", len(ds_ot) >= 2, str(len(ds_ot)))
check("ranqueado por score desc",
      [d["score"] for d in ds_ot] == sorted((d["score"] for d in ds_ot), reverse=True))
check("casamento de área é insensível a acento (otimizacao == Otimização)",
      len(kg.disciplinas_da_area("otimizacao")) == len(ds_ot))
check("área inexistente retorna vazio (auto-gated)",
      kg.disciplinas_da_area("gastronomia molecular") == [])

# ── 3. Contato/disciplinas de grupo de docentes ──────────────────────────────
print(f"\n{BOLD}── grupo de docentes: grounding + iteração no grafo ──{RESET}")


class _GRShim:
    """graph_rag mínimo p/ o teste: expõe .kg e o grounding _find_docente_in_text."""

    def __init__(self, kg):
        self.kg = kg

    def _find_docente_in_text(self, text):
        t = f" {self.kg._normalize_text(text)} "
        best = ""
        for _nid, d in self.kg.graph.nodes(data=True):
            if d.get("tipo") != "docente":
                continue
            nome = d.get("nome", "")
            n = self.kg._normalize_text(nome)
            if n and f" {n} " in t and len(n) > len(self.kg._normalize_text(best)):
                best = nome
        return best


gr = _GRShim(kg)
# docentes REAIS com e sem contato na base (para o grupo aterrado + lacuna honesta)
com_contato = [d.get("nome") for _n, d in kg.graph.nodes(data=True)
               if d.get("tipo") == "docente" and (d.get("email") or d.get("sala"))]
sem_contato = [
    n for _n, d in kg.graph.nodes(data=True)
    if d.get("tipo") == "docente" and (n := d.get("nome"))
    and kg._find_docente_id(n)
    and not ((kg.get_docente_info(n) or {}).get("email")
             or (kg.get_docente_info(n) or {}).get("sala"))]
falta_doc = sem_contato[0]
grupo = com_contato[:2] + [falta_doc]

# monkeypatch da intenção semântica (o teste valida grounding+iteração, não o embed)
contatos._intent_grupo = lambda p: (
    "contato" if any(w in p.lower() for w in ("falo", "contato", "email"))
    else "disciplinas")

r_contato = contatos.responder_grupo(gr, "como falo com eles?", grupo)
check("grupo/contato lista os docentes com contato na base",
      r_contato and all(nome in r_contato for nome in com_contato[:2]), (r_contato or "")[:80])
check("grupo/contato é honesto sobre docente REAL sem contato",
      r_contato and falta_doc in r_contato)

# grounding-filter: nome que NÃO aterra em docente (ruído de bullet de
# disciplina no context tracker) é descartado, não vira "faltante"
r_ruido = contatos.responder_grupo(
    gr, "como falo com eles?", com_contato[:2] + ["Geometria Analítica"])
check("nome que não aterra em docente é filtrado (não vira 'faltante')",
      r_ruido and "Geometria Analítica" not in r_ruido, (r_ruido or "")[:80])

nomeado = com_contato[0]
r_single = contatos.responder_grupo(gr, f"como falo com {nomeado}?", grupo)
check("pergunta que NOMEIA um docente responde só ele (grounding)",
      r_single and nomeado in r_single and com_contato[1] not in r_single, (r_single or "")[:80])

check("lista com <2 e sem nome não vira grupo (retorna None)",
      contatos.responder_grupo(gr, "como falo com eles?", []) is None)

# grounding em PROSA: docentes citados corridos no texto (não só bullets) —
# resolve a anáfora de grupo quando o LLM responde em prosa
prosa = (f"os docentes da disciplina são a {com_contato[0]}, "
         f"o {com_contato[1]} e tal, qualquer dúvida é só chamar")
ment = kg.docentes_mencionados(prosa)
check("docentes_mencionados captura nomes em prosa (não só bullets)",
      com_contato[0] in ment and com_contato[1] in ment, str(ment)[:80])
check("docentes_mencionados não inventa quem não está no texto",
      falta_doc not in kg.docentes_mencionados("texto sem docente nenhum aqui"))

# ── 4. Oferta × conteúdo: classificação semântica NN (requer embeddings) ─────
print(f"\n{BOLD}── oferta×conteúdo: nearest-neighbor (evita diluição de centróide) ──{RESET}")
oferta_real = _import_module("oferta_real", "src/oferta_real.py")
_emb = None
try:
    from src.rag import RAGUnifesp
    _r = RAGUnifesp()
    _r.sync()
    _emb = _r.embeddings
except Exception:
    _emb = None

if _emb is None:
    print("  (pulado: sem modelo de embeddings — roda no container)")
else:
    oferta_real.configurar_semantica(_emb)
    CONTEUDO_Q = [
        "qual a carga horária de compiladores",       # carga ≠ horário da aula
        "quantos créditos tem álgebra linear",
        "quais as áreas de pesquisa do professor",    # perfil-docente ≠ oferta
        "como falo com o professor",
        "qual a ementa de redes neurais",
        "quais os pré-requisitos de cálculo 2",
    ]
    OFERTA_Q = [
        "qual a sala de redes neurais",
        "que dia é a aula de inferência",
        "quais disciplinas o professor dá esse semestre",
        "em que sala fica algoritmos",
    ]
    for q in CONTEUDO_Q:
        check(f"conteúdo NÃO vira oferta: {q[:42]}",
              oferta_real._intencao_oferta(q) is False)
    for q in OFERTA_Q:
        check(f"oferta detectada: {q[:42]}",
              oferta_real._intencao_oferta(q) is True)

print(f"\n{BOLD}{_passed} passed, {_failed} failed{RESET}")
sys.exit(1 if _failed else 0)
