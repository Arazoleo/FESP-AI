"""
Testes de regressão do follow-up de atividades complementares (ciclo 2 de
usabilidade): oferta de detalhamento por eixo ao fim das respostas sobre AC,
aceite curto reescrito para a pergunta canônica e resposta simbólica direta
do regulamento estruturado.

Executa sem LLM/backend.
"""

import importlib.util
import sys
import types as _types
from pathlib import Path

ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT))


def _import_module(full_name: str, path: str):
    """Importa módulos de src/ sem executar src/__init__.py (que puxa langchain)."""
    if "src" not in sys.modules:
        pkg = _types.ModuleType("src")
        pkg.__path__ = [str(ROOT / "src")]
        pkg.__package__ = "src"
        sys.modules["src"] = pkg
    spec = importlib.util.spec_from_file_location(full_name, ROOT / path)
    mod = importlib.util.module_from_spec(spec)
    mod.__package__ = full_name.rsplit(".", 1)[0]
    sys.modules[full_name] = mod
    spec.loader.exec_module(mod)
    return mod


_ac = _import_module(
    "src.atividades_complementares", "src/atividades_complementares.py"
)
_cr = _import_module("src.context_resolver", "src/context_resolver.py")

BREAKDOWN_CANONICAL_QUESTION = _ac.BREAKDOWN_CANONICAL_QUESTION
FOLLOWUP_OFFER = _ac.FOLLOWUP_OFFER
OFFER_MARKER = _ac.OFFER_MARKER
build_breakdown_response = _ac.build_breakdown_response
is_ac_question = _ac.is_ac_question
is_affirmative_reply = _ac.is_affirmative_reply
is_breakdown_request = _ac.is_breakdown_request
maybe_append_offer = _ac.maybe_append_offer
ContextResolver = _cr.ContextResolver

GREEN, RED, BOLD, RESET = "\033[92m", "\033[91m", "\033[1m", "\033[0m"
_passed, _failed = 0, 0


def check(desc, cond, detail=""):
    global _passed, _failed
    if cond:
        _passed += 1
        print(f"  {GREEN}PASS{RESET} {desc}")
    else:
        _failed += 1
        print(f"  {RED}FAIL{RESET} {desc}" + (f" — {detail}" if detail else ""))


# ── 1. Resposta simbólica direta do regulamento ──────────────────────────────
print(f"\n{BOLD}1. build_breakdown_response (regulamento estruturado){RESET}")
resp = build_breakdown_response()
check("resposta não vazia", bool(resp))
check("cita os 3 eixos",
      all(n in resp for n in (
          "Formação Cidadã", "Orientação Acadêmica", "Formação Pessoal")),
      resp[:120])
check("limite de 104 horas do eixo 1", "104" in resp)
check("carga mínima de 312 horas", "312" in resp)
check("ACE eletivas (36 a 108 horas)", "ACE" in resp and "108" in resp)
check("cita a fonte (regulamento)", "Regulamento" in resp)
check("marcador da oferta NÃO está na própria resposta", OFFER_MARKER not in resp)

# ── 2. Detecção do pedido de detalhamento ────────────────────────────────────
print(f"\n{BOLD}2. is_breakdown_request{RESET}")
positivos = [
    BREAKDOWN_CANONICAL_QUESTION,
    "O que conta em cada eixo das atividades complementares?",
    "Quais são os eixos das atividades complementares?",
    "O que vale como atividade complementar?",
    "Quais atividades são aceitas em cada eixo?",
    "Tipos de atividades complementares",
    "Detalha as atividades complementares por categoria, por favor",
]
for q in positivos:
    check(f"positivo: '{q[:55]}'", is_breakdown_request(q))
negativos = [
    "Quantas horas de atividades complementares preciso?",
    "Como funcionam as atividades complementares?",
    "As ACE são obrigatórias?",
    "Quais atividades posso fazer no próximo semestre?",
    "Quais os pré-requisitos de Compiladores?",
]
for q in negativos:
    check(f"negativo: '{q[:55]}'", not is_breakdown_request(q))

# ── 3. Aceite curto da oferta ────────────────────────────────────────────────
print(f"\n{BOLD}3. is_affirmative_reply{RESET}")
for q in ["sim", "Sim!", "sim, pode", "quero, por favor", "pode ser",
          "claro", "detalha", "manda", "Sim, por favor."]:
    check(f"aceita: '{q}'", is_affirmative_reply(q))
for q in ["não", "nao, obrigado", "sim, mas quantas horas de extensão?",
          "quem leciona Cálculo?", "", "talvez depois",
          "sim quero saber sobre o professor"]:
    check(f"rejeita: '{q}'", not is_affirmative_reply(q))

# ── 4. Oferta pós-resposta ───────────────────────────────────────────────────
print(f"\n{BOLD}4. maybe_append_offer{RESET}")
pergunta_ac = "Como funcionam as atividades complementares?"
resposta_base = "As AC somam 312 horas obrigatórias em três eixos."
com_oferta = maybe_append_offer(pergunta_ac, resposta_base)
check("anexa oferta em pergunta sobre AC", com_oferta.endswith(FOLLOWUP_OFFER))
check("idempotente (não duplica a oferta)",
      maybe_append_offer(pergunta_ac, com_oferta) == com_oferta)
check("não anexa quando a pergunta JÁ pede o detalhamento",
      maybe_append_offer("O que conta em cada eixo das atividades complementares?",
                         resposta_base) == resposta_base)
check("não anexa em pergunta de outro assunto",
      maybe_append_offer("Quais os pré-requisitos de IA?", resposta_base)
      == resposta_base)
check("não anexa em resposta vazia", maybe_append_offer(pergunta_ac, "") == "")

# ── 5. Fluxo no ContextResolver (oferta pendente → aceite → canônica) ────────
print(f"\n{BOLD}5. ContextResolver: aceite vira pergunta canônica{RESET}")
resolver = ContextResolver()
conv = "test-ac-followup"
historia = [
    {"role": "user", "content": pergunta_ac},
    {"role": "assistant", "content": com_oferta},
]
for msg in historia:
    resolver.update_context(conv, msg["content"], msg["role"])
resolved, modified = resolver.resolve_question("sim, pode", conv, historia)
check("aceite reescrito para a pergunta canônica",
      modified and resolved == BREAKDOWN_CANONICAL_QUESTION, resolved)
check("pergunta canônica toma o atalho simbólico",
      is_breakdown_request(resolved))
check("oferta pendente consumida após o aceite",
      resolver.get_context(conv).pending_offer is None)

resolver2 = ContextResolver()
conv2 = "test-ac-recusa"
for msg in historia:
    resolver2.update_context(conv2, msg["content"], msg["role"])
resolved2, modified2 = resolver2.resolve_question("não, obrigado", conv2, historia)
check("recusa não é reescrita", resolved2 == "não, obrigado")

resolver3 = ContextResolver()
conv3 = "test-ac-oferta-limpa"
resolver3.update_context(conv3, com_oferta, "assistant")
resolver3.update_context(conv3, "A ementa de Cálculo 1 é: limites e derivadas.",
                         "assistant")
resolved3, modified3 = resolver3.resolve_question("sim", conv3, [])
check("resposta nova do assistente limpa a oferta pendente",
      resolved3 == "sim" and not modified3, resolved3)

# ── Resumo ───────────────────────────────────────────────────────────────────
total = _passed + _failed
cor = GREEN if _failed == 0 else RED
print(f"\n{BOLD}{cor}{_passed}/{total} testes passaram{RESET}\n")
sys.exit(0 if _failed == 0 else 1)
