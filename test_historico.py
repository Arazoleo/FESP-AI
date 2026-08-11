"""
Testes do parser de Histórico Acadêmico e do suporte a CR.
Usa fixture sintética no formato do extrator de PDF. Executa sem LLM/backend.
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

_spec = importlib.util.spec_from_file_location("src.historico", ROOT / "src/historico.py")
h = importlib.util.module_from_spec(_spec)
h.__package__ = "src"
sys.modules["src.historico"] = h
_spec.loader.exec_module(h)

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


FIXTURE = """Curso: INTERDISCIPLINAR EM CIÊNCIA E TECNOLOGIA - NOTURNO
Situação Acadêmica: EM CURSO Coeficiente de Rendimento (CR) Geral: 6.6
ANO/SEM | 2023/1 Coeficiente de Rendimento (CR): 7.5
Unidade Curricular Cod.
Grupo Tipo UC CH CHEXT Crédito Freq.
(%) Conceito Situação
9394 - LÓGICA DE PROGRAMAÇÃO
Docente: FULANA DE TAL Titulação: Doutorado 121 DF 72 - 4 94 8,0 APROVADO
2609 - PROBABILIDADE E ESTATÍSTICA
Docente: BELTRANO SILVA Titulação: Doutorado 182 DE 72 18 4 86 7,0 APROVADO
ANO/SEM | 2023/2 Coeficiente de Rendimento (CR): 4.8
2832 - ALGORITMOS E ESTRUTURAS DE DADOS I
Docente: CICLANA SOUZA Titulação: Doutorado 102 DE 72 - 4 97 4,8 REPROVADO
"""

print(f"\n{BOLD}1. Parser do histórico{RESET}")
d = h.parsear_historico(FIXTURE)
check("parse retorna dados", d is not None)
check("curso extraído", "CIÊNCIA E TECNOLOGIA" in d["curso"], d["curso"])
check("3 disciplinas parseadas", len(d["disciplinas"]) == 3)
check("2 semestres com CR", len(d["semestres"]) == 2 and d["semestres"][0]["cr"] == 7.5)
lp = d["disciplinas"][0]
check("campos da UC corretos",
      lp["codigo"] == "9394" and lp["creditos"] == 4 and lp["nota"] == 8.0
      and lp["grupo"] == "121" and lp["situacao"] == "APROVADO", str(lp))
check("texto irreconhecível retorna None", h.parsear_historico("oi tudo bem?") is None)

print(f"\n{BOLD}2. CR: cálculo, validação e simulação{RESET}")
check("CR = média ponderada nota × créditos (6.6)", d["cr_calculado"] == 6.6, str(d["cr_calculado"]))
check("CR recalculado confere com o do documento", d["cr_confere"])
check("simulação: +10 em 4 créditos sobe para 7.45",
      h.simular_cr(d["disciplinas"], [(10, 4)]) == 7.45,
      str(h.simular_cr(d["disciplinas"], [(10, 4)])))

print(f"\n{BOLD}3. Extrações do histórico{RESET}")
check("aprovadas exclui reprovação",
      len(h.aprovadas(d)) == 2 and not any("Estruturas" in a for a in h.aprovadas(d)))
check("interdisciplinar detectada pelo grupo 182",
      h.interdisciplinares_cursadas(d) == ["Probabilidade E Estatística"])
check("reprovações listadas", len(h.reprovacoes(d)) == 1)
check("resumo cita CR e interdisciplinares",
      "6.6" in h.resumo_historico(d) and "1 de 4" in h.resumo_historico(d))

check("curso do histórico mapeado para BCT (sem cair na sigla EM)",
      h.curso_sigla("INTERDISCIPLINAR EM CIÊNCIA E TECNOLOGIA - NOTURNO") == "BCT")
check("engenharia de materiais mapeia para EM",
      h.curso_sigla("ENGENHARIA DE MATERIAIS") == "EM")

print(f"\n{BOLD}4. Detectores e simulação em linguagem natural{RESET}")
check("detecta 'qual meu CR?'", h.is_cr_request("Qual meu CR?"))
check("detecta 'simula meu cr'", h.is_cr_request("simula meu cr se eu tirar 9 em AED"))
check("não dispara em pergunta de CR alheio",
      not h.is_cr_request("o CR influencia na matrícula?"))
sims = h.extrair_simulacao("e se eu tirar 9,5 em banco de dados de 4 créditos?")
check("extrai nota, alvo e créditos da simulação",
      sims == [(9.5, "banco de dados", 4)], str(sims))
check("sem histórico, resposta pede o upload",
      "Histórico" in h.responder_cr(None, "qual meu cr?"))
resp = h.responder_cr(d, "qual meu cr? e se eu tirar 10 em uma disciplina de 4 créditos?")
check("resposta com histórico traz CR e simulação",
      "6.6" in resp and "Simulação" in resp, resp[:150])

total = _passed + _failed
cor = GREEN if _failed == 0 else RED
print(f"\n{BOLD}{cor}{_passed}/{total} testes passaram{RESET}\n")
sys.exit(0 if _failed == 0 else 1)
