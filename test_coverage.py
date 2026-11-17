"""
Testes da checagem de cobertura da resposta (Perceive/Evaluate, MetaKGRAG).

Roda offline com o KG real da graduação (markdowns), sem LLM/langgraph:
carrega src/workflow/coverage.py e src/interaction_log.py isolados.
"""

import sys
import json
import tempfile
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
cov = _import_module("coverage", "src/workflow/coverage.py")
ilog = _import_module("interaction_log", "src/interaction_log.py")

kg = kg_mod.KnowledgeGraph()
kg.build_from_directories(
    disciplinas_dir="./markdown_disciplinas",
    regimentos_dir="./markdown_regimentos",
    docentes_dir="./markdown_docentes",
    cursos_dir="./markdown_cursos",
)

print(f"\n{BOLD}── Perceive: entidades da pergunta por grounding ──{RESET}")
ents = cov.entidades_da_pergunta(kg, "quem leciona compiladores e banco de dados?")
check("duas disciplinas aterradas",
      ents == [("disciplina", "Compiladores"), ("disciplina", "Banco de Dados")], ents)
ents = cov.entidades_da_pergunta(kg, "como falo com a lilian?")
check("docente por nome parcial único", ents == [("docente", "Lilian Berton")], ents)
check("pergunta sem entidade do KG → vazio",
      cov.entidades_da_pergunta(kg, "como trancar matrícula?") == [])
check("sem KG → vazio", cov.entidades_da_pergunta(None, "ementa de compiladores") == [])

print(f"\n{BOLD}── entidade_coberta: variações de escrita ──{RESET}")
check("numeral romano ↔ arábico",
      cov.entidade_coberta("disciplina", "Algoritmos e Estruturas de Dados II",
                           "A ementa de Algoritmos e Estruturas de Dados 2 cobre árvores."))
check("à/às e acento não importam",
      cov.entidade_coberta("disciplina", "Introdução às Redes Neurais Artificiais",
                           "Introducao a Redes Neurais Artificiais nao tem pre-requisito."))
check("docente pelo primeiro nome",
      cov.entidade_coberta("docente", "Lilian Berton", "A Profa. Lilian atende na sala 203."))
check("docente pelo sobrenome",
      cov.entidade_coberta("docente", "Marcos Gonçalves Quiles", "O email do prof. Quiles é ..."))
check("disciplina parcial NÃO cobre (Dados ≠ Banco de Dados)",
      not cov.entidade_coberta("disciplina", "Banco de Dados", "Estruturas de Dados é do 2º termo."))
check("numeral diferente NÃO cobre (I ≠ II)",
      not cov.entidade_coberta("disciplina", "Algoritmos e Estruturas de Dados II",
                               "Algoritmos e Estruturas de Dados I é do 1º termo."))

check("frase que só confessa falta NÃO cobre",
      not cov.entidade_coberta("disciplina", "Álgebra Linear",
                               "Matemática Discreta é do 2º termo. Não possuo "
                               "informações sobre a disciplina de Álgebra Linear."))
check("mesma entidade citada em outra frase com o dado cobre",
      cov.entidade_coberta("disciplina", "Álgebra Linear",
                           "Álgebra Linear é do 2º termo. Não tenho informações "
                           "sobre o horário de Álgebra Linear."))
check("sobrenome comum a outra entidade da pergunta NÃO cobre",
      not cov.entidade_coberta(
          "docente", "Sanderson Lincohn Gonzaga de Oliveira",
          "O email da docente Luzia Pedroso de Oliveira é luzia@unifesp.br.",
          ["Luzia Pedroso de Oliveira"]))
check("sobrenome sozinho cobre quando não há ambiguidade na pergunta",
      cov.entidade_coberta("docente", "Sanderson Lincohn Gonzaga de Oliveira",
                           "O prof. Sanderson atende na sala 310."))

print(f"\n{BOLD}── Evaluate: deficiência de completude ──{RESET}")
r = cov.avaliar_cobertura(
    kg, "quem leciona compiladores e banco de dados?",
    "Compiladores é lecionada pelo prof. Fulano no 6º termo.", "disciplinas")
check("detecta a entidade que faltou",
      r and r["faltantes"] == ["Banco de Dados"] and r["cobertura"] == 0.5, r)
r = cov.avaliar_cobertura(
    kg, "Banco de Dados é pré-requisito de Compiladores, né?",
    "Não: Banco de Dados não está na cadeia de pré-requisitos de Compiladores.",
    "symbolic_kg")
check("resposta completa → sem faltantes", r and r["faltantes"] == [], r)
r = cov.avaliar_cobertura(
    kg, "qual a sala de compiladores?",
    "Sinto muito, mas não tenho a informação sobre a sala da disciplina de "
    "Compiladores.", "disciplinas")
check("resposta que só confessa falta → ausencia_confessa, sem faltantes",
      r and r.get("ausencia_confessa") and r["faltantes"] == [], r)
r = cov.avaliar_cobertura(
    kg, "em que termo ficam Matemática Discreta e Álgebra Linear?",
    "Matemática Discreta fica no 2º termo. Não possuo informações sobre "
    "Álgebra Linear.", "disciplinas")
check("confissão PARCIAL → faltante, não ausência total",
      r and r["faltantes"] == ["Álgebra Linear"] and not r.get("ausencia_confessa"), r)
check("pergunta sem entidade → None (não se aplica)",
      cov.avaliar_cobertura(kg, "como trancar matrícula?", "Pelo SIIU ...", "regimentos") is None)
check("agente clarify é isento",
      cov.avaliar_cobertura(kg, "ementa de compiladores", "Você quis dizer...", "clarify") is None)
check("resposta vazia → None",
      cov.avaliar_cobertura(kg, "ementa de compiladores", "", "disciplinas") is None)

print(f"\n{BOLD}── contrato de atributo (intent → valor no KG) ──{RESET}")
r = cov.avaliar_cobertura(kg, "quais as áreas de pesquisa da Lilian?",
                          "A Profa. Lilian Berton leciona Lógica de Programação.",
                          "docentes", intent="docente_areas")
check("cita a docente mas omite as áreas → atributo faltante",
      r and r["faltantes"] == [] and
      r["atributos_faltantes"] == [("Lilian Berton", "áreas de pesquisa")], r)
r = cov.avaliar_cobertura(kg, "quais as áreas de pesquisa da Lilian?",
                          "A Profa. Lilian pesquisa aprendizado de máquina e redes complexas.",
                          "docentes", intent="docente_areas")
check("uma área do KG presente cobre", r and r["atributos_faltantes"] == [], r)
r = cov.avaliar_cobertura(kg, "como falo com a lilian?",
                          "Fale com a Lilian pelo lberton@unifesp.br.", "docentes",
                          intent="docente_info")
check("contato: email cobre", r and r["atributos_faltantes"] == [], r)
r = cov.avaliar_cobertura(kg, "quais os pré-requisitos de compiladores?",
                          "Compiladores é do 6º termo e trata de análise léxica.",
                          "symbolic_kg", intent="prerequisite_chain")
check("pré-requisito omitido → faltante",
      r and r["atributos_faltantes"] == [("Compiladores", "pré-requisitos")], r)
r = cov.avaliar_cobertura(kg, "quais os pré-requisitos de compiladores?",
                          "Para Compiladores você precisa de Linguagens Formais e Autômatos.",
                          "symbolic_kg", intent="prerequisite_chain")
check("pré-requisito citado cobre", r and r["atributos_faltantes"] == [], r)
r = cov.avaliar_cobertura(kg, "qual a ementa de compiladores?",
                          "Compiladores cobre análise léxica, análise sintática e geração de código.",
                          "disciplinas", intent="ementa_disciplina")
check("ementa: termos da ementa reaproveitados cobrem", r and r["atributos_faltantes"] == [], r)
r = cov.avaliar_cobertura(kg, "qual a ementa de compiladores?",
                          "Compiladores é ministrada pelo prof. Rodrigo no 6º termo.",
                          "disciplinas", intent="ementa_disciplina")
check("ementa omitida → faltante",
      r and r["atributos_faltantes"] == [("Compiladores", "ementa")], r)
r = cov.avaliar_cobertura(kg, "quem leciona compiladores?", "Compiladores é do 6º termo.",
                          "disciplinas", intent="faqs")
check("intent sem contrato não cobra atributo", r and r["atributos_faltantes"] == [], r)
check("resumo_faltantes junta entidade e atributo",
      cov.resumo_faltantes({"faltantes": ["Banco de Dados"],
                            "atributos_faltantes": [("Lilian Berton", "áreas de pesquisa")]})
      == ["Banco de Dados", "Lilian Berton (áreas de pesquisa)"])

print(f"\n{BOLD}── combinar_coberturas (pergunta composta) ──{RESET}")
c = cov.combinar_coberturas([
    {"entidades": ["Compiladores"], "faltantes": [], "cobertura": 1.0},
    None,
    {"entidades": ["Banco de Dados"], "faltantes": ["Banco de Dados"], "cobertura": 0.0},
])
check("une entidades e faltantes das subperguntas",
      c == {"entidades": ["Compiladores", "Banco de Dados"],
            "faltantes": ["Banco de Dados"], "atributos_faltantes": [],
            "cobertura": 0.5}, c)
check("nenhuma subpergunta aplicável → None", cov.combinar_coberturas([None, None]) is None)

print(f"\n{BOLD}── interaction_log: cobertura incompleta é turno suspeito ──{RESET}")
with tempfile.TemporaryDirectory() as tmp:
    alvo = str(Path(tmp) / "interactions.jsonl")
    ilog.log_turn("c1", "quem leciona compiladores e banco de dados?", "disciplinas",
                  "docente_info", 900, False, answer="Compiladores: prof. Fulano.",
                  path=alvo, cobertura_faltante=["Banco de Dados"])
    ilog.log_turn("c1", "ementa de compiladores", "disciplinas", "ementa",
                  900, False, answer="Compiladores aborda ...", path=alvo)
    linhas = [json.loads(l) for l in open(alvo, encoding="utf-8")]
check("grava faltantes e a resposta",
      linhas[0].get("cobertura_faltante") == ["Banco de Dados"]
      and linhas[0].get("suspeito") and "answer" in linhas[0], linhas[0])
check("turno completo e rápido segue sem resposta gravada",
      "answer" not in linhas[1] and "cobertura_faltante" not in linhas[1], linhas[1])

print(f"\n{BOLD}Resultado: {_passed} passaram, {_failed} falharam{RESET}")
sys.exit(1 if _failed else 0)
