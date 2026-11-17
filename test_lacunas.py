"""
Testes da autoevolução verificada do KG (src/workflow/lacunas.py).

Roda offline com o KG real e os markdowns da base, sem LLM (o LLM da
proposta é simulado; a verificação é determinística).
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
_wf = _types.ModuleType("src.workflow")
_wf.__path__ = [str(ROOT / "src/workflow")]
sys.modules["src.workflow"] = _wf


def _import_workflow(name: str):
    full = f"src.workflow.{name}"
    spec = importlib.util.spec_from_file_location(full, ROOT / f"src/workflow/{name}.py")
    mod = importlib.util.module_from_spec(spec)
    mod.__package__ = "src.workflow"
    sys.modules[full] = mod
    spec.loader.exec_module(mod)
    return mod


cov = _import_workflow("coverage")
lac = _import_workflow("lacunas")

kg = kg_mod.KnowledgeGraph()
kg.build_from_directories(
    disciplinas_dir="./markdown_disciplinas",
    regimentos_dir="./markdown_regimentos",
    docentes_dir="./markdown_docentes",
    cursos_dir="./markdown_cursos",
)

print(f"\n{BOLD}── classificar: o KG decide código × dado ──{RESET}")
c = lac.classificar(kg, "quais as áreas de pesquisa da lilian?", "docente_areas")
check("KG tem as áreas → falha é de CÓDIGO",
      c == [{"entidade": "Lilian Berton", "tipo_entidade": "docente",
             "atributo": "áreas de pesquisa", "intent": "docente_areas", "classe": "codigo"}], c)
c = lac.classificar(kg, "quantos créditos tem álgebra linear?", "matriz_info")
check("KG não tem créditos → falha é de DADO",
      [x["classe"] for x in c] == ["dado"] and c[0]["entidade"] == "Álgebra Linear", c)
check("intent sem contrato → nada a classificar",
      lac.classificar(kg, "quem leciona compiladores?", "faqs") == [])

turnos = [
    {"question": "quantos créditos tem álgebra linear?", "intent": "matriz_info", "miss": True},
    {"question": "créditos de álgebra linear", "intent": "matriz_info", "miss": True},
    {"question": "quais as áreas da lilian?", "intent": "docente_areas", "miss": False,
     "cobertura_faltante": ["Lilian Berton (áreas de pesquisa)"]},
    {"question": "qual a ementa de compiladores?", "intent": "ementa_disciplina", "miss": False},
]
ls = lac.lacunas_do_log(kg, turnos)
check("agrega por (classe, entidade, atributo) e ignora turno sem falha",
      [(l["classe"], l["entidade"], l["frequencia"]) for l in ls]
      == [("dado", "Álgebra Linear", 2), ("codigo", "Lilian Berton", 1)], ls)

print(f"\n{BOLD}── proposta com proveniência ──{RESET}")
trechos = lac.trechos_fonte(ROOT, "Álgebra Linear")
check("acha as linhas de tabela com o nome exato (créditos/carga)",
      any("| Álgebra Linear | 4 |" in t["texto"] for t in trechos)
      and any("ÁLGEBRA LINEAR | 72h" in t["texto"] for t in trechos), [t["arquivo"] for t in trechos])
check("não confunde com Álgebra Linear Computacional no topo",
      "Computacional" not in trechos[0]["texto"].splitlines()[min(2, len(trechos[0]["texto"].splitlines()) - 1)],
      trechos[0])
lacuna = {"entidade": "Álgebra Linear", "tipo_entidade": "disciplina",
          "atributo": "créditos ou carga horária"}
boa = {"valor": "4", "citacao": "| Álgebra Linear | 4 |",
       "arquivo": "markdown_cursos/matriz_curricular_bcc.md"}
check("proposta fiel à fonte é verificada", lac.verificar(boa, lacuna, ROOT, kg)["ok"])
v = lac.verificar({**boa, "citacao": "| Álgebra Linear | 6 |", "valor": "6"}, lacuna, ROOT, kg)
check("citação inventada é rejeitada",
      not v["ok"] and "citação não existe literalmente no arquivo" in v["motivos"], v)
v = lac.verificar({**boa, "valor": "6"}, lacuna, ROOT, kg)
check("valor fora da citação é rejeitado",
      not v["ok"] and "valor não está na citação" in v["motivos"], v)
v = lac.verificar({**boa, "arquivo": "../../etc/hosts"}, lacuna, ROOT, kg)
check("arquivo fora das fontes é rejeitado", not v["ok"], v)
v = lac.verificar({"valor": "Lógica", "citacao": "| Lógica de Programação | 4 |",
                   "arquivo": "markdown_cursos/matriz_curricular_bcc.md"}, lacuna, ROOT, kg)
check("citação de outra entidade / tipo errado é rejeitada",
      not v["ok"] and "citação não é sobre a entidade" in v["motivos"]
      and "valor não tem o tipo de 'créditos ou carga horária'" in v["motivos"], v)
p = lac.propor({**lacuna}, ROOT, lambda _prompt: json.dumps(boa))
check("propor devolve o JSON do LLM", p == boa, p)
check("LLM sem valor → sem proposta",
      lac.propor({**lacuna}, ROOT, lambda _p: '{"valor": null}') is None)

print(f"\n{BOLD}Resultado: {_passed} passaram, {_failed} falharam{RESET}")
sys.exit(1 if _failed else 0)
