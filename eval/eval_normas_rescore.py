"""
Recalcula acordo e taxa de violação das formalizações já salvas (.lp), sem
chamar LLM — para quando o banco de cenários ou a formalização manual mudam.

Uso: .venv-normas/bin/python eval/eval_normas_rescore.py --out eval/normas_out/com_contratos
"""

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "eval"))

from normas import Motor  # noqa: E402
from normas.autoformalizar import combinar  # noqa: E402
from normas.cenarios import gerar  # noqa: E402
from normas.grupos import POR_NOME  # noqa: E402
from eval_normas_autoformalizacao import comparar, taxa_violacao  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--cenarios", type=int, default=300)
    a = ap.parse_args()
    base, cenarios = Motor(), gerar(a.cenarios)
    for js in sorted(Path(a.out).glob("*__*.json")):
        if js.name.startswith("resumo"):
            continue
        d = json.loads(js.read_text(encoding="utf-8"))
        if d.get("valida"):
            g = POR_NOME[d["grupo"]]
            motor = combinar(base, g, js.with_suffix(".lp").read_text(encoding="utf-8"))
            d.update(comparar(base, motor, g, cenarios))
            d["taxa_violacao_contrato"] = taxa_violacao(motor, g, cenarios)
            js.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
        print(d["modelo"], d["grupo"], d.get("acordo_total"), d.get("taxa_violacao_contrato"), flush=True)


if __name__ == "__main__":
    main()
