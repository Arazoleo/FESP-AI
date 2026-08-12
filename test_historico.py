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
RESUMO
Totais de carga horária por tipo de UC
FIXAS 72
ELETIVAS 72
Total de horas cumpridas pelo estudante (teórica + prática) 144
Carga horária extensionista: 18 horas do total cumprido pelo(a) estudante.
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
      "6.6" in h.resumo_historico(d)
      and "1 UCs Eletivas Interdisciplinares" in h.resumo_historico(d),
      h.resumo_historico(d)[:300])
check("resumo traz as horas do RESUMO do PDF",
      "144h cumpridas" in h.resumo_historico(d)
      and "18h de extensão" in h.resumo_historico(d),
      h.resumo_historico(d)[:300])

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

print(f"\n{BOLD}5. Previsão de CR: semestre atual e metas{RESET}")
cursando = h.extrair_cursando(
    "estou fazendo Compiladores, Redes de Computadores e IHC esse semestre"
)
check("extrai as disciplinas do semestre atual",
      cursando == ["compiladores", "redes de computadores", "ihc"], str(cursando))
check("declaração detectada",
      h.is_cursando_decl("tô cursando Banco de Dados e IHC neste semestre"))
check("pergunta comum não vira declaração",
      not h.is_cursando_decl("quais os pré-requisitos de Compiladores?"))
check("nota uniforme extraída",
      h.extrair_nota_uniforme("se eu passar com 8 em todas, quanto fica?") == 8.0)
check("alvo de CR extraído",
      h.extrair_alvo_cr("quanto preciso tirar para meu cr chegar a 8.5?") == 8.5)
check("sem contexto de meta não extrai alvo",
      h.extrair_alvo_cr("meu cr é 8.5") is None)

necessaria = h.nota_necessaria(d["disciplinas"], [4, 4], 7.5)
check("nota necessária resolve a equação da média ponderada (8.85)",
      necessaria == 8.85, str(necessaria))
check("meta impossível retorna acima de 10",
      h.nota_necessaria(d["disciplinas"], [4], 9.9) > 10)

sessao = dict(d)
h.registrar_cursando(sessao, ["Disciplina A", "Disciplina B"], kg=None)
check("cursando registrado na sessão com 4 créditos default",
      len(sessao["cursando"]) == 2 and sessao["cursando"][0]["creditos"] == 4)
resp_meta = h.responder_cr(sessao, "quanto preciso tirar para meu cr chegar a 7.5?")
check("resposta de meta traz a média necessária",
      "8.85" in resp_meta, resp_meta[:200])
resp_cen = h.responder_cr(sessao, "se eu passar com 8 em todas, quanto fica meu cr?")
check("cenário uniforme simulado (6.6 → 7.16)",
      "7.16" in resp_cen, resp_cen[:220])
resp_decl = h.responder_cursando(dict(d), "estou fazendo Disciplina A esse semestre")
check("declaração confirma e ensina as perguntas de previsão",
      "Anotei" in resp_decl and "chegar a" in resp_decl)

print(f"\n{BOLD}6. Horas do RESUMO e quadro de integralização{RESET}")
check("horas do RESUMO parseadas",
      d["horas"] == {"fixas": 72, "eletivas": 72, "total": 144, "extensao": 18},
      str(d["horas"]))

_spec_p = importlib.util.spec_from_file_location("src.progresso", ROOT / "src/progresso.py")
p = importlib.util.module_from_spec(_spec_p)
p.__package__ = "src"
sys.modules["src.progresso"] = p
_spec_p.loader.exec_module(p)

quadro = p._quadro_integralizacao("BCT", d, 0, ["Probabilidade E Estatística"])
check("quadro de integralização montado para o BCT", quadro is not None)
comps = {c["nome"]: c for c in quadro["componentes"]}
check("fixas comparadas com 468h exigidas (72 < 468 → falta)",
      comps["UCs fixas (obrigatórias)"]["ok"] is False
      and comps["UCs fixas (obrigatórias)"]["exigido"] == 468)
check("eletivas comparadas com 1620h", comps["UCs eletivas"]["exigido"] == 1620)
check("extensão comparada com 240h",
      comps["Extensão curricularizada"]["ok"] is False
      and comps["Extensão curricularizada"]["exigido"] == 240)
check("interdisciplinares 1 de 4 → falta",
      comps["UCs Eletivas Interdisciplinares"]["ok"] is False)
check("AC marcadas como a confirmar (fora do histórico)",
      comps["Atividades Complementares"]["ok"] is None)
check("quadro aponta o que falta",
      not quadro["completo_verificavel"] and len(quadro["faltando"]) == 4,
      str([c["nome"] for c in quadro["faltando"]]))

d_ok = dict(d)
d_ok["horas"] = {"fixas": 468, "eletivas": 2016, "total": 2484, "extensao": 248}
quadro_ok = p._quadro_integralizacao(
    "BCT", d_ok, 0,
    ["A", "B", "C", "D", "E", "F"],
)
check("com horas completas, tudo verificável fica completo",
      quadro_ok["completo_verificavel"]
      and [c["nome"] for c in quadro_ok["a_confirmar"]] == ["Atividades Complementares"])
r_fmt = {
    "curso": "BCT", "total_matriz": 7, "cursadas": ["x"] * 7,
    "eletivas_cursadas": [], "desconhecidas": [], "pendentes": 0,
    "disponiveis": [], "bloqueadas": [], "semestres_minimos": 0,
    "interdisciplinares_cursadas": ["A", "B", "C", "D", "E", "F"],
    "integralizacao": quadro_ok,
}
texto_fmt = p.formatar_progresso(r_fmt)
check("resposta humanizada abre com a conclusão",
      texto_fmt.startswith("**Quanto falta para você se formar no BCT?**")
      and "tudo o que dá para conferir pelo histórico está completo" in texto_fmt,
      texto_fmt[:250])
check("resposta lista requisito por requisito com folga",
      "✓ **UCs eletivas**: 2016h de 1620h exigidas" in texto_fmt
      and "+396h além do mínimo" in texto_fmt, texto_fmt[:600])
check("AC sinalizadas como a confirmar via SEI",
      "… **Atividades Complementares**" in texto_fmt and "SEI" in texto_fmt)
check("quadro None para curso sem requisitos cadastrados",
      p._quadro_integralizacao("XYZ", d, 0, []) is None)
quadro_bcc = p._quadro_integralizacao("BCC", d, 0, [])
comps_bcc = {c["nome"]: c for c in quadro_bcc["componentes"]}
check("BCC agora tem requisitos oficiais do SIIU (fixas 2484h, TCC a confirmar)",
      comps_bcc["UCs fixas (obrigatórias)"]["exigido"] == 2484
      and comps_bcc["TCC"]["ok"] is None
      and "UCs Eletivas Interdisciplinares" not in comps_bcc,
      str(list(comps_bcc)))
quadro_ec = p._quadro_integralizacao("EC", d, 0, [])
comps_ec = {c["nome"]: c for c in quadro_ec["componentes"]}
check("EC com estágio e TCC a confirmar (3276h fixas, 252h eletivas)",
      comps_ec["UCs fixas (obrigatórias)"]["exigido"] == 3276
      and comps_ec["UCs eletivas"]["exigido"] == 252
      and comps_ec["Estágio obrigatório"]["ok"] is None,
      str(list(comps_ec)))
check("turno do histórico escolhe a matriz certa (BCT noturno)",
      p.requisitos_do_curso("BCT", "INTERDISCIPLINAR EM CIÊNCIA E TECNOLOGIA - NOTURNO")["turno"] == "noturno"
      and p.requisitos_do_curso("BCT", "")["turno"] == "integral")
check("quadro None sem horas no histórico",
      p._quadro_integralizacao("BCT", {"horas": {}}, 0, []) is None)

total = _passed + _failed
cor = GREEN if _failed == 0 else RED
print(f"\n{BOLD}{cor}{_passed}/{total} testes passaram{RESET}\n")
sys.exit(0 if _failed == 0 else 1)
