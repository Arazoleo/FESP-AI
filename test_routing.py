"""
Testes de regressão do roteamento (item P2 do backlog).

Cobre:
  - Misroute do eval: "Me fale sobre a professora Lilian Berton." ia para
    disciplinas em vez de docentes.
  - phrase_override como fonte única dos overrides (substituiu correções
    hardcoded do pipeline).
  - check_routing do eval aceitando alternativas "a|b".

Executa sem LLM/embeddings.
"""

import sys
import importlib.util
from pathlib import Path

ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT))

spec = importlib.util.spec_from_file_location("router", ROOT / "src/workflow/router.py")
router = importlib.util.module_from_spec(spec)
spec.loader.exec_module(router)

GREEN, RED, BOLD, RESET = "\033[92m", "\033[91m", "\033[1m", "\033[0m"
_passed, _failed = 0, 0


def check(desc, cond, detail=""):
    global _passed, _failed
    if cond:
        _passed += 1
        print(f"{GREEN}✓{RESET} {desc}")
    else:
        _failed += 1
        print(f"{RED}✗ {desc}{RESET}" + (f" — {detail}" if detail else ""))


print(f"{BOLD}── route_intent / phrase_override ──{RESET}")
CASES = [
    # (pergunta, intent classificado, agente esperado)
    ("me fale sobre a professora lilian berton.", "ementa_disciplina", "docentes"),
    ("quem é o professor sanderson?", "", "docentes"),
    ("me fale sobre matemática discreta", "ementa_disciplina", "disciplinas"),
    ("fale sobre compiladores", "", "disciplinas"),
    ("qual a ementa de banco de dados?", "ementa_disciplina", "disciplinas"),
    ("quem leciona redes de computadores?", "discipline_docentes", "docentes"),
    ("quais os pré-requisitos de compiladores?", "prerequisite_chain", "disciplinas"),
    ("o que diz o regimento sobre estágio?", "", "regimentos"),
    ("como funcionam os cursos sequenciais?", "", "cursos"),
    ("grade curricular de bcc?", "todos_termos_curso", "cursos"),
]
for q, intent, expected in CASES:
    got = router.route_intent(intent, q)
    check(f"{q!r} → {expected}", got == expected, f"obteve {got!r}")

print(f"\n{BOLD}── phrase_override com agente do embedding ──{RESET}")
check(
    "'ementa' corrige docentes → disciplinas",
    router.phrase_override("qual a ementa de ihc?", "docentes") == "disciplinas",
)
check(
    "info de disciplina NÃO sobrescreve escolha explícita de cursos",
    router.phrase_override("me fale sobre o curso de bcc", "cursos") is None,
)
check(
    "'sobre a professora' sobrescreve qualquer agente",
    router.phrase_override("me fale sobre a professora lilian", "disciplinas") == "docentes",
)
check(
    "sem frase-gatilho retorna None (embedding mantém a escolha)",
    router.phrase_override("quais disciplinas do termo 3 de bcc?", "cursos") is None,
)

print(f"\n{BOLD}── word-boundary em todas as listas (classe de bug de substring) ──{RESET}")
check("'interdisciplinar' não aciona a exclusão 'disciplina' do web_sjc",
      router.is_web_sjc("como eu ingresso no curso de bacharelado interdisciplinar em ciência e tecnologia (bct)?"))
check("'disciplina' explícita ainda exclui do web_sjc",
      not router.is_web_sjc("qual o ingresso da disciplina de cálculo?"))
check("'normalmente' não força regimentos ('norma' interno)",
      router.phrase_override("normalmente quem coordena os estágios?") != "regimentos")

print(f"\n{BOLD}── formação/integralização: informacional ≠ montar grade ──{RESET}")
check("'o que preciso para me formar no bct?' NÃO é montar_grade",
      not router.is_montar_grade("o que preciso para me formar no bct?"))
check("'quantas horas para me formar no bct?' NÃO é montar_grade",
      not router.is_montar_grade("quantas horas para me formar no bct?"))
check("'o que preciso para me formar no bct?' → web_sjc (FAQ do site)",
      router.is_web_sjc("o que preciso para me formar no bct?"))
check("'quantas horas para me formar no bct?' → web_sjc",
      router.is_web_sjc("quantas horas para me formar no bct?"))
check("'como funciona a formação no bct?' → web_sjc",
      router.is_web_sjc("como funciona a formação no bct?"))
check("'monte minha grade de bcc' continua montar_grade",
      router.is_montar_grade("monte minha grade de bcc"))
check("'que disciplinas devo cursar no próximo semestre?' continua montar_grade",
      router.is_montar_grade("que disciplinas devo cursar no próximo semestre?"))
check("'monta minha grade respeitando os pré-requisitos' continua montar_grade",
      router.is_montar_grade("monta minha grade respeitando os pré-requisitos"))
check("'quantas horas tem o curso de bcc?' NÃO vira web_sjc (fica no KG)",
      not router.is_web_sjc("quantas horas tem o curso de bcc?"))

print(f"\n{BOLD}── quebra/distribuição de horas → web_sjc (FAQ do site tem os números) ──{RESET}")
check("'mas essas horas estão distribuídas em diferentes atividades?' → web_sjc",
      router.is_web_sjc("mas essas horas estão distribuídas em diferentes atividades?"))
check("pergunta reescrita de distribuição de horas → web_sjc",
      router.is_web_sjc("como as horas para integralizar o bct estão distribuídas entre unidades curriculares, extensão e atividades complementares?"))
check("'como as horas do bct são divididas?' → web_sjc",
      router.is_web_sjc("como as horas do bct são divididas?"))
check("'quantas horas de eletivas do bct?' → web_sjc",
      router.is_web_sjc("quantas horas de eletivas do bct?"))
check("'quantas horas de extensão preciso cumprir?' → web_sjc",
      router.is_web_sjc("quantas horas de extensão preciso cumprir?"))
check("'quantas horas de atividades complementares no bct?' → web_sjc",
      router.is_web_sjc("quantas horas de atividades complementares no bct?"))
check("'qual a carga horária de cálculo numérico?' NÃO vira web_sjc (disciplina, KG)",
      not router.is_web_sjc("qual a carga horária de cálculo numérico?"))
check("'quais as eletivas de bcc?' NÃO vira web_sjc (lista de eletivas, KG)",
      not router.is_web_sjc("quais as eletivas de bcc?"))
check("'como as disciplinas estão distribuídas nos termos?' NÃO vira web_sjc (sem 'horas')",
      not router.is_web_sjc("como as disciplinas estão distribuídas nos termos?"))

print(f"\n{BOLD}── is_conversational (word-boundary, não substring) ──{RESET}")
check("'como funciona o aproveitamento de estudos?' NÃO é conversa ('ei' interno)",
      not router.is_conversational("como funciona o aproveitamento de estudos?"))
check("'oi, tudo bem?' é conversa",
      router.is_conversational("oi, tudo bem?"))
check("'valeu, obrigado!' é conversa",
      router.is_conversational("valeu, obrigado!"))
check("'e ai beleza' é conversa",
      router.is_conversational("e ai beleza"))

print(f"\n{BOLD}── is_course_overview (desambiguação curso × disciplina via KG) ──{RESET}")
import re as _re
import unicodedata as _ud


class _FakeKG:
    """KG mínimo: 'teoria dos grafos' é disciplina; 'bct' é curso."""

    class _G:
        nodes = {"d1": {"tipo": "disciplina"}, "c1": {"tipo": "curso"}}

    graph = _G()
    _index_by_sigla = {}

    @staticmethod
    def _normalize_text(t):
        s = _ud.normalize("NFD", (t or "").lower().strip())
        s = "".join(c for c in s if _ud.category(c) != "Mn")
        s = _re.sub(r"[^\w\s]", " ", s)
        s = _re.sub(r"\b(de|da|do|das|dos|e)\b", " ", s)
        return _re.sub(r"\s+", " ", s).strip()

    @property
    def _index_by_name(self):
        return {"teoria grafos": "d1"}

    def _find_node(self, termo, tipo=None):
        if tipo == "curso" and self._normalize_text(termo) in ("bct", "ciencia tecnologia"):
            return "c1"
        return None


fake_kg = _FakeKG()
check("'o que é o bct?' → overview de curso", router.is_course_overview("o que é o bct?", fake_kg))
check("'o que é o curso de bct?' → overview de curso",
      router.is_course_overview("o que é o curso de bct?", fake_kg))
check("'me fale sobre o bct' → overview de curso",
      router.is_course_overview("me fale sobre o bct", fake_kg))
check("'o que é teoria dos grafos?' → NÃO (é disciplina)",
      not router.is_course_overview("o que é teoria dos grafos?", fake_kg))
check("'o que é o napcem?' → NÃO (entidade desconhecida)",
      not router.is_course_overview("o que é o napcem?", fake_kg))
check("kg=None não quebra",
      not router.is_course_overview("o que é o bct?", None))

print(f"\n{BOLD}── check_routing do eval (alternativas com '|') ──{RESET}")
eval_spec = importlib.util.spec_from_file_location("evalns", ROOT / "eval" / "eval_neurosymbolic.py")
evalns = importlib.util.module_from_spec(eval_spec)
try:
    eval_spec.loader.exec_module(evalns)
    check("aceita symbolic_kg em 'symbolic_kg|docentes'",
          evalns.check_routing("symbolic_kg", "symbolic_kg|docentes"))
    check("aceita docentes em 'symbolic_kg|docentes'",
          evalns.check_routing("docentes", "symbolic_kg|docentes"))
    check("rejeita agente fora das alternativas",
          not evalns.check_routing("disciplinas", "symbolic_kg|docentes"))
    check("comparação simples continua funcionando",
          evalns.check_routing("Docentes", "docentes"))
except SystemExit:
    print("(eval_neurosymbolic requer requests — pulando)")

print(f"\n{BOLD}{_passed} passed, {_failed} failed{RESET}")
sys.exit(1 if _failed else 0)
