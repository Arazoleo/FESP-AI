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

print(f"\n{BOLD}6b. Formato antigo (2025): sem CHEXT, ADE da pandemia, EM CURSO, AC no RESUMO{RESET}")
FIXTURE_2025 = """Curso: INTERDISCIPLINAR EM CIÊNCIA E TECNOLOGIA - INTEGRAL
Ano de ingresso: 2021 Forma de Ingresso: SISTEMA DE SELEÇÃO UNIFICADA
Situação Acadêmica: EM CURSO Coeficiente de Rendimento (CR) Geral: 7.0
ANO/SEM | 2021/1 Coeficiente de Rendimento (CR): 0
Unidade Curricular Cod.
Grupo Tipo UC CH Crédito Freq.
(%) Conceito Situação
9394 - LÓGICA DE PROGRAMAÇÃO
Docente: FULANA DE TAL Titulação: Doutorado 121 DF 72 4 - CUMPRIDO
5704 - QUÍMICA GERAL
Docente: BELTRANA SILVA Titulação: Doutorado 121 DF 72 4 NÃO CUMPRIDO
ANO/SEM | 2022/1 Coeficiente de Rendimento (CR): 7.0
2609 - PROBABILIDADE E ESTATÍSTICA
Docente: CICLANO SOUZA Titulação: Doutorado 182 DE 72 4 90 7,0 APROVADO
ANO/SEM | 2025/2 Coeficiente de Rendimento (CR): 0
2831 - BANCO DE DADOS
Docente: FULANO LIMA Titulação: Doutorado 102 DE 72 4 EM CURSO
RESUMO
Totais de carga horária por tipo de UC
ATIVIDADES COMPLEMENTARES 312
FIXAS 72
ELETIVAS 72
Total de horas cumpridas pelo estudante (teórica + prática) 456
Carga horária extensionista: 96 horas do total cumprido pelo(a) estudante.
"""
d25 = h.parsear_historico(FIXTURE_2025)
check("formato 2025 é parseado", d25 is not None and len(d25["disciplinas"]) == 4,
      str(len(d25["disciplinas"]) if d25 else None))
sit = {x["nome"]: x["situacao"] for x in d25["disciplinas"]}
check("CUMPRIDO, NÃO CUMPRIDO e EM CURSO reconhecidos",
      sit.get("Lógica De Programação") == "CUMPRIDO"
      and sit.get("Química Geral") == "NÃO CUMPRIDO"
      and sit.get("Banco De Dados") == "EM CURSO", str(sit))
check("linha graduada sem CHEXT parseada com nota",
      next(x for x in d25["disciplinas"] if x["nome"] == "Probabilidade E Estatística")["nota"] == 7.0)
check("CUMPRIDO conta como aprovada", "Lógica De Programação" in h.aprovadas(d25))
check("NÃO CUMPRIDO conta como reprovação",
      any(x["nome"] == "Química Geral" for x in h.reprovacoes(d25)))
check("EM CURSO não conta como aprovada", "Banco De Dados" not in h.aprovadas(d25))
check("CR ignora UCs sem nota (só a graduada entra)",
      d25["cr_calculado"] == 7.0, str(d25["cr_calculado"]))
check("UCs EM CURSO viram cursando automático",
      d25.get("cursando") and d25["cursando"][0]["nome"] == "Banco De Dados"
      and d25["cursando"][0]["creditos"] == 4, str(d25.get("cursando")))
check("AC do RESUMO parseadas", d25["horas"].get("ac") == 312, str(d25["horas"]))
check("ano de ingresso extraído", d25.get("ano_ingresso") == 2021)
check("resumo cita AC validadas e UCs em curso",
      "312h de Atividades Complementares" in h.resumo_historico(d25)
      and "em curso" in h.resumo_historico(d25).lower(), h.resumo_historico(d25)[:400])

quadro25 = p._quadro_integralizacao("BCT", d25, 0, ["Probabilidade E Estatística"])
comps25 = {c["nome"]: c for c in quadro25["componentes"]}
check("AC verificadas pelo histórico (312/312 ✓, não mais 'a confirmar')",
      comps25["Atividades Complementares"]["ok"] is True
      and comps25["Atividades Complementares"]["cumprido"] == 312,
      str(comps25["Atividades Complementares"]))
check("extensão dispensada para ingressante 2021",
      comps25["Extensão curricularizada"]["ok"] is True
      and "dispensada" in comps25["Extensão curricularizada"]["obs"],
      str(comps25["Extensão curricularizada"]))
texto25 = p.formatar_progresso({
    "curso": "BCT", "total_matriz": 7, "cursadas": [], "eletivas_cursadas": [],
    "desconhecidas": [], "pendentes": 0, "disponiveis": [], "bloqueadas": [],
    "semestres_minimos": 0, "interdisciplinares_cursadas": [],
    "integralizacao": quadro25,
})
check("formatter não quebra com componente dispensado",
      "dispensada" in texto25, texto25[:300])

print(f"\n{BOLD}6c. Contexto do histórico para os agentes LLM{RESET}")
ctx = h.contexto_para_prompt(d25)
check("bloco marcado como dados do aluno",
      ctx.startswith("[DADOS DO ALUNO"), ctx[:60])
check("aprovadas listadas", "Lógica De Programação" in ctx)
check("reprovações com semestre", "Química Geral (2021/1)" in ctx, ctx)
check("UCs em curso presentes", "EM CURSO" in ctx and "Banco De Dados" in ctx)
check("horas e AC no bloco", "AC validadas 312h" in ctx)
check("CR e ingresso no bloco", "7.0" in ctx and "2021" in ctx)
check("sem histórico retorna vazio",
      h.contexto_para_prompt(None) == "" and h.contexto_para_prompt({}) == "")


class _KGEmentas:
    class _G:
        nodes = {"n1": {"ementa": "Modelagem   de dados, SQL e transações. " * 20}}

    graph = _G()

    def _find_node(self, nome, tipo):
        return "n1" if "banco" in nome.lower() else None


ctx_em = h.contexto_para_prompt(d25, kg=_KGEmentas(), incluir_ementas=True)
check("com incluir_ementas anexa a ementa da UC em curso",
      "Ementa de Banco De Dados:" in ctx_em and "SQL" in ctx_em, ctx_em[-200:])
check("ementa truncada a 280 chars",
      all(len(l) <= 280 + len("Ementa de Banco De Dados: ")
          for l in ctx_em.splitlines() if l.startswith("Ementa de")))
check("sem a flag não anexa ementas",
      "Ementa de" not in h.contexto_para_prompt(d25, kg=_KGEmentas()))

check("pergunta sobre as cursando NÃO vira declaração ('estou cursando agora, qual...')",
      h.extrair_cursando(
          "das disciplinas que estou cursando agora, qual tem mais a ver com redes?"
      ) == [], str(h.extrair_cursando(
          "das disciplinas que estou cursando agora, qual tem mais a ver com redes?")))
check("declaração real segue funcionando",
      h.extrair_cursando("estou cursando Compiladores e Redes esse semestre")
      == ["compiladores", "redes"])

print(f"\n{BOLD}6e. Tudo vira contexto de sessão (varredura){RESET}")
sessao_v = {}
check("declaração 'já cursei X e Y' detectada",
      h.is_cursadas_decl("já cursei Lógica de Programação e Cálculo em Uma Variável"))
check("pergunta com ? não é declaração",
      not h.is_cursadas_decl("já cursei Lógica de Programação?"))
check("frase no meio não dispara (âncora no início)",
      not h.is_cursadas_decl("quero saber se já cursei tudo"))
resp_decl = h.responder_cursadas_decl(
    sessao_v, "já cursei Lógica de Programação e Cálculo em Uma Variável"
)
check("declaração registra 2 disciplinas na sessão",
      len(sessao_v.get("cursadas_declaradas", [])) == 2, str(sessao_v))
check("resposta confirma e ensina os follow-ups",
      "Anotei" in resp_decl and "me formar" in resp_decl)
h.registrar_cursadas_declaradas(sessao_v, ["Lógica de Programação", "Matemática Discreta"])
check("re-declaração deduplica e soma",
      len(sessao_v["cursadas_declaradas"]) == 3, str(sessao_v["cursadas_declaradas"]))
todas_v = h.cursadas_da_sessao({**d25, **sessao_v})
check("cursadas_da_sessao une histórico + declaradas",
      "Lógica De Programação" in todas_v and "Matemática Discreta" in todas_v,
      str(todas_v))
sessao_v["ac_itens"] = [{"descricao": "72h de doação de sangue", "horas": 72.0}]
ctx_v = h.contexto_para_prompt(sessao_v)
check("sessão sem PDF ainda gera contexto (declaradas + AC)",
      ctx_v.startswith("[DADOS DO ALUNO") and "Matemática Discreta" in ctx_v
      and "doação de sangue (72h)" in ctx_v, ctx_v)
check("sessão vazia não gera contexto", h.contexto_para_prompt({}) == "")

d_sem_ac = {**d25, "horas": {k: v for k, v in d25["horas"].items() if k != "ac"},
            "ac_itens": sessao_v["ac_itens"]}
quadro_ac = p._quadro_integralizacao("BCT", d_sem_ac, 0, [])
comp_ac = next(c for c in quadro_ac["componentes"]
               if c["nome"] == "Atividades Complementares")
check("quadro de integralização menciona AC declaradas na conversa",
      "declarou ~72h" in comp_ac["obs"], str(comp_ac))

print(f"\n{BOLD}6d. 'Já cursei X?' respondido direto do histórico{RESET}")
check("extrai o alvo de 'eu já cursei X?'",
      h.extrair_disciplina_cursei("eu já cursei Teoria dos Grafos?") == "teoria dos grafos")
check("extrai de 'já fiz X?'",
      h.extrair_disciplina_cursei("já fiz banco de dados?") == "banco de dados")
check("sem interrogação não intercepta (declaração ≠ pergunta)",
      h.extrair_disciplina_cursei("eu já cursei Cálculo em Uma Variável") is None)
check("pergunta comum não casa",
      h.extrair_disciplina_cursei("quais os pré-requisitos de Compiladores?") is None)
r_ap = h.responder_cursei(d25, "lógica de programação")
check("aprovada responde Sim com semestre",
      "Sim!" in r_ap and "2021/1" in r_ap, r_ap)
r_rep = h.responder_cursei(d25, "química geral")
check("reprovada avisa que precisa cursar de novo",
      "cursar de novo" in r_rep, r_rep)
r_ec = h.responder_cursei(d25, "banco de dados")
check("em curso é reportada como em curso",
      "em curso" in r_ec.lower(), r_ec)
r_nao = h.responder_cursei(d25, "libras")
check("ausente responde que não consta",
      "não aparece" in r_nao, r_nao)

print(f"\n{BOLD}7. Requisitos de integralização por pergunta direta{RESET}")
check("detecta 'quantas horas preciso para me formar'",
      p.is_requisitos_request("Quantas horas eu preciso para me formar em Engenharia de Computação?"))
check("detecta 'carga horária para integralizar'",
      p.is_requisitos_request("qual a carga horária para integralizar o BCT?"))
check("não dispara em pergunta de progresso pessoal",
      not p.is_requisitos_request("quanto falta para me formar?"))
check("não dispara em pergunta de AC genérica",
      not p.is_requisitos_request("o que são atividades complementares?"))
check("extrai sigla de nome por extenso",
      p.extrair_curso_requisitos("quantas horas para me formar em Engenharia de Computação?") == "EC")
check("extrai sigla direta",
      p.extrair_curso_requisitos("requisitos de integralização do bcc") == "BCC")
resp_req = p.responder_requisitos("EC")
check("resposta da EC traz total, estágio e TCC",
      "3960" in resp_req and "Estágio obrigatório" in resp_req
      and "180h" in resp_req and "SIIU" in resp_req, resp_req[:300])
resp_bct = p.responder_requisitos("BCT", "NOTURNO")
check("resposta do BCT inclui extras do PPC (extensão e interdisciplinares)",
      "240h" in resp_bct and "4 UCs" in resp_bct, resp_bct[:300])
check("sigla desconhecida retorna None", p.responder_requisitos("XYZ") is None)
check("quadro None sem horas no histórico",
      p._quadro_integralizacao("BCT", {"horas": {}}, 0, []) is None)

total = _passed + _failed
cor = GREEN if _failed == 0 else RED
print(f"\n{BOLD}{cor}{_passed}/{total} testes passaram{RESET}\n")
sys.exit(0 if _failed == 0 else 1)
