"""
Precisão/recall da checagem de cobertura (src/workflow/coverage.py).

Produção quase não grava resposta incompleta, então os casos são montados:
o LLM escreve respostas naturais a partir de fatos do KG, em duas versões.

- COMPLETA (negativo): recebe os fatos de TODAS as entidades da pergunta.
  Mede o alarme falso principal: resposta correta que não repete o nome.
- INCOMPLETA (positivo): pergunta com 2 entidades, o LLM só recebe os fatos
  da primeira e responde sem comentar o que falta (falha silenciosa).

Perguntas: as reais do interactions.jsonl que citam entidade do KG, mais
compostas sintéticas (pares de entidades reais em modelos de pergunta).
Não toca no backend nem nos logs de produção; usa o Ollama local.

    python3 eval/eval_cobertura.py [--log chroma_db_unifesp/interactions.jsonl]
        [--modelo gemma4:31b-cloud] [--n-sinteticas 30]
    python3 eval/eval_cobertura.py --rescore eval/cobertura_out/cobertura__X.json
        # reavalia as MESMAS respostas com o detector atual (sem LLM)
"""

import argparse
import importlib.util
import json
import os
import random
import sys
import types
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def _imp(name, path):
    if "src" not in sys.modules:
        pkg = types.ModuleType("src")
        pkg.__path__ = [str(ROOT / "src")]
        sys.modules["src"] = pkg
    spec = importlib.util.spec_from_file_location(f"src.{name}", ROOT / path)
    mod = importlib.util.module_from_spec(spec)
    mod.__package__ = "src"
    sys.modules[f"src.{name}"] = mod
    spec.loader.exec_module(mod)
    return mod


kg_mod = _imp("knowledge_graph", "src/knowledge_graph.py")
cov = _imp("coverage", "src/workflow/coverage.py")

OLLAMA = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")

_SISTEMA = ("Você é o assistente acadêmico da UNIFESP (campus São José dos "
            "Campos) conversando com um aluno. Responda em português, de forma "
            "natural e direta, em 2 a 4 frases, usando SÓ os fatos fornecidos.")

_INSTR_COMPLETA = "Responda à pergunta inteira."
_INSTR_INCOMPLETA = ("Responda apenas o que os fatos permitem. NÃO mencione, "
                     "nem para dizer que falta, nada além do que está nos fatos.")


def fatos(kg, tipo, nome):
    if tipo == "disciplina":
        nid = kg._find_node(nome, "disciplina")
        d = kg.graph.nodes[nid] if nid else {}
        linhas = [f"Disciplina: {nome}"]
        if d.get("termo"):
            linhas.append(f"termo: {d['termo']}")
        if d.get("ementa"):
            linhas.append(f"ementa: {str(d['ementa'])[:300]}")
        docs = kg.get_docentes_of_discipline(nome)
        if docs:
            linhas.append("docentes: " + ", ".join(docs))
        pre = kg.get_prerequisite_chain(nome, max_depth=1)
        if pre:
            linhas.append("pré-requisitos: " + ", ".join(pre))
        return "\n".join(linhas)
    info = kg.get_docente_info(nome) or {}
    linhas = [f"Docente: {nome}"]
    areas = kg.get_areas_of_docente(nome)
    if areas:
        linhas.append("áreas de pesquisa: " + ", ".join(areas))
    for campo in ("email", "sala"):
        if info.get(campo):
            linhas.append(f"{campo}: {info[campo]}")
    discs = kg.get_disciplines_of_docente(nome)
    if discs:
        linhas.append("leciona: " + ", ".join(discs[:5]))
    return "\n".join(linhas)


def gerar(modelo, pergunta, blocos, instrucao):
    prompt = (f"FATOS:\n" + "\n\n".join(blocos) +
              f"\n\nPERGUNTA DO ALUNO: {pergunta}\n\n{instrucao}")
    body = json.dumps({
        "model": modelo, "stream": False,
        "messages": [{"role": "system", "content": _SISTEMA},
                     {"role": "user", "content": prompt}],
        "options": {"temperature": 0.7},
    }).encode()
    req = urllib.request.Request(f"{OLLAMA}/api/chat", data=body,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=180) as r:
        return json.load(r)["message"]["content"].strip()


_MODELOS = {
    ("disciplina", "disciplina"): [
        "qual a ementa de {a} e de {b}?",
        "quem leciona {a} e quem leciona {b}?",
        "em que termo ficam {a} e {b}?",
    ],
    ("disciplina", "docente"): [
        "qual a ementa de {a} e qual o email de {b}?",
        "me fala sobre {a} e sobre as áreas de pesquisa de {b}",
    ],
    ("docente", "disciplina"): [
        "qual a sala de {a} e quais os pré-requisitos de {b}?",
    ],
    ("docente", "docente"): [
        "qual o email de {a} e de {b}?",
        "quais as áreas de pesquisa de {a} e de {b}?",
    ],
}


def sinteticas(kg, entidades, n, rng):
    """Compostas com pares de entidades reais (as citadas em produção)."""
    out, tentativas = [], 0
    while len(out) < n and tentativas < n * 20:
        tentativas += 1
        ea, eb = rng.sample(entidades, 2)
        if ea[1] == eb[1]:
            continue
        modelos = _MODELOS.get((ea[0], eb[0]))
        if not modelos:
            continue
        q = rng.choice(modelos).format(a=ea[1], b=eb[1])
        # só vale se o grounding enxerga exatamente as duas entidades
        if cov.entidades_da_pergunta(kg, q) == [ea, eb]:
            out.append(q)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--log", default=str(ROOT / "chroma_db_unifesp/interactions.jsonl"))
    ap.add_argument("--modelo", default="gemma4:31b-cloud")
    ap.add_argument("--n-sinteticas", type=int, default=30)
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--out", default=str(ROOT / "eval/cobertura_out"))
    ap.add_argument("--rescore", help="JSON de uma rodada anterior")
    args = ap.parse_args()
    rng = random.Random(args.seed)

    os.chdir(ROOT)
    kg = kg_mod.KnowledgeGraph()
    kg.build_from_directories(
        disciplinas_dir="./markdown_disciplinas",
        regimentos_dir="./markdown_regimentos",
        docentes_dir="./markdown_docentes",
        cursos_dir="./markdown_cursos",
    )

    if args.rescore:
        anterior = json.load(open(args.rescore, encoding="utf-8"))
        args.modelo = anterior["modelo"]
        casos = anterior["casos"]
        for c in casos:
            r = cov.avaliar_cobertura(kg, c["pergunta"], c["resposta"], "disciplinas")
            c["faltantes"] = r["faltantes"] if r else []
            c["alarme"] = bool(c["faltantes"])
        relatorio(casos, args)
        return

    reais, entidades = [], []
    for linha in open(args.log, encoding="utf-8"):
        if not linha.strip():
            continue
        q = json.loads(linha)["question"].strip()
        ents = cov.entidades_da_pergunta(kg, q)
        if ents and q not in reais:
            reais.append(q)
            entidades += [e for e in ents if e not in entidades]
    comp = sinteticas(kg, entidades, args.n_sinteticas, rng)

    casos = []
    for origem, perguntas in (("real", reais), ("sintetica", comp)):
        for q in perguntas:
            ents = cov.entidades_da_pergunta(kg, q)
            todos = [fatos(kg, t, n) for t, n in ents]
            casos.append({"origem": origem, "pergunta": q, "rotulo": "completa",
                          "blocos": todos, "instr": _INSTR_COMPLETA})
            if len(ents) >= 2:
                casos.append({"origem": origem, "pergunta": q, "rotulo": "incompleta",
                              "blocos": todos[:1], "instr": _INSTR_INCOMPLETA,
                              "omitida": ents[1][1]})
    print(f"{len(reais)} perguntas reais, {len(comp)} sintéticas → {len(casos)} respostas a gerar")

    def rodar(c):
        try:
            c["resposta"] = gerar(args.modelo, c["pergunta"], c["blocos"], c["instr"])
        except Exception as e:
            c["erro"] = str(e)
            return c
        r = cov.avaliar_cobertura(kg, c["pergunta"], c["resposta"], "disciplinas")
        c["faltantes"] = r["faltantes"] if r else []
        c["alarme"] = bool(c["faltantes"])
        return c

    with ThreadPoolExecutor(max_workers=4) as ex:
        casos = list(ex.map(rodar, casos))
    casos = [c for c in casos if "erro" not in c]
    relatorio(casos, args)


def relatorio(casos, args):
    vp = sum(1 for c in casos if c["rotulo"] == "incompleta" and c["alarme"])
    fn = sum(1 for c in casos if c["rotulo"] == "incompleta" and not c["alarme"])
    fp = sum(1 for c in casos if c["rotulo"] == "completa" and c["alarme"])
    vn = sum(1 for c in casos if c["rotulo"] == "completa" and not c["alarme"])
    precisao = vp / (vp + fp) if vp + fp else 0.0
    recall = vp / (vp + fn) if vp + fn else 0.0
    # o alarme aponta a entidade certa?
    certa = sum(1 for c in casos if c["rotulo"] == "incompleta" and c["alarme"]
                and c["omitida"] in c["faltantes"])

    print(f"\nVP={vp} FN={fn} FP={fp} VN={vn}")
    print(f"precisão={precisao:.3f} recall={recall:.3f} "
          f"entidade-certa={certa}/{vp}")
    for orig in ("real", "sintetica"):
        neg = [c for c in casos if c["origem"] == orig and c["rotulo"] == "completa"]
        if neg:
            print(f"  FP em completas {orig}: {sum(c['alarme'] for c in neg)}/{len(neg)}")
    for c in casos:
        if (c["rotulo"] == "completa") == c["alarme"]:
            tag = "FP" if c["alarme"] else "FN"
            print(f"\n[{tag}] {c['pergunta']}\n  faltantes={c['faltantes']}"
                  f"\n  resposta: {c['resposta'][:300]!r}")

    os.makedirs(args.out, exist_ok=True)
    sufixo = "__rescore" if args.rescore else ""
    destino = Path(args.out) / f"cobertura__{args.modelo.replace(':', '_')}{sufixo}.json"
    with open(destino, "w", encoding="utf-8") as f:
        json.dump({"modelo": args.modelo, "vp": vp, "fn": fn, "fp": fp, "vn": vn,
                   "precisao": precisao, "recall": recall, "casos": casos},
                  f, ensure_ascii=False, indent=1)
    print(f"\nsalvo em {destino}")


if __name__ == "__main__":
    main()
