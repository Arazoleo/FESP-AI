"""
Testes do debate com juiz simbólico.
Executa sem LLM/langgraph: carrega o módulo isolado e usa candidatos mockados.
"""

import sys
import importlib.util
import types as _types
from pathlib import Path

ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT))

sc_spec = importlib.util.spec_from_file_location(
    "second_chance", ROOT / "src/workflow/second_chance.py"
)
sc = importlib.util.module_from_spec(sc_spec)
sc_spec.loader.exec_module(sc)
sys.modules["src"] = _types.ModuleType("src")
sys.modules["src"].__path__ = [str(ROOT / "src")]
sys.modules["src.workflow"] = _types.ModuleType("src.workflow")
sys.modules["src.workflow"].__path__ = [str(ROOT / "src/workflow")]
sys.modules["src.workflow.second_chance"] = sc

db_spec = importlib.util.spec_from_file_location(
    "src.workflow.debate", ROOT / "src/workflow/debate.py"
)
db = importlib.util.module_from_spec(db_spec)
db.__package__ = "src.workflow"
sys.modules["src.workflow.debate"] = db
db_spec.loader.exec_module(db)

GREEN, RED, BOLD, RESET = "\033[92m", "\033[91m", "\033[1m", "\033[0m"
_passed, _failed = 0, 0


def check(desc, cond, detail=""):
    global _passed, _failed
    if cond:
        _passed += 1
        print(f"  {GREEN}PASS{RESET} {desc}")
    else:
        _failed += 1
        print(f"  {RED}FAIL{RESET} {desc}" + (f" - {detail}" if detail else ""))


print(f"\n{BOLD}1. Pontuação simbólica{RESET}")
check("fatos verificados somam",
      db.pontuar({"response": "ok", "fatos_verificados": ["a", "b"], "violacoes": []}) == 4)
check("violações penalizam mais que fatos somam",
      db.pontuar({"response": "ok", "fatos_verificados": ["a"], "violacoes": ["v"]}) == -1)
check("miss é desclassificado",
      db.pontuar({"response": "não encontrei nada", "fatos_verificados": ["a", "b", "c"]}) < 0)
check("resposta vazia é desclassificada", db.pontuar({"response": "  "}) < 0)

print(f"\n{BOLD}2. Julgamento{RESET}")
a = {"agente": "web_sjc", "response": "resposta A", "fatos_verificados": ["f1"], "violacoes": []}
b = {"agente": "rag_geral", "response": "resposta B", "fatos_verificados": ["f1", "f2"], "violacoes": []}
v = db.julgar([a, b])
check("mais fatos verificados vence", v["agente"] == "rag_geral", str(v.get("veredito")))
check("veredito registra os scores dos dois",
      v["veredito"]["scores"] == {"web_sjc": 2, "rag_geral": 4}, str(v["veredito"]))
empate = db.julgar([a, {**b, "fatos_verificados": ["f1"]}])
check("empate mantém o primeiro candidato", empate["agente"] == "web_sjc")
check("empate sinalizado no veredito", empate["veredito"]["empate"] is True)
viol = db.julgar([
    {"agente": "x", "response": "afirma coisas erradas", "fatos_verificados": ["f1", "f2"], "violacoes": ["v1", "v2"]},
    {"agente": "y", "response": "modesta e correta", "fatos_verificados": ["f1"], "violacoes": []},
])
check("resposta com violações perde para resposta limpa", viol["agente"] == "y")
miss = db.julgar([
    {"agente": "x", "response": "não encontrei nada sobre isso", "fatos_verificados": []},
    {"agente": "y", "response": "aqui está a informação", "fatos_verificados": []},
])
check("não-miss vence miss mesmo sem fatos", miss["agente"] == "y")

print(f"\n{BOLD}3. debater (orquestração){RESET}")


def resp_ok():
    return {"response": "informação boa", "sources": ["s1"]}


def resp_miss():
    return {"response": "não encontrei", "sources": []}


def resp_explode():
    raise RuntimeError("caiu")


def validar(resposta):
    if "boa" in resposta:
        return {"fatos_verificados": ["f"], "violacoes": []}
    return {"fatos_verificados": [], "violacoes": []}


contadores = {}


def incr(k):
    contadores[k] = contadores.get(k, 0) + 1


r = db.debater("q", [
    {"agente": "a", "responder": resp_miss},
    {"agente": "b", "responder": resp_ok},
], validar=validar, telemetry_incr=incr)
check("vencedor certo com validação", r["agente"] == "b", str(r.get("veredito")))
check("telemetria do debate registrada",
      contadores.get("debate_executado") == 1 and contadores.get("debate_vencedor_b") == 1,
      str(contadores))
r2 = db.debater("q", [
    {"agente": "a", "responder": resp_explode},
    {"agente": "b", "responder": resp_ok},
])
check("candidato que explode é descartado, sobrevivente responde",
      r2.get("agente") == "b" and "veredito" not in r2)
check("nenhum candidato → dict vazio", db.debater("q", [
    {"agente": "a", "responder": resp_explode},
]) == {})

total = _passed + _failed
cor = GREEN if _failed == 0 else RED
print(f"\n{BOLD}{cor}{_passed}/{total} testes passaram{RESET}\n")
sys.exit(0 if _failed == 0 else 1)
