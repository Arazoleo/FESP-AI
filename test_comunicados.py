"""
Testes do módulo de comunicados por email (src/comunicados.py), sem LLM nem
embeddings: janela de tempo, parsing do .md e listagem por data.
"""
import sys, tempfile
import importlib.util
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).parent
spec = importlib.util.spec_from_file_location("comunicados", ROOT / "src/comunicados.py")
cm = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cm)

GREEN, RED, BOLD, RESET = "\033[92m", "\033[91m", "\033[1m", "\033[0m"
_p = _f = 0


def check(desc, cond, detail=""):
    global _p, _f
    if cond:
        _p += 1; print(f"{GREEN}✓{RESET} {desc}")
    else:
        _f += 1; print(f"{RED}✗ {desc}{RESET}" + (f" - {detail}" if detail else ""))


AGORA = datetime(2026, 10, 2, 13, 0)
print(f"{BOLD}── janela de tempo ──{RESET}")
for q, ini, rot in [
    ("oq tem no email hj", datetime(2026, 10, 2), "hoje"),
    ("o que tem no email hoje?", datetime(2026, 10, 2), "hoje"),
    ("o que chegou ontem?", datetime(2026, 10, 1), "ontem"),
    ("avisos dessa semana", datetime(2026, 9, 26), "7 dias"),
    ("comunicados de 18/08", datetime(2026, 8, 18), "18/08"),
    ("últimos 3 dias", datetime(2026, 9, 30), "3 dias"),
]:
    i, f, r = cm.janela(q, AGORA)
    check(f"'{q}' → início {ini:%d/%m}", i == ini and rot in r, f"{i} {r}")
check("sem expressão de tempo → sem janela", cm.janela("tem estágio novo?", AGORA)[0] is None)

print(f"\n{BOLD}── parsing e listagem ──{RESET}")
MD = """# Comunicado institucional: Fwd: Super Estágios – Nova Oportunidade

> Fonte: email institucional UNIFESP (comunicado em massa a lista de alunos).
> Remetente: "Divisão de Assuntos Educacionais" <dae.sjc@unifesp.br>
> Lista: conecta.digr.ict
> Data: {data}
> Esta é uma fonte externa (não validada pelo KG).

## Conteúdo

---------- Forwarded message ---------
De: 'adm@exemplo.com'
A Super Estágios apresenta uma nova vaga de estágio para estudantes de engenharia.
"""
with tempfile.TemporaryDirectory() as d:
    d = Path(d)
    (d / "2026-10-01_super-estagios_aaaa.md").write_text(MD.format(data="01/10/2026 17:36"), encoding="utf-8")
    (d / "2026-10-02_biblioteca_bbbb.md").write_text(
        MD.format(data="02/10/2026 11:11").replace("Super Estágios – Nova Oportunidade", "Acervo atualizado"),
        encoding="utf-8")
    cm.DIR = d
    cm.SYNC_FILE = d / ".ultima_sync"
    cm._cache.update(chave=None, itens=[])
    itens = cm.carregar()
    check("lê os 2 comunicados, mais recente primeiro", [i["titulo"] for i in itens] ==
          ["Acervo atualizado", "Super Estágios – Nova Oportunidade"], str([i["titulo"] for i in itens]))
    check("tira 'Fwd:' do título e <email> do remetente",
          itens[1]["titulo"].startswith("Super") and itens[1]["remetente"] == "Divisão de Assuntos Educacionais")
    check("resumo pula cabeçalho de encaminhamento", itens[1]["resumo"].startswith("A Super Estágios"), itens[1]["resumo"])
    r = cm.responder("oq tem no email hj", agora=AGORA)
    check("'hj' lista só o de hoje", r and [i["titulo"] for i in r["itens"]] == ["Acervo atualizado"],
          str(r and [i["titulo"] for i in r["itens"]]))
    check("fontes citam o comunicado com data", r and r["fontes"][0].startswith("Comunicado: Acervo atualizado") and "02/10/2026" in r["fontes"][0])
    check("rodapé deixa claro que não lê email pessoal", r and "não leio email pessoal" in r["texto"])
    r = cm.responder("comunicados de 15/09", agora=AGORA)
    check("janela vazia → diz que não chegou e mostra os mais recentes",
          r and r["texto"].startswith("Não chegou nenhum comunicado") and "Acervo atualizado" in r["texto"])

    print(f"\n{BOLD}── follow-up (sem embeddings) ──{RESET}")
    lst = cm.carregar()
    check("'o segundo' escolhe o 2º listado", cm.escolher("o segundo", lst) == [lst[1]])
    check("'detalhe o primeiro' escolhe o 1º", cm.escolher("detalhe o primeiro", lst) == [lst[0]])
    check("'o último' escolhe o último", cm.escolher("e o último?", lst) == [lst[-1]])
    check("ordinal fora da lista → nenhum", cm.escolher("o quinto", lst) == [])
    check("sem ordinal nem modelo → nenhum", cm.escolher("detalhe mais", lst) == [])
    check("texto completo tira link de rastreamento",
          "http" not in cm.texto_completo(lst[0]) or "t.rdsv2" not in cm.texto_completo(lst[0]))
    check("detalhar sem LLM devolve o texto bruto com fonte",
          (cm.detalhar("detalhe", [lst[0]], None) or {}).get("fontes", [""])[0].startswith("Comunicado:"))

print(f"\n{BOLD}{_p} passed, {_f} failed{RESET}")
sys.exit(1 if _f else 0)
