"""
Extrator neural de conceitos: o LLM lê a ementa de cada disciplina do KG e
propõe arestas ABORDA (conceitos que a disciplina ensina) e REQUER_BASE
(conceitos que ela pressupõe), restritas a um vocabulário controlado.

Guardrails anti-poluição:
- só disciplinas que JÁ existem no KG entram (iteração sobre o próprio grafo);
- conceitos fora do vocabulário não viram aresta: ficam em _novos_sugeridos,
  no arquivo de saída, para curadoria humana;
- a confiança das extrações é limitada a 0.8 na carga (o seed curado, com
  confiança 1.0, sempre domina e nunca é sobrescrito).

Uso (dentro do container, com Ollama acessível):
  python -m src.conceito_extractor --max 20      # amostra
  python -m src.conceito_extractor               # todas as disciplinas
Saída: src/conceitos_extraidos.json (carregado no próximo build do KG).
"""

import argparse
import json
import os
import re
import unicodedata
from pathlib import Path
from typing import Dict, List, Optional, Set

BASE = Path(__file__).parent
SEED_PATH = BASE / "conceitos_seed.json"
SAIDA_PATH = BASE / "conceitos_extraidos.json"

PROMPT = """Voce e um curador academico de um grafo de conhecimento universitario.
Analise a disciplina abaixo e classifique conceitos em duas categorias:

1. "aborda": conceitos que a disciplina ENSINA como parte central do conteudo.
2. "requer_base": conceitos que a disciplina PRESSUPOE que o aluno ja domine
   (base matematica ou tecnica implicita, mesmo que a ementa nao cite), com uma
   confianca de 0.5 a 1.0.

VOCABULARIO PERMITIDO (use SOMENTE estes termos, exatamente como escritos):
{vocab}

Se um conceito importante nao esta no vocabulario, liste-o em "novos_sugeridos"
(nao sera usado automaticamente).

Disciplina: {nome}
Ementa: {ementa}

Responda APENAS com JSON valido:
{{"aborda": ["conceito"], "requer_base": {{"conceito": 0.8}}, "novos_sugeridos": []}}

JSON:"""


def _norm_conceito(texto: str) -> str:
    t = re.sub(r"\s+", " ", str(texto or "").strip().lower())
    return t.strip(".,;:")


def carregar_vocabulario(seed_path: Path = SEED_PATH) -> Set[str]:
    with open(seed_path, encoding="utf-8") as f:
        seed = json.load(f)
    vocab = {_norm_conceito(c) for c in seed.get("vocabulario") or []}
    vocab |= {_norm_conceito(c) for c in (seed.get("aborda") or {})}
    for conceitos in (seed.get("requer_base") or {}).values():
        vocab |= {_norm_conceito(c) for c in conceitos}
    return {v for v in vocab if v}


def parse_conceitos_llm(raw: str, vocab: Set[str]) -> Dict:
    out = {"aborda": [], "requer_base": {}, "novos": []}
    m = re.search(r"\{.*\}", str(raw or ""), re.DOTALL)
    if not m:
        return out
    try:
        data = json.loads(m.group(0))
    except (json.JSONDecodeError, ValueError):
        return out
    if not isinstance(data, dict):
        return out

    for c in data.get("aborda") or []:
        cn = _norm_conceito(c)
        if not cn:
            continue
        if cn in vocab:
            if cn not in out["aborda"]:
                out["aborda"].append(cn)
        elif cn not in out["novos"]:
            out["novos"].append(cn)

    requer = data.get("requer_base") or {}
    if isinstance(requer, list):
        requer = {c: 0.7 for c in requer}
    if isinstance(requer, dict):
        for c, conf in requer.items():
            cn = _norm_conceito(c)
            if not cn:
                continue
            try:
                conf = float(conf)
            except (TypeError, ValueError):
                conf = 0.7
            conf = max(0.0, min(conf, 1.0))
            if cn in vocab:
                out["requer_base"][cn] = max(conf, out["requer_base"].get(cn, 0.0))
            elif cn not in out["novos"]:
                out["novos"].append(cn)

    for c in data.get("novos_sugeridos") or []:
        cn = _norm_conceito(c)
        if cn and cn not in vocab and cn not in out["novos"]:
            out["novos"].append(cn)
    return out


def montar_saida(resultados: Dict[str, Dict], modelo: str) -> Dict:
    aborda: Dict[str, List[Dict]] = {}
    requer_base: Dict[str, Dict[str, float]] = {}
    novos: Dict[str, List[str]] = {}
    for disciplina, r in resultados.items():
        for conceito in r["aborda"]:
            aborda.setdefault(conceito, []).append(
                {"disciplina": disciplina, "confidence": 0.7}
            )
        if r["requer_base"]:
            requer_base[disciplina] = dict(sorted(r["requer_base"].items()))
        for conceito in r["novos"]:
            lista = novos.setdefault(conceito, [])
            if disciplina not in lista:
                lista.append(disciplina)
    return {
        "_meta": {"gerado_por": "conceito_extractor", "modelo": modelo},
        "_novos_sugeridos": dict(sorted(novos.items())),
        "aborda": dict(sorted(aborda.items())),
        "requer_base": dict(sorted(requer_base.items())),
    }


def _get_llm():
    from langchain_ollama import OllamaLLM

    kwargs = dict(
        model=os.getenv("MODEL_NAME", "gemma4:12b"),
        temperature=0,
        num_predict=350,
        keep_alive=3600,
    )
    base_url = (os.getenv("OLLAMA_BASE_URL") or "").strip()
    if base_url:
        kwargs["base_url"] = base_url
    return OllamaLLM(**kwargs)


def main():
    p = argparse.ArgumentParser(description="Extrator neural de conceitos")
    p.add_argument("--max", type=int, default=None)
    p.add_argument("--out", default=str(SAIDA_PATH))
    p.add_argument("--dry", action="store_true")
    args = p.parse_args()

    from .knowledge_graph import KnowledgeGraph

    kg = KnowledgeGraph()
    kg.build_from_directories(
        "markdown_disciplinas", "markdown_regimentos",
        "markdown_docentes", "markdown_cursos",
    )
    vocab = carregar_vocabulario()
    vocab_str = ", ".join(sorted(vocab))
    llm = _get_llm()

    disciplinas = [
        (d.get("nome"), d.get("ementa"))
        for _, d in kg.graph.nodes(data=True)
        if d.get("tipo") == "disciplina" and len(d.get("ementa") or "") > 40
    ]
    disciplinas.sort()
    if args.max:
        disciplinas = disciplinas[: args.max]

    resultados: Dict[str, Dict] = {}
    for i, (nome, ementa) in enumerate(disciplinas, 1):
        prompt = PROMPT.format(vocab=vocab_str, nome=nome, ementa=ementa[:700])
        try:
            raw = llm.invoke(prompt)
        except Exception as e:
            print(f"  [{i}/{len(disciplinas)}] {nome}: ERRO {e}")
            continue
        parsed = parse_conceitos_llm(raw, vocab)
        resultados[nome] = parsed
        print(
            f"  [{i}/{len(disciplinas)}] {nome}: "
            f"{len(parsed['aborda'])} aborda, "
            f"{len(parsed['requer_base'])} requer, "
            f"{len(parsed['novos'])} novos"
        )

    saida = montar_saida(resultados, os.getenv("MODEL_NAME", ""))
    total_aborda = sum(len(v) for v in saida["aborda"].values())
    print(
        f"\nTotal: {total_aborda} arestas ABORDA, "
        f"{len(saida['requer_base'])} disciplinas com REQUER_BASE, "
        f"{len(saida['_novos_sugeridos'])} conceitos novos sugeridos"
    )
    if args.dry:
        print(json.dumps(saida, ensure_ascii=False, indent=2)[:2000])
        return
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(saida, f, ensure_ascii=False, indent=2)
    print(f"Salvo em {args.out}")


if __name__ == "__main__":
    main()
