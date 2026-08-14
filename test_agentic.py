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

print(f"\n{BOLD}2a. Duas atividades na mesma frase ligadas por 'e' (beta tester){RESET}")
itens_e = auditor.parsear_atividades(
    "Sei que tenho 72 horas de doação de sangue e 100 horas de monitoria de AL"
)
check("frase com 'e' vira 2 itens", len(itens_e) == 2, str(itens_e))
r_e = auditor.auditar_atividades(itens_e)
check("eixo I com 72h E eixo II com 100h",
      r_e["horas_validas"][1] == 72 and r_e["horas_validas"][2] == 100,
      str(r_e["horas_validas"]))
itens_tb = auditor.parsear_atividades(
    "40h de palestras e também tenho 30h de curso de inglês"
)
check("'e também tenho' separa itens", len(itens_tb) == 2, str(itens_tb))
check("'Ciência e Tecnologia' no nome não é dividido",
      len(auditor.parsear_atividades("20h de evento de Ciência e Tecnologia na UNIFESP")) == 1)
itens_5 = auditor.parsear_atividades(
    "fiz 72 horas de doação de sangue, 100 horas de monitoria, 80 horas de IC, "
    "20 horas de palestras e 15 horas de teatro na cidade"
)
check("cinco atividades numa frase viram 5 itens", len(itens_5) == 5, str(len(itens_5)))
r_5 = auditor.auditar_atividades(itens_5)
check("os 3 eixos preenchidos a partir da frase única",
      r_5["horas_validas"][1] == 87 and r_5["horas_validas"][2] == 100
      and r_5["horas_validas"][3] == 100, str(r_5["horas_validas"]))
itens_enc = auditor.parsear_atividades(
    "tenho 40h de palestras e 30h de curso de inglês e 20h de teatro e 10h de doação de sangue"
)
check("'e' encadeado quatro vezes separa 4 itens", len(itens_enc) == 4, str(len(itens_enc)))

print(f"\n{BOLD}2b. Acúmulo de atividades na sessão (bug do beta tester){RESET}")
sessao_ac = {}
i1 = auditor.parsear_atividades("eu tenho apenas 72h de doação de sangue")
acum = auditor.registrar_atividades(sessao_ac, i1)
check("primeira declaração registrada na sessão", len(acum) == 1)
i2 = auditor.parsear_atividades("lembrei, tbm tenho 104 horas de monitoria de CVV")
acum = auditor.registrar_atividades(sessao_ac, i2)
check("segunda declaração SOMA com a primeira (não substitui)",
      len(acum) == 2, str(acum))
r_acum = auditor.auditar_atividades(acum)
check("auditoria acumulada: eixo I com 72h E eixo II com 104h",
      r_acum["horas_validas"][1] == 72 and r_acum["horas_validas"][2] == 104,
      str(r_acum["horas_validas"]))
acum = auditor.registrar_atividades(
    sessao_ac, auditor.parsear_atividades("lembrei, tbm tenho 104 horas de monitoria de CVV")
)
check("mesma frase repetida não duplica", len(acum) == 2)
check("detector de reset", auditor.is_reset_ac("zera minhas atividades complementares"))
check("frase comum não reseta", not auditor.is_reset_ac("tenho 40h de monitoria"))
acum = auditor.registrar_atividades(
    sessao_ac, auditor.parsear_atividades("tenho 10h de palestras"), reset=True
)
check("reset descarta as anteriores", len(acum) == 1 and acum[0]["horas"] == 10, str(acum))
check("sessão None degrada para a lista da mensagem",
      len(auditor.registrar_atividades(None, i1)) == 1)

print(f"\n{BOLD}2c. Regras por curso: BBT ≠ BCT{RESET}")
itens_bbt = auditor.parsear_atividades(
    "tenho 40h de projeto de extensão no SIEX da UNIFESP, 30h de monitoria e 50h de iniciação científica"
)
r_bbt = auditor.auditar_atividades(itens_bbt, curso="BBT")
check("BBT: total exigido é 108h", r_bbt["total_exigido"] == 108, str(r_bbt["total_exigido"]))
check("BBT: 120h declaradas cobrem as 108h",
      r_bbt["faltam"] == 0, str(r_bbt["faltam"]))
check("BBT: sem teto de 104h no eixo de extensão",
      not any("teto" in a for a in r_bbt["avisos"]), str(r_bbt["avisos"]))
r_bbt2 = auditor.auditar_atividades(
    auditor.parsear_atividades("tenho 20h de voluntariado na ONG Esperança e 100h de IC"),
    curso="BBT",
)
check("BBT: avisa quando faltam as 36h de SIEX",
      any("SIEX" in a for a in r_bbt2["avisos"]), str(r_bbt2["avisos"]))
check("BBT: sem regra de 2 certificados",
      not any("certificado" in a for a in r_bbt2["avisos"]))
r_bct_ref = auditor.auditar_atividades(itens_bbt, curso="BCT")
check("mesmos itens no BCT usam 312h", r_bct_ref["total_exigido"] == 312)
check("payload usa o alvo do curso",
      auditor.payload_auditoria(r_bbt)["alvo"] == 108
      and auditor.payload_auditoria(r_bct_ref)["alvo"] == 312)
check("rodapé cita o regulamento do BBT",
      "Anexo F" in auditor.formatar_auditoria(r_bbt), auditor.formatar_auditoria(r_bbt)[-200:])

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

print(f"\n{BOLD}8. UCs Eletivas Interdisciplinares (PPC 2023){RESET}")
inter = _mod("src.interdisciplinares", "src/interdisciplinares.py")
ucs = kg.get_interdisciplinares()
check("flag aterrada em 40+ UCs", len(ucs) >= 40, str(len(ucs)))
check("Bioestatística marcada como interdisciplinar",
      kg.is_interdisciplinar("Bioestatística") is True)
check("Desenvolvimento de Games marcada",
      kg.is_interdisciplinar("Desenvolvimento de Games") is True)
check("Cálculo em Uma Variável NÃO é interdisciplinar",
      kg.is_interdisciplinar("Cálculo em Uma Variável") is False)
check("disciplina inexistente retorna None",
      kg.is_interdisciplinar("Disciplina Fantasma XYZ") is None)
lista = inter.responder_lista(kg)
check("lista com chips e regra das 4 UCs",
      lista and "4 UCs" in lista["texto"] and len(lista["chips"]["items"]) >= 40)
check("detector da lista",
      inter.is_lista_interdisciplinares("Quais são as eletivas interdisciplinares?"))
check("extração do check pontual",
      inter.extrair_disciplina_check("Bioestatística é interdisciplinar?") == "bioestatistica")
check("resposta do check afirmativa",
      "Sim" in inter.responder_check(kg, "Bioestatística"))
check("resposta do check negativa",
      "Não" in inter.responder_check(kg, "Cálculo em Uma Variável"))
res_bct = progresso.auditar_progresso(
    kg, "BCT", ["Lógica de Programação", "Probabilidade e Estatística"]
)
check("progresso do BCT conta interdisciplinares cursadas (1 de 4)",
      res_bct["interdisciplinares_cursadas"] == ["Probabilidade e Estatística"],
      str(res_bct["interdisciplinares_cursadas"]))
check("resposta do progresso mostra o placar de interdisciplinares",
      "de 4" in progresso.formatar_progresso(res_bct))

print(f"\n{BOLD}9. Oferta por paridade do termo{RESET}")
oferta = _mod("src.oferta", "src/oferta.py")
from datetime import date as _date

_ago = _date(2026, 8, 15)
_mar = _date(2026, 3, 10)
check("semestre de agosto/2026 é 2026/2", oferta.semestre_de(_ago) == (2026, 2))
check("semestre de março/2026 é 2026/1", oferta.semestre_de(_mar) == (2026, 1))
check("próximo semestre após 2026/2 é 2027/1", oferta.proximo_semestre(_ago) == (2027, 1))
check("próximo semestre após 2026/1 é 2026/2", oferta.proximo_semestre(_mar) == (2026, 2))
check("termo ímpar é ofertado em X/1", oferta.ofertada_em("impar", (2027, 1)) is True)
check("termo par NÃO é ofertado em X/1", oferta.ofertada_em("par", (2027, 1)) is False)
check("paridade desconhecida → None", oferta.ofertada_em(None, (2027, 1)) is None)
check("próxima oferta de termo par visto de 2026/2 é 2027/2",
      oferta.proxima_oferta("par", _ago) == (2027, 2))
check("próxima oferta de termo ímpar visto de 2026/2 é 2027/1",
      oferta.proxima_oferta("impar", _ago) == (2027, 1))
nota = oferta.nota_oferta("par", _ago)
check("nota de oferta avisa que par não abre no próximo semestre",
      nota and "2027/2" in nota and "não no próximo" in nota, str(nota))
nota_ok = oferta.nota_oferta("impar", _ago)
check("nota de oferta confirma ímpar no próximo semestre",
      nota_ok and "2027/1" in nota_ok, str(nota_ok))

check("extração: 'vai ter X no próximo semestre'",
      oferta.extrair_disciplina_oferta("vai ter Compiladores no próximo semestre?")
      == "compiladores")
check("extração: 'X será ofertada semestre que vem?'",
      oferta.extrair_disciplina_oferta("Cálculo em Uma Variável será ofertada semestre que vem?")
      == "calculo em uma variavel")
check("extração: 'em qual semestre tem X?'",
      oferta.extrair_disciplina_oferta("em qual semestre tem Compiladores?")
      == "compiladores")
check("sem gatilho de oferta → None",
      oferta.extrair_disciplina_oferta("quais os pré-requisitos de Compiladores?") is None)

par_calc = kg.paridade_oferta("Cálculo em Uma Variável")
check("Cálculo em Uma Variável tem paridade ímpar (termo 1)",
      par_calc == "impar", str(par_calc))
check("disciplina inexistente → paridade None",
      kg.paridade_oferta("Disciplina Fantasma XYZ") is None)
resp_of = oferta.responder_oferta(kg, "Cálculo em Uma Variável", _ago)
check("resposta de oferta cita semestres ímpares e vale confirmar",
      resp_of and "ímpares" in resp_of and "vale confirmar" in resp_of, str(resp_of)[:200])
check("resposta de oferta prevê o próximo semestre (2027/1) com oferta",
      resp_of and "2027/1" in resp_of and "deve ter oferta" in resp_of, str(resp_of)[:200])

rr_par = risco.analisar_reprovacao(kg, "Cálculo em Uma Variável")
check("análise de risco carrega paridade", rr_par.get("paridade") == "impar",
      str(rr_par.get("paridade")))
texto_rp = risco.formatar_risco(rr_par)
check("risco com paridade conhecida avisa custo de 1 ano",
      "1 ano" in texto_rp and "confirmar" in texto_rp, texto_rp[:200])

vm_of = progresso.verificar_matricula(
    kg, [rr_par["diretos"][0]], ["Cálculo em Uma Variável"]
)
check("parecer de matrícula carrega paridade",
      "paridade" in vm_of["pareceres"][0], str(vm_of["pareceres"][0]))
texto_vm = progresso.formatar_matricula(vm_of)
check("resposta de matrícula menciona oferta esperada quando paridade conhecida",
      "oferta" in texto_vm.lower(), texto_vm[:300])

res_par = progresso.auditar_progresso(kg, "BCC", ["Lógica de Programação"])
check("disponíveis do progresso carregam paridade",
      all("paridade" in d for d in res_par["disponiveis"]),
      str(res_par["disponiveis"][:2]))
texto_pg = progresso.formatar_progresso(res_par)
check("resposta do progresso menciona oferta prevista pela paridade",
      "paridade do termo" in texto_pg, texto_pg[:300])

total = _passed + _failed
cor = GREEN if _failed == 0 else RED
print(f"\n{BOLD}{cor}{_passed}/{total} testes passaram{RESET}\n")
sys.exit(0 if _failed == 0 else 1)
