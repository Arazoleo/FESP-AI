"""
Testes da decomposição de perguntas compostas.
Usa um LLM falso (stub) - executa sem backend.
"""

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

_spec = importlib.util.spec_from_file_location("src.decomposer", ROOT / "src/decomposer.py")
d = importlib.util.module_from_spec(_spec)
d.__package__ = "src"
sys.modules["src.decomposer"] = d
_spec.loader.exec_module(d)

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


class FakeLLM:
    def __init__(self, resposta):
        self.resposta = resposta
        self.chamadas = 0

    def invoke(self, prompt):
        self.chamadas += 1
        return _types.SimpleNamespace(content=self.resposta)


print(f"\n{BOLD}1. Gate barato (alto recall, decisão nunca é dele){RESET}")
check("caso do beta tester 1 passa no gate",
      d.pode_ser_composta("Quais os pré-requisitos de Compiladores e quem leciona essa disciplina?"))
check("caso do beta tester 2 passa no gate",
      d.pode_ser_composta("Qual a ementa de Banco de Dados e quantas horas de AC eu preciso?"))
check("duas frases interrogativas passam no gate",
      d.pode_ser_composta("Quem leciona Compiladores? Qual a carga horária?"))
check("pergunta simples sem separador não passa",
      not d.pode_ser_composta("Quais os pré-requisitos de Compiladores?"))
check("pergunta curta não passa", not d.pode_ser_composta("Quem leciona IHC?"))
check("nome de disciplina com 'e' passa no gate (LLM decide não dividir)",
      d.pode_ser_composta("Qual a ementa de Ciência, Tecnologia e Sociedade?"))

print(f"\n{BOLD}2. Decisão do LLM{RESET}")
llm_divide = FakeLLM(
    '{"composta": true, "subperguntas": ["Quais os pré-requisitos de Compiladores?", "Quem leciona Compiladores?"]}'
)
subs = d.decompor_pergunta("Quais os pré-requisitos de Compiladores e quem leciona?", llm_divide)
check("LLM divide em 2 subperguntas autocontidas",
      subs == ["Quais os pré-requisitos de Compiladores?", "Quem leciona Compiladores?"], str(subs))
check("composta=false retorna None",
      d.decompor_pergunta("x", FakeLLM('{"composta": false, "subperguntas": []}')) is None)
check("JSON com cerca de código é tolerado",
      d.decompor_pergunta("x", FakeLLM('```json\n{"composta": true, "subperguntas": ["Pergunta um valida?", "Pergunta dois valida?"]}\n```')) is not None)
check("JSON quebrado retorna None",
      d.decompor_pergunta("x", FakeLLM('nao sei responder')) is None)
check("uma subpergunta só retorna None (não é composta de verdade)",
      d.decompor_pergunta("x", FakeLLM('{"composta": true, "subperguntas": ["Só uma pergunta?"]}')) is None)
subs4 = d.decompor_pergunta("x", FakeLLM(
    '{"composta": true, "subperguntas": ["Pergunta um valida?", "Pergunta dois valida?", "Pergunta tres valida?", "Pergunta quatro valida?"]}'
))
check("mais de 3 subperguntas é capado em 3", subs4 is not None and len(subs4) == 3, str(subs4))
check("subpergunta vazia/curta é descartada",
      d.decompor_pergunta("x", FakeLLM('{"composta": true, "subperguntas": ["ok?", "Pergunta valida de verdade?"]}')) is None)
check("LLM ausente retorna None", d.decompor_pergunta("x", None) is None)


class LLMExplode:
    def invoke(self, prompt):
        raise RuntimeError("timeout")


check("erro no LLM retorna None (pipeline segue caminho normal)",
      d.decompor_pergunta("x", LLMExplode()) is None)

print(f"\n{BOLD}3. Composição das respostas{RESET}")
subs = ["Quais os pré-requisitos de Compiladores?", "Quem leciona Compiladores?"]
resultados = [
    {
        "response": "Compiladores exige LFA e AED I.",
        "active_agent": "symbolic_kg",
        "confidence": 1.0,
        "sources": ["Knowledge Graph"],
        "graph_data": {"nodes": [1]},
        "suggestions": ["E a ementa?"],
    },
    {
        "response": "Quem leciona é o docente X.",
        "active_agent": "docentes",
        "confidence": 0.85,
        "sources": ["Knowledge Graph", "Corpo docente"],
    },
]
c = d.combinar_respostas(subs, resultados)
check("resposta em seções numeradas com a subpergunta como título",
      c["response"].startswith("**1. Quais os pré-requisitos de Compiladores?**")
      and "**2. Quem leciona Compiladores?**" in c["response"], c["response"][:120])
check("separador entre as partes", "\n\n---\n\n" in c["response"])
check("agentes diferentes viram 'multi'", c["active_agent"] == "multi")
check("intent é multi_intent", c["intent"] == "multi_intent")
check("fontes unidas sem duplicata",
      c["sources"] == ["Knowledge Graph", "Corpo docente"], str(c["sources"]))
check("confidence é o mínimo das partes", c["confidence"] == 0.85)
check("graph_data da primeira parte que tem", c["graph_data"] == {"nodes": [1]})
check("suggestions herdadas", c["suggestions"] == ["E a ementa?"])
mesmos = d.combinar_respostas(subs, [
    {"response": "a", "active_agent": "disciplinas", "sources": []},
    {"response": "b", "active_agent": "disciplinas", "sources": []},
])
check("mesmo agente nas duas partes mantém o agente", mesmos["active_agent"] == "disciplinas")

total = _passed + _failed
cor = GREEN if _failed == 0 else RED
print(f"\n{BOLD}{cor}{_passed}/{total} testes passaram{RESET}\n")
sys.exit(0 if _failed == 0 else 1)
