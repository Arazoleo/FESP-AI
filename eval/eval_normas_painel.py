"""
Painel de autoformalizações: a discordância entre formalizações independentes
prevê o erro?

Para cada grupo de normas, cada modelo com formalização válida (saída de
eval_normas_autoformalizacao.py) "vota" nas conclusões de cada cenário. Os
votos viram o intervalo de crença do HNKGA:

    l = sim / n        u = 1 - não / n       (n = modelos do painel)

Formalização inválida não vota (alarga o intervalo). A resposta do painel é a
maioria; a análise cruza o nível de concordância com o acerto em relação à
formalização manual (referência de DESENVOLVIMENTO, não gabarito).

Uso: .venv-normas/bin/python eval/eval_normas_painel.py --cenarios 300
"""

import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "eval"))

from normas import Motor  # noqa: E402
from normas.autoformalizar import combinar  # noqa: E402
from normas.cenarios import gerar  # noqa: E402
from normas.grupos import GRUPOS  # noqa: E402
from eval_normas_autoformalizacao import OUT, saidas  # noqa: E402


def carregar(OUT=OUT):
    """{grupo: {modelo: programa}} só com formalizações válidas."""
    painel = defaultdict(dict)
    modelos = set()
    for js in OUT.glob("*__*.json"):
        if js.name.startswith("resumo"):
            continue
        d = json.loads(js.read_text(encoding="utf-8"))
        modelos.add(d["modelo"])
        if d.get("valida"):
            painel[d["grupo"]][d["modelo"]] = js.with_suffix(".lp").read_text(encoding="utf-8")
    return painel, sorted(modelos)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cenarios", type=int, default=300)
    ap.add_argument("--out", default=str(OUT))
    a = ap.parse_args()
    out = Path(a.out)

    base = Motor()
    cenarios = gerar(a.cenarios)
    painel, modelos = carregar(out)
    n_painel = len(modelos)
    rel = {"modelos": modelos, "grupos": {}}

    for g in GRUPOS:
        progs = painel.get(g.nome, {})
        motores = {m: combinar(base, g, p) for m, p in progs.items()}
        faixas = defaultdict(lambda: Counter())
        larguras = []
        for aluno in cenarios:
            fatos = aluno.fatos()
            ref = saidas(base.avaliar(fatos), g)
            votos = {}
            for m, mot in motores.items():
                try:
                    votos[m] = saidas(mot.avaliar(fatos), g)
                except (RuntimeError, ValueError):
                    pass
            for s in g.saidas:
                # cada conjunto de átomos distinto é uma "resposta"; maioria vence
                respostas = Counter(json.dumps(v[s]) for v in votos.values())
                if not respostas:
                    faixas["sem_painel"]["n"] += 1
                    continue
                maioria, k = respostas.most_common(1)[0]
                certo = json.loads(maioria) == ref[s]
                faixa = "unanime" if k == n_painel else ("maioria" if k > n_painel / 2 else "dividido")
                faixas[faixa]["n"] += 1
                faixas[faixa]["certo"] += int(certo)
                # intervalo da resposta majoritária: sim = k, não = votos válidos que divergem
                l, u = k / n_painel, 1 - (len(votos) - k) / n_painel
                larguras.append(u - l)
        rel["grupos"][g.nome] = {
            "modelos_validos": sorted(progs),
            "faixas": {f: {"n": c["n"], "acerto": round(c["certo"] / c["n"], 3) if c["n"] else None}
                       for f, c in faixas.items()},
            "largura_media_intervalo": round(sum(larguras) / len(larguras), 3) if larguras else None,
        }
        print(g.nome, json.dumps(rel["grupos"][g.nome], ensure_ascii=False), flush=True)

    (out / "painel.json").write_text(json.dumps(rel, ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
