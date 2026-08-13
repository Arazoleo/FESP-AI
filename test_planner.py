"""Teste standalone do planner (sem dependências pesadas)."""
import importlib.util
import sys
import types as _types
from pathlib import Path

ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT))

if "src" not in sys.modules:
    _pkg = _types.ModuleType("src")
    _pkg.__path__ = [str(ROOT / "src")]
    _pkg.__package__ = "src"
    sys.modules["src"] = _pkg


def _mod(name, path):
    spec = importlib.util.spec_from_file_location(name, ROOT / path)
    m = importlib.util.module_from_spec(spec)
    m.__package__ = "src"
    sys.modules[name] = m
    spec.loader.exec_module(m)
    return m


_mod("src.oferta", "src/oferta.py")
_mod("src.historico", "src/historico.py")
_mod("src.progresso", "src/progresso.py")
planner = _mod("src.planner", "src/planner.py")


class StubKG:
    """KG falso com um currículo pequeno para validar o algoritmo."""

    TERMOS = {
        1: [("Cálculo 1", 4), ("Algoritmos 1", 4)],
        2: [("Cálculo 2", 4), ("Estruturas de Dados", 4)],
        3: [("Cálculo 3", 4), ("Compiladores", 6)],
    }
    PREREQS = {
        "Cálculo 2": ["Cálculo 1"],
        "Cálculo 3": ["Cálculo 2"],
        "Estruturas de Dados": ["Algoritmos 1"],
        "Compiladores": ["Estruturas de Dados"],
    }

    def _normalize_text(self, s):
        return (s or "").strip().lower()

    def get_todos_termos_do_curso(self, curso):
        if self._normalize_text(curso) not in ("teste", "bcc"):
            return {}
        return {
            t: [{"nome": n, "creditos": c, "termo": t} for n, c in discs]
            for t, discs in self.TERMOS.items()
        }

    def get_direct_prerequisites(self, nome):
        return list(self.PREREQS.get(nome, []))


def show(plan):
    print(f"Curso: {plan['curso']} | teto {plan['max_creditos']} cr")
    print(f"Cursadas reconhecidas: {plan['completed']}")
    for s in plan["semestres"]:
        nomes = [f"{d['nome']}({d['creditos']})" for d in s["disciplinas"]]
        print(f"  Semestre {s['numero']} [{s['creditos']}cr]: {', '.join(nomes)}")
    print(f"  Totais: {plan['total_semestres']} sem, {plan['total_disciplinas']} disc, {plan['total_creditos']}cr")
    print(f"  Avisos: {plan['avisos']}")
    print(f"  Nós: {len(plan['nodes'])} | Arestas: {len(plan['edges'])}")
    print()


kg = StubKG()

plan = planner.plan_curriculum(kg, "Teste", ["Cálculo 1"], max_creditos=8)
show(plan)

checks = []
sems = plan["semestres"]
def sem_de_in(plan, nome):
    for s in plan["semestres"]:
        if any(d["nome"] == nome for d in s["disciplinas"]):
            return s["numero"]
    return None

def sem_de(nome):
    return sem_de_in(plan, nome)

checks.append(("Cálculo 1 não reaparece", sem_de("Cálculo 1") is None))
checks.append(("Algoritmos 1 antes de Estruturas de Dados", sem_de("Algoritmos 1") < sem_de("Estruturas de Dados")))
checks.append(("Cálculo 2 antes de Cálculo 3", sem_de("Cálculo 2") < sem_de("Cálculo 3")))
checks.append(("Estruturas antes de Compiladores", sem_de("Estruturas de Dados") < sem_de("Compiladores")))
checks.append(("Nenhum semestre passa de 8 cr", all(s["creditos"] <= 8 for s in sems)))
checks.append(("Todas as 5 restantes planejadas", plan["total_disciplinas"] == 5))
checks.append(("Sem avisos de não-planejadas", not any("não consegui encaixar" in a.lower() for a in plan["avisos"])))
checks.append(("Aresta Cálculo 1 -> Cálculo 2 existe", {"from": "Cálculo 1", "to": "Cálculo 2"} in plan["edges"]))

plan2 = planner.plan_curriculum(kg, "Curso Fantasma", [])
checks.append(("Curso inexistente retorna None", plan2 is None))

plan3 = planner.plan_curriculum(kg, "Teste", ["Quântica Avançada"], max_creditos=24)
checks.append(("Cursada desconhecida gera aviso", any("não reconheci" in a.lower() for a in plan3["avisos"])))
plan4 = planner.plan_curriculum(kg, "Teste", ["Cálculo 1", "Algoritmos 1"], max_creditos=24)
checks.append(("Teto 24: Estruturas e Cálculo 2 no mesmo semestre", sem_de_in(plan4, "Cálculo 2") == sem_de_in(plan4, "Estruturas de Dados")))

from datetime import date as _date

_ago = _date(2026, 8, 15)
plan5 = planner.plan_curriculum(kg, "Teste", [], max_creditos=8, data=_ago)
sems5 = plan5["semestres"]
checks.append(("semestres ganham rotulo real a partir do proximo (2027/1)",
               sems5[0].get("rotulo") == "2027/1"))
checks.append(("paridade do semestre registrada",
               sems5[0].get("paridade") == "impar"))
def paridades_ok(plan):
    for s in plan["semestres"]:
        for d in s["disciplinas"]:
            if d.get("paridade") and d["paridade"] != s["paridade"]:
                return False
    return True
checks.append(("nenhuma UC cai em semestre de paridade errada", paridades_ok(plan5)))
checks.append(("termo 2 (par) so em semestre par",
               all(s["paridade"] == "par"
                   for s in sems5 for d in s["disciplinas"]
                   if d["termo_sugerido"] == 2)))
plan6 = planner.plan_curriculum(kg, "Teste", [], max_creditos=8,
                                respeitar_oferta=False, data=_ago)
checks.append(("respeitar_oferta=False volta ao empacotamento livre",
               plan6["total_semestres"] <= plan5["total_semestres"]))

ok = True
for name, passed in checks:
    print(f"  [{'OK ' if passed else 'FAIL'}] {name}")
    ok = ok and passed
print("\nRESULTADO:", "TODOS OK" if ok else "FALHAS")
