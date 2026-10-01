"""
Regressões e2e de ROTEAMENTO (backend no ar: FESPAI_URL, default localhost:8000).

Diferente de test_prod_regressions (que só checa não-miss), aqui a resposta
errada NÃO é miss — é uma resposta confiante sobre outra coisa. Cada caso fixa
o agente/intent aceitável e um trecho que a resposta precisa (ou não pode) ter.

Bugs cobertos (01/10/2026):
  - classificadores binários de mundo fechado sem abstenção
    ('tem estágio no BCC' → prazo; 'matriz de EM' → oferta de disciplina);
  - disciplinas_termo sem número de termo → 'Formato inválido';
  - intent de CURSO com entidade DISCIPLINA ('créditos de álgebra linear 2'
    → matriz_info) e créditos só na aresta INCLUI do KG;
  - gate de conflito KG×comunicado no fio da navalha (limiar absoluto).
"""
import os, sys, json, urllib.request

BASE = os.getenv("FESPAI_URL", "http://localhost:8000")
GREEN, RED, RESET = "\033[92m", "\033[91m", "\033[0m"

# (pergunta, agentes aceitos, deve_conter (casefold), nao_pode_conter)
CASOS = [
    ("tem estágio no BCC", None, "estágio", "prazo"),
    ("matriz curricular de engenharia de materiais", {"symbolic_kg"}, "engenharia de materiais", "na oferta de"),
    ("quais disciplinas tem no BCT", {"symbolic_kg"}, "termo", "formato inválido"),
    ("quantos creditos tem algebra linear 2?", {"disciplinas"}, "créditos", "não encontrei"),
    ("quantas horas tem o curso de engenharia de computação", {"symbolic_kg"}, "horas", "prazo para concluir"),
    ("quanto tempo tenho pra terminar o BCT", {"symbolic_kg", "regimentos"}, "prazo", None),
    ("qual a sala de cálculo numérico", {"symbolic_kg"}, "na oferta de", None),
    ("plantão de dúvidas do BCT", {"clarify"}, "comunicado", None),
    ("plantão de dúvidas BCT", {"clarify"}, "comunicado", None),
    ("quando é o plantão de dúvidas do BCT?", {"clarify"}, "comunicado", None),
    ("qual a ementa de compiladores", {"disciplinas"}, "ementa", None),
    ("oi tudo bem", {"conversa"}, None, "comunicado"),
]


def _perguntar(q):
    data = json.dumps({"message": q, "conversation_id": f"e2e-{abs(hash(q))}"}).encode()
    req = urllib.request.Request(BASE + "/chat", data=data,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=180) as r:
        return json.loads(r.read())


ok_n = fail_n = 0
for q, agentes, tem, nao_tem in CASOS:
    try:
        d = _perguntar(q)
        ag, resp = d.get("active_agent", ""), (d.get("response") or "").casefold()
        erros = []
        if agentes and ag not in agentes:
            erros.append(f"agente={ag}")
        if tem and tem.casefold() not in resp:
            erros.append(f"faltou '{tem}'")
        if nao_tem and nao_tem.casefold() in resp:
            erros.append(f"contém '{nao_tem}'")
    except Exception as e:
        ag, erros = "?", [f"ERRO {e}"]
    if erros:
        fail_n += 1
        print(f"{RED}XX {q} -> {ag} ({'; '.join(erros)}){RESET}")
    else:
        ok_n += 1
        print(f"{GREEN}OK{RESET} {q} -> {ag}")

print(f"\n{ok_n} passed, {fail_n} failed (roteamento e2e)")
sys.exit(1 if fail_n else 0)
