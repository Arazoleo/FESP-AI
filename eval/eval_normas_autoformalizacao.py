"""
Piloto: autoformalização da Res. CONSU 246/2023 (+ Portaria 566/2022) por LLM.

Para cada (modelo, grupo de normas):
  1. o LLM formaliza os dispositivos em ASP, com até N rodadas de reparo
     guiadas SÓ pelo verificador simbólico (sintaxe, contrato de saída,
     vocabulário, execução) — sem gabarito no laço;
  2. a formalização válida substitui o grupo correspondente da formalização
     manual (upstream manual = erro atribuído ao grupo certo);
  3. as conclusões de saída são comparadas com as da formalização manual em
     cenários sintéticos (métrica de DESENVOLVIMENTO: a manual não é gabarito).

Uso (venv com clingo: .venv-normas):
  .venv-normas/bin/python eval/eval_normas_autoformalizacao.py \
      --modelos gemma4:31b-cloud --grupos all --cenarios 300
"""

import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from normas import Motor  # noqa: E402
from normas.autoformalizar import autoformalizar, com_contratos, combinar, violacoes  # noqa: E402
from normas.cenarios import gerar  # noqa: E402
from normas.grupos import GRUPOS, POR_NOME  # noqa: E402

OUT = ROOT / "eval/normas_out"


def taxa_violacao(motor, grupo, cenarios):
    """Fração de cenários com alguma violação de contrato (métrica sem gabarito)."""
    if not grupo.contratos:
        return None
    mc = com_contratos(motor, grupo)
    ruins = 0
    for aluno in cenarios:
        try:
            ruins += bool(violacoes(mc, aluno))
        except (RuntimeError, ValueError):
            ruins += 1
    return round(ruins / len(cenarios), 3)


def saidas(resultado, grupo):
    por_pred = {}
    for sig in grupo.saidas:
        nome, ar = sig.split("/")
        por_pred[sig] = sorted(str(a) for a in resultado.atomos
                               if a.name == nome and len(a.arguments) == int(ar))
    return por_pred


def comparar(base, motor_auto, grupo, cenarios):
    acordo = {s: 0 for s in grupo.saidas}
    divergencias, falhas = [], 0
    for i, aluno in enumerate(cenarios):
        fatos = aluno.fatos()
        ref = saidas(base.avaliar(fatos), grupo)
        try:
            got = saidas(motor_auto.avaliar(fatos), grupo)
        except (RuntimeError, ValueError) as e:
            falhas += 1
            divergencias.append({"cenario": i, "erro": str(e)[:300]})
            continue
        for s in grupo.saidas:
            if ref[s] == got[s]:
                acordo[s] += 1
            elif len(divergencias) < 40:
                divergencias.append({"cenario": i, "saida": s,
                                     "manual": ref[s], "auto": got[s],
                                     "fatos": fatos})
    n = len(cenarios)
    return {"n": n, "falhas_execucao": falhas,
            "acordo": {s: round(v / n, 3) for s, v in acordo.items()},
            "acordo_total": round(sum(acordo.values()) / (n * len(acordo)), 3),
            "divergencias": divergencias}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--modelos", default="gemma4:31b-cloud")
    ap.add_argument("--grupos", default="all")
    ap.add_argument("--cenarios", type=int, default=300)
    ap.add_argument("--tentativas", type=int, default=3)
    ap.add_argument("--sem-contratos", action="store_true",
                    help="ablação: reparo só com sintaxe/vocabulário/execução")
    ap.add_argument("--out", default=str(OUT))
    a = ap.parse_args()
    out = Path(a.out)

    base = Motor()
    cenarios = gerar(a.cenarios)
    verif = cenarios[:25]
    grupos = GRUPOS if a.grupos == "all" else [POR_NOME[g] for g in a.grupos.split(",")]
    out.mkdir(parents=True, exist_ok=True)

    resumo = []
    for modelo in a.modelos.split(","):
        for g in grupos:
            t0 = time.time()
            f = autoformalizar(g, modelo, base, verif, a.tentativas, not a.sem_contratos)
            tag = f"{modelo.replace(':', '_').replace('/', '_')}__{g.nome}"
            (out / f"{tag}.lp").write_text(f.programa or "", encoding="utf-8")
            linha = {"modelo": modelo, "grupo": g.nome, "valida": f.valida,
                     "tentativas": len(f.tentativas),
                     "erros_por_tentativa": [t.erros for t in f.tentativas],
                     "segundos": round(time.time() - t0, 1)}
            if f.valida:
                motor = combinar(base, g, f.programa)
                linha.update(comparar(base, motor, g, cenarios))
                linha["taxa_violacao_contrato"] = taxa_violacao(motor, g, cenarios)
            (out / f"{tag}.json").write_text(json.dumps(linha, ensure_ascii=False, indent=1),
                                             encoding="utf-8")
            resumo.append({k: v for k, v in linha.items() if k not in ("divergencias", "erros_por_tentativa")})
            print(json.dumps(resumo[-1], ensure_ascii=False), flush=True)

    (out / f"resumo__{a.modelos.replace(':', '_').replace(',', '+')}.json").write_text(json.dumps(resumo, ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
