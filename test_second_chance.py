"""
Testes do loop de segunda chance (retry-on-miss).

Executa sem LLM/langgraph: carrega src/workflow/second_chance.py isolado e
simula o pipeline com funções mockadas.
"""

import sys
import importlib.util
from pathlib import Path

ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT))

spec = importlib.util.spec_from_file_location(
    "second_chance", ROOT / "src/workflow/second_chance.py"
)
sc = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sc)

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


print(f"{BOLD}── is_miss_response (case/acento-insensitive) ──{RESET}")
check("'Não encontrei a disciplina X.' é miss",
      sc.is_miss_response("Não encontrei a disciplina X."))
check("'nao encontrei nada sobre isso' (sem acento) é miss",
      sc.is_miss_response("nao encontrei nada sobre isso"))
check("'NÃO ENCONTREI' (maiúsculas) é miss",
      sc.is_miss_response("Desculpe, NÃO ENCONTREI essa informação."))
check("'não tenho esse dado' é miss",
      sc.is_miss_response("Infelizmente não tenho esse dado no momento."))
check("'não consegui identificar' é miss",
      sc.is_miss_response("Não consegui identificar o curso na sua pergunta."))
check("resposta normal NÃO é miss",
      not sc.is_miss_response("A disciplina tem 4 créditos e é do 3º termo."))
check("'Encontrei 3 disciplinas' NÃO é miss",
      not sc.is_miss_response("Encontrei 3 disciplinas com esse nome."))
check("resposta vazia NÃO é miss (não dispara retry à toa)",
      not sc.is_miss_response(""))

print(f"\n{BOLD}── fallback_agent_for (heurística de segunda chance) ──{RESET}")
check("symbolic_kg → web_sjc", sc.fallback_agent_for("symbolic_kg") == "web_sjc")
check("disciplinas → web_sjc", sc.fallback_agent_for("disciplinas") == "web_sjc")
check("docentes → web_sjc", sc.fallback_agent_for("docentes") == "web_sjc")
check("cursos → web_sjc", sc.fallback_agent_for("cursos") == "web_sjc")
check("regimentos → web_sjc", sc.fallback_agent_for("regimentos") == "web_sjc")
check("web_sjc → fallback", sc.fallback_agent_for("web_sjc") == "fallback")
check("fallback → None (fim da cadeia)", sc.fallback_agent_for("fallback") is None)
check("conversa → None (sem retry)", sc.fallback_agent_for("conversa") is None)
check("meta → None (sem retry)", sc.fallback_agent_for("meta") is None)

print(f"\n{BOLD}── run_with_second_chance (pipeline mockado) ──{RESET}")

MISS = "Desculpe, não encontrei essa informação."
OK = "O responsável é o Prof. Fulano (sala 205)."


def make_pipeline(first_agent, first_resp, retry_resp):
    """Pipeline fake: 1ª chamada devolve first_resp; com forced_agent, retry_resp."""
    calls = []

    def invoke(state):
        calls.append(dict(state))
        if state.get("forced_agent"):
            return {**state, "active_agent": state["forced_agent"],
                    "response": retry_resp}
        return {**state, "active_agent": first_agent, "response": first_resp}

    return invoke, calls


events = []
inc = events.append

invoke, calls = make_pipeline("symbolic_kg", MISS, OK)
final = sc.run_with_second_chance(invoke, {"question": "q", "retry_count": 0}, inc)
check("miss → re-roteia (2 chamadas ao pipeline)", len(calls) == 2)
check("retry usa forced_agent=web_sjc", calls[1].get("forced_agent") == "web_sjc")
check("retry marca retry_count=1", calls[1].get("retry_count") == 1)
check("resposta recuperada substitui a primeira", final["response"] == OK)
check("agente final é o da segunda chance", final["active_agent"] == "web_sjc")
check("estado registra o agente que falhou", final.get("retry_from_agent") == "symbolic_kg")
check("telemetria: retry_recuperado", events == ["retry_recuperado"])

events.clear()
invoke, calls = make_pipeline("disciplinas", MISS, "Não encontrei no site do campus.")
final = sc.run_with_second_chance(invoke, {"question": "q", "retry_count": 0}, inc)
check("retry sem sucesso mantém a 1ª resposta", final["response"] == MISS)
check("agente final continua o original", final["active_agent"] == "disciplinas")
check("telemetria: retry_sem_sucesso", events == ["retry_sem_sucesso"])

events.clear()
invoke, calls = make_pipeline("docentes", OK, "n/a")
final = sc.run_with_second_chance(invoke, {"question": "q", "retry_count": 0}, inc)
check("sem miss → 1 chamada só", len(calls) == 1)
check("sem miss → sem eventos de telemetria", events == [])

invoke, calls = make_pipeline("conversa", MISS, OK)
final = sc.run_with_second_chance(invoke, {"question": "q", "retry_count": 0}, inc)
check("agente sem fallback não re-roteia", len(calls) == 1 and final["response"] == MISS)

invoke, calls = make_pipeline("web_sjc", MISS, OK)
final = sc.run_with_second_chance(invoke, {"question": "q", "retry_count": 0}, inc)
check("web_sjc → retry no fallback", calls[1].get("forced_agent") == "fallback")

invoke, calls = make_pipeline("symbolic_kg", MISS, OK)
final = sc.run_with_second_chance(invoke, {"question": "q", "retry_count": 1}, inc)
check("retry_count>0 nunca re-roteia (sem loop infinito)", len(calls) == 1)

invoke, calls = make_pipeline("cursos", MISS, "   ")
final = sc.run_with_second_chance(invoke, {"question": "q", "retry_count": 0}, inc)
check("retry com resposta vazia mantém a 1ª", final["response"] == MISS)

def invoke_boom(state):
    if state.get("forced_agent"):
        raise RuntimeError("boom")
    return {**state, "active_agent": "regimentos", "response": MISS}

final = sc.run_with_second_chance(invoke_boom, {"question": "q", "retry_count": 0}, inc)
check("exceção no retry mantém a 1ª resposta", final["response"] == MISS)

invoke, calls = make_pipeline("disciplinas", MISS, MISS)
final = sc.run_with_second_chance(invoke, {"question": "q", "retry_count": 0}, inc)
check("retry sem sucesso expõe retry_agent_tried",
      final.get("retry_agent_tried") == "web_sjc")

print(f"\n{BOLD}── misses_queue (fila de 'não encontrei') ──{RESET}")
import json as _json
import tempfile
import os as _os

mq_spec = importlib.util.spec_from_file_location("misses_queue", ROOT / "src/misses_queue.py")
mq = importlib.util.module_from_spec(mq_spec)
mq_spec.loader.exec_module(mq)

with tempfile.TemporaryDirectory() as tmp:
    path = _os.path.join(tmp, "misses_queue.jsonl")
    check("fila vazia → []", mq.read_misses(path=path) == [])
    mq.record_miss("q original?", "q enhanced?", ["disciplinas", "web_sjc"],
                   "Não encontrei nada. " + "x" * 500, path=path)
    itens = mq.read_misses(path=path)
    check("registro aparece na leitura", len(itens) == 1)
    e = itens[0] if itens else {}
    check("campos {ts,question,enhanced_question,agentes,resposta_truncada}",
          set(e) == {"ts", "question", "enhanced_question", "agentes", "resposta_truncada"})
    check("agentes registrados", e.get("agentes") == ["disciplinas", "web_sjc"])
    check("resposta truncada a 300 chars", len(e.get("resposta_truncada", "")) == 300)
    for i in range(60):
        mq.record_miss(f"q{i}", f"q{i}", ["a"], "não encontrei", path=path)
    itens = mq.read_misses(limit=50, path=path)
    check("read_misses respeita o limite de 50", len(itens) == 50)
    check("mais recente primeiro", itens[0].get("question") == "q59")
    with open(path, "a", encoding="utf-8") as f:
        f.write("{quebrado\n")
    check("linha corrompida é ignorada", len(mq.read_misses(limit=50, path=path)) == 50)

print(f"\n{BOLD}{_passed} passed, {_failed} failed{RESET}")
sys.exit(1 if _failed else 0)
