"""Teste standalone do planner (sem dependências pesadas)."""
import importlib.util

spec = importlib.util.spec_from_file_location("planner_mod", "src/planner.py")
planner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(planner)


class StubKG:
    """KG falso com um currículo pequeno para validar o algoritmo."""

    # termo -> [(nome, creditos)]
    TERMOS = {
        1: [("Cálculo 1", 4), ("Algoritmos 1", 4)],
        2: [("Cálculo 2", 4), ("Estruturas de Dados", 4)],
        3: [("Cálculo 3", 4), ("Compiladores", 6)],
    }
    # disciplina -> pré-requisitos diretos
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

# Caso 1: já cursou Cálculo 1, teto 8 créditos.
plan = planner.plan_curriculum(kg, "Teste", ["Cálculo 1"], max_creditos=8)
show(plan)

checks = []
sems = plan["semestres"]
# Pré-requisitos respeitados: Cálculo 2 depois de Cálculo 1 (cursada); EstruturasDados depois de Algoritmos 1.
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

# Caso 2: curso inexistente -> None
plan2 = planner.plan_curriculum(kg, "Curso Fantasma", [])
checks.append(("Curso inexistente retorna None", plan2 is None))

# Caso 3: disciplina cursada desconhecida -> aviso
plan3 = planner.plan_curriculum(kg, "Teste", ["Quântica Avançada"], max_creditos=24)
checks.append(("Cursada desconhecida gera aviso", any("não reconheci" in a.lower() for a in plan3["avisos"])))
# Caso 4: teto alto empacota mais por semestre
plan4 = planner.plan_curriculum(kg, "Teste", ["Cálculo 1", "Algoritmos 1"], max_creditos=24)
checks.append(("Teto 24: Estruturas e Cálculo 2 no mesmo semestre", sem_de_in(plan4, "Cálculo 2") == sem_de_in(plan4, "Estruturas de Dados")))

ok = True
for name, passed in checks:
    print(f"  [{'OK ' if passed else 'FAIL'}] {name}")
    ok = ok and passed
print("\nRESULTADO:", "TODOS OK" if ok else "FALHAS")
