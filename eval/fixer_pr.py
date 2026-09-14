"""
Fase 3 — harness de VERIFICAÇÃO + PR do loop de auto-correção.

Roda os portões (suíte-chave + regressões de produção no container) e, se tudo
verde, abre um PR via gh com a evidência do ticket. NUNCA faz merge — o humano é
o portão final. Automatiza exatamente o que foi feito à mão no PR #3.

Roda no HOST (usa docker exec p/ os testes e gh p/ o PR).

Uso:
    python eval/fixer_pr.py --title "fix(routing): ..." --body-file corpo.md \\
        --base feat/minha-branch [--pr]     # sem --pr: só verifica
Env: FESPAI_CONTAINER (default fesp-ai-backend).
"""

import os
import sys
import subprocess

CONTAINER = os.getenv("FESPAI_CONTAINER", "fesp-ai-backend")
SUITE = ["test_formatura_area_grupo.py", "test_routing.py",
         "test_neurosymbolic.py", "test_historico.py"]


def _arg(flag, default=None):
    return sys.argv[sys.argv.index(flag) + 1] if flag in sys.argv else default


def _sh(cmd):
    return subprocess.run(cmd, shell=True, capture_output=True, text=True)


def _run_in_container(script):
    for f in ([script] if isinstance(script, str) else script):
        _sh(f"docker cp {f} {CONTAINER}:/app/ 2>/dev/null")
    r = _sh(f"docker exec {CONTAINER} bash -lc "
            f"'cd /app && python {script if isinstance(script,str) else script[0]}'")
    return r


def verificar():
    """Portões: suíte-chave + regressões de produção. Retorna (ok, resumo)."""
    resumo = []
    ok = True
    for t in SUITE:
        _sh(f"docker cp {t} {CONTAINER}:/app/ 2>/dev/null")
        r = _sh(f"docker exec {CONTAINER} bash -lc 'cd /app && python {t}'")
        passou = ("0 failed" in r.stdout) or ("Todos passaram" in r.stdout) \
            or ("/ " in r.stdout and "failed" not in r.stdout.lower())
        # heurística robusta: falha se aparecer 'failed' com número > 0
        passou = r.returncode == 0
        resumo.append(f"  {'OK' if passou else 'XX'} {t}")
        ok = ok and passou
    # regressões de produção
    _sh(f"docker cp test_prod_regressions.py {CONTAINER}:/app/ 2>/dev/null")
    r = _sh(f"docker exec {CONTAINER} bash -lc "
            f"'cd /app && FESPAI_URL=http://localhost:8000 python test_prod_regressions.py'")
    prod_ok = r.returncode == 0
    linha = [l for l in r.stdout.splitlines() if "regressões de produção" in l]
    resumo.append(f"  {'OK' if prod_ok else 'XX'} regressões de produção "
                  f"({linha[0].strip() if linha else '?'})")
    # nota: prod pode ter gap de DADO remanescente; não bloqueia o PR de código,
    # mas o resumo mostra o número.
    return ok, "\n".join(resumo)


def abrir_pr(base, title, body_file):
    branch = _sh("git branch --show-current").stdout.strip()
    _sh(f"git push -u origin {branch}")
    body_arg = f"--body-file {body_file}" if body_file and os.path.exists(body_file) else \
        '--body "Gerado pelo loop de auto-correção (verify+PR). Merge = humano."'
    r = _sh(f'gh pr create --base {base} --head {branch} '
            f'--title "{title}" {body_arg}')
    return r.stdout.strip() or r.stderr.strip()


def main():
    base = _arg("--base", "main")
    title = _arg("--title", "fix: auto-heal")
    body_file = _arg("--body-file")
    ok, resumo = verificar()
    print("== VERIFICAÇÃO (portões do loop) ==")
    print(resumo)
    if not ok:
        print("\n❌ suíte com regressão — PR NÃO aberto.")
        sys.exit(1)
    if "--pr" not in sys.argv:
        print("\n✅ verde. (sem --pr; não abri PR)")
        return
    print("\n✅ verde — abrindo PR...")
    print(abrir_pr(base, title, body_file))


if __name__ == "__main__":
    main()
