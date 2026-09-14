"""
AUTO-GERADO por eval/gen_prod_tests.py — NÃO editar à mão.

Suíte de regressão dirigida por PRODUÇÃO: cada caso é uma pergunta que falhou
(miss) em produção; o backend deve agora dar uma resposta ATERRADA (não-miss).
Requer o backend no ar (FESPAI_URL, default http://localhost:8000). O oráculo de
miss é o mesmo do runtime.
"""
import os, sys, json, urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from src.workflow.second_chance import is_miss_response

BASE = os.getenv("FESPAI_URL", "http://localhost:8000")
GREEN, RED, RESET = "\033[92m", "\033[91m", "\033[0m"
_passed = _failed = 0

# (pergunta, frequencia_em_producao)
CASOS = [('quero trancar o semestre', 6), ('onde vejo minhas notas?', 6), ('Qual os professores de rpvmm?', 6), ('quanto tempo dura a graduação?', 5), ('Tem algum professor que trabalha com Redes Complexas?', 5), ('quantos creditos tem algebra linear 2?', 5), ('qual o prazo maximo de integralizacao do BCC?', 4), ('Quais disciplinas o professor Sanderson leciona?', 3), ('Quem é Leonardo Arazo', 3), ('como me inscrevo nesse congresso', 3)]


def _perguntar(q):
    data = json.dumps({"message": q, "conversation_id": f"prodreg-{abs(hash(q))}"}).encode()
    req = urllib.request.Request(BASE + "/chat", data=data,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=90) as r:
        return json.loads(r.read())


for q, freq in CASOS:
    try:
        d = _perguntar(q)
        resp = d.get("response", "")
        ok = bool(resp) and not is_miss_response(resp)
    except Exception as e:
        ok, d = False, {"active_agent": f"ERRO {e}"}
    if ok:
        _passed += 1
        print(f"{GREEN}OK{RESET} [{freq}x] {q[:52]} -> {d.get('active_agent')}")
    else:
        _failed += 1
        print(f"{RED}XX [{freq}x] {q[:52]} -> {d.get('active_agent')}{RESET}")

print(f"\n{_passed} passed, {_failed} failed "
      f"(regressões de produção)")
sys.exit(1 if _failed else 0)
