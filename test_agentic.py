"""
Testes das capacidades agênticas: auditor de AC, checklist SEI, auditoria de
progresso, pré-verificação de matrícula, risco de reprovação e trilhas por
objetivo. Regras aplicadas como código sobre o Knowledge Graph real.

Executa sem LLM/backend.
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


def _mod(name, path):
    spec = importlib.util.spec_from_file_location(name, ROOT / path)
    m = importlib.util.module_from_spec(spec)
    m.__package__ = "src"
    sys.modules[name] = m
    spec.loader.exec_module(m)
    return m


kgm = _mod("src.knowledge_graph", "src/knowledge_graph.py")
auditor = _mod("src.ac_auditor", "src/ac_auditor.py")
progresso = _mod("src.progresso", "src/progresso.py")
risco = _mod("src.risco", "src/risco.py")
trilhas = _mod("src.trilhas", "src/trilhas.py")

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


print(f"\n{BOLD}1. Auditor de AC: classificação de eixo{RESET}")
casos = [
    ("40h de monitoria de Cálculo", 2),
    ("doação de sangue", 1),
    ("80h de curso de inglês", 3),
    ("120h de iniciação científica", 3),
    ("participei do centro acadêmico", 1),
    ("estágio não obrigatório na Embraer", 3),
    ("teatro na cidade", 1),
    ("recepção de calouros", 2),
]
for desc, eixo in casos:
    c = auditor.classificar_eixo(desc)
    check(f"'{desc}' → eixo {eixo}", bool(c) and c["eixo"] == eixo, str(c))
check("descrição sem casamento retorna None",
      auditor.classificar_eixo("assisti série no sofá") is None)

print(f"\n{BOLD}2. Auditor de AC: parser e regras{RESET}")
texto = ("40h de monitoria; 200h de teatro; 80h de curso de inglês na Cultura Inglesa; "
         "50h de curso online na Alura; 30h de curso de espanhol na Alura; 20h de palestras na Alura")
itens = auditor.parsear_atividades(texto)
check("parser extrai 6 itens com horas", len(itens) == 6, str(len(itens)))
r = auditor.auditar_atividades(itens)
check("teto do eixo I aplicado (200h → 104h)",
      r["horas_brutas"][1] == 200 and r["horas_validas"][1] == 104, str(r["horas_validas"]))
check("aviso de excedente do eixo I", any("104" in a for a in r["avisos"]))
check("regra de 2 certificados por instituição (3 da Alura)",
      any("alura" in a.lower() for a in r["avisos"]), str(r["avisos"]))
check("total e faltantes coerentes",
      r["total_valido"] == 104 + 40 + 180 and r["faltam"] == max(0, 312 - r["total_valido"]),
      str(r["total_valido"]))
r2 = auditor.auditar_atividades(auditor.parsear_atividades("400h de iniciação científica"))
check("mínimo por eixo: pendências para eixos I e II zerados",
      len(r2["pendencias"]) == 2, str(r2["pendencias"]))
check("sem itens → resposta pede a lista formatada",
      "liste" in auditor.responder_auditoria("audita minhas atividades complementares").lower())

print(f"\n{BOLD}3. Detectores do auditor e checklist{RESET}")
check("detecta auditoria com horas + AC",
      auditor.is_audit_request("Tenho 40h de monitoria e 100h de IC, quanto tenho de AC?"))
check("não dispara em pergunta conceitual",
      not auditor.is_audit_request("O que são atividades complementares?"))
check("detecta checklist",
      auditor.is_checklist_request("Estou pronto para enviar minhas AC?"))
check("checklist cita SA02 e histórico sem assinatura",
      "SA02" in auditor.responder_checklist()
      and "SEM assinatura" in auditor.responder_checklist())

print(f"\n{BOLD}4. Progresso: KG real{RESET}")
kg = kgm.KnowledgeGraph()
import io, contextlib
with contextlib.redirect_stdout(io.StringIO()):
    kg.build_from_directories(
        "markdown_disciplinas", "markdown_regimentos",
        "markdown_docentes", "markdown_cursos",
    )
res = progresso.auditar_progresso(
    kg, "BCC",
    ["Lógica de Programação", "Cálculo em Uma Variável", "Disciplina Inventada QQQ"],
)
check("auditoria roda para o BCC", res is not None)
check("cursadas reconhecidas (2 de 3)", len(res["cursadas"]) == 2, str(res["cursadas"]))
check("disciplina inventada reportada", res["desconhecidas"] == ["Disciplina Inventada QQQ"])
check("pendentes = matriz - cursadas",
      res["pendentes"] == res["total_matriz"] - len(res["cursadas"]))
nomes_disp = {d["nome"] for d in res["disponiveis"]}
check("AED I liberada após Lógica de Programação",
      any("Estruturas de Dados I" in n for n in nomes_disp), str(sorted(nomes_disp))[:150])
nomes_bloq = {d["nome"]: d["faltando"] for d in res["bloqueadas"]}
check("Compiladores bloqueada com pré-requisito nomeado",
      any("Compiladores" == n for n in nomes_bloq),
      str({k: v for k, v in nomes_bloq.items() if k == "Compiladores"}))
check("semestres mínimos é plausível (2 a 12)",
      2 <= res["semestres_minimos"] <= 12, str(res["semestres_minimos"]))

print(f"\n{BOLD}5. Pré-verificação de matrícula{RESET}")
vm = progresso.verificar_matricula(
    kg,
    ["Compiladores", "Lógica de Programação"],
    ["Lógica de Programação", "Matemática Discreta"],
)
por_disc = {p["disciplina"]: p for p in vm["pareceres"]}
check("Compiladores em risco por pré-requisito",
      por_disc["Compiladores"]["status"] == "risco"
      and any("pré-requisito" in m for m in por_disc["Compiladores"]["motivos"]))
check("UC já cursada flagrada",
      any("já cursada" in m for m in por_disc["Lógica de Programação"]["motivos"]))
check("extração de desejadas e cursadas da frase",
      progresso.extrair_desejadas(
          "Posso me matricular em Compiladores e Redes tendo cursado AED I?"
      ) == ["Compiladores", "Redes"])
check("detector de matrícula",
      progresso.is_matricula_request("Posso me matricular em Compiladores tendo cursado AED I?"))

vm2 = progresso.verificar_matricula(
    kg, ["Inteligência Artificial"],
    ["Lógica de Programação", "Algoritmos e Estruturas de Dados I",
     "Algoritmos e Estruturas de Dados II", "Matemática Discreta"],
)
p_ia = vm2["pareceres"][0]
check("R6 na matrícula: IA aponta base recomendada pendente (probabilidade)",
      any("Probabilidade" in b for b in p_ia["base_pendente"]),
      str(p_ia["base_pendente"]))
check("aviso de base aparece na resposta formatada",
      "base recomendada" in progresso.formatar_matricula(vm2))

pay = auditor.payload_auditoria(auditor.auditar_atividades(
    auditor.parsear_atividades("40h de monitoria; 200h de teatro; 100h de IC")
))
check("payload do auditor: 3 eixos com teto no eixo I",
      pay["type"] == "ac_report" and len(pay["eixos"]) == 3
      and pay["eixos"][0]["teto"] == 104 and pay["eixos"][0]["validas"] == 104)
check("payload traz total e faltantes",
      pay["total"] == 244 and pay["faltam"] == 68, str(pay))
check("detector de progresso",
      progresso.is_progresso_request("Já cursei Cálculo, quanto falta para me formar?"))
check("detector de progresso pega 'o que falta p me formar'",
      progresso.is_progresso_request("tenho 200h de doação de sangue, o que falta p me formar?"))
check("auditor cede prioridade quando a pergunta é sobre formar",
      not auditor.is_audit_request("tenho 200h de doação de sangue, o que falta p me formar?"))
check("auditor pega horas de atividade reconhecível mesmo sem a palavra AC",
      auditor.is_audit_request("tenho 200h de doação de sangue e 40h de monitoria, quanto já tenho?"))

print(f"\n{BOLD}6. Risco de reprovação{RESET}")
rr = risco.analisar_reprovacao(kg, "Lógica de Programação")
check("Lógica de Programação tem dependentes diretos", len(rr["diretos"]) >= 2, str(rr["diretos"])[:120])
check("marcada como crítica (R3)", rr["critica"])
check("cadeia transitiva maior que direta", len(rr["transitivos"]) >= len(rr["diretos"]))
texto_r = risco.formatar_risco(rr)
check("resposta cita bloqueio e regra", "Bloqueio imediato" in texto_r and "critical_node" in texto_r)
check("extração da disciplina do texto",
      risco.extrair_disciplina_risco("o que acontece se eu reprovar em Cálculo em Uma Variável?")
      == "calculo em uma variavel")
check("sem gatilho de risco → None",
      risco.extrair_disciplina_risco("quais os pré-requisitos de Cálculo?") is None)

print(f"\n{BOLD}7. Trilhas por objetivo{RESET}")
tr = trilhas.montar_trilha(kg, "Quero trabalhar com aprendizado de máquina, que disciplinas devo fazer?")
check("trilha montada", tr is not None)
check("conceitos detectados",
      any("aprendizado de máquina" in c for c in tr["conceitos"]), str(tr["conceitos"]))
nomes_tr = {d["nome"] for d in tr["disciplinas"]}
check("disciplinas de IA/ML na trilha",
      any("Intelig" in n or "Aprendizado" in n for n in nomes_tr), str(sorted(nomes_tr))[:150])
check("docentes sugeridos para a área",
      any("Berton" in n for n in tr["docentes"]), str(list(tr["docentes"])[:4]))
check("objetivo sem conceito conhecido → None",
      trilhas.montar_trilha(kg, "quero trabalhar com culinária vegana") is None)
check("detector de trilha",
      trilhas.is_trilha_request("quero seguir carreira em ciência de dados"))

total = _passed + _failed
cor = GREEN if _failed == 0 else RED
print(f"\n{BOLD}{cor}{_passed}/{total} testes passaram{RESET}\n")
sys.exit(0 if _failed == 0 else 1)
