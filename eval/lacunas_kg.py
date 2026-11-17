"""
Lacunas do KG a partir das falhas de produção (src/workflow/lacunas.py).

Lê o interactions.jsonl, classifica cada falha pelo próprio KG (CÓDIGO: a base
tem o valor e a resposta não trouxe; DADO: a base não tem) e, com --propor,
pede ao LLM o valor faltante COM citação da fonte e verifica a proposta sem
LLM. Só proposta verificada vai para a fila de curadoria como sugestão; o
humano aprova e aplica no markdown de origem. Nada é escrito no KG.

    python3 eval/lacunas_kg.py [--log chroma_db_unifesp/interactions.jsonl]
        [--propor --modelo gemma4:31b-cloud] [--out chroma_db_unifesp]
"""

import argparse
import importlib.util
import json
import os
import sys
import types
import urllib.request
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OLLAMA = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")


def _carregar():
    if "src" not in sys.modules:
        pkg = types.ModuleType("src")
        pkg.__path__ = [str(ROOT / "src")]
        sys.modules["src"] = pkg
    if "src.workflow" not in sys.modules:
        wf = types.ModuleType("src.workflow")
        wf.__path__ = [str(ROOT / "src/workflow")]
        sys.modules["src.workflow"] = wf
    mods = {}
    for nome, pacote, caminho in (("src.knowledge_graph", "src", "src/knowledge_graph.py"),
                                  ("src.workflow.coverage", "src.workflow", "src/workflow/coverage.py"),
                                  ("src.workflow.lacunas", "src.workflow", "src/workflow/lacunas.py")):
        if nome in sys.modules and getattr(sys.modules[nome], "__file__", None):
            mods[nome] = sys.modules[nome]
            continue
        spec = importlib.util.spec_from_file_location(nome, ROOT / caminho)
        mod = importlib.util.module_from_spec(spec)
        mod.__package__ = pacote
        sys.modules[nome] = mod
        spec.loader.exec_module(mod)
        mods[nome] = mod
    return mods["src.knowledge_graph"], mods["src.workflow.lacunas"]


def construir_kg(kg_mod):
    cwd = os.getcwd()
    os.chdir(ROOT)
    try:
        kg = kg_mod.KnowledgeGraph()
        kg.build_from_directories(disciplinas_dir="./markdown_disciplinas",
                                  regimentos_dir="./markdown_regimentos",
                                  docentes_dir="./markdown_docentes",
                                  cursos_dir="./markdown_cursos")
        return kg
    finally:
        os.chdir(cwd)


def llm_ollama(modelo):
    def chamar(prompt):
        body = json.dumps({"model": modelo, "stream": False, "options": {"temperature": 0},
                           "messages": [{"role": "user", "content": prompt}]}).encode()
        req = urllib.request.Request(f"{OLLAMA}/api/chat", data=body,
                                     headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=180) as r:
            return json.load(r)["message"]["content"]
    return chamar


def gerar(kg, lac, turnos, llm=None):
    """(work orders de CÓDIGO, itens de curadoria de DADO)."""
    agora = datetime.now().isoformat(timespec="seconds")
    codigo, dado = [], []
    for l in lac.lacunas_do_log(kg, turnos):
        rep = f"{l['entidade']}: {l['atributo']}"
        if l["classe"] == "codigo":
            codigo.append({
                "representante": rep, "frequencia": l["frequencia"], "exemplos": l["exemplos"],
                "tipo_hint": "codigo (o KG TEM o valor; a resposta não trouxe)",
                "origem": "lacuna_kg", "intent": l["intent"],
                "hint": (f"O KG tem '{l['atributo']}' de {l['entidade']}: o defeito é de "
                         f"roteamento, handler ou grounding da entidade (o intent "
                         f"'{l['intent']}' chegou?). Reproduza com os exemplos."),
                "criado_em": agora,
            })
            continue
        item = {
            "representante": rep, "frequencia": l["frequencia"], "exemplos": l["exemplos"],
            "tipo": "lacuna_kg", "entidade": l["entidade"], "atributo": l["atributo"],
            "acao": "curar dado na base (o KG não tem o valor); NÃO é PR de código",
            "criado_em": agora,
        }
        if llm is not None:
            try:
                prop = lac.propor(l, ROOT, llm)
            except Exception as e:
                prop, item["erro_proposta"] = None, str(e)
            if prop:
                item["proposta"] = prop
                item["verificacao"] = lac.verificar(prop, l, ROOT, kg)
                if item["verificacao"]["ok"]:
                    item["acao"] = (f"APROVAR: '{prop['valor']}' citado em {prop['arquivo']} "
                                    f"(\"{prop['citacao']}\"); aplicar no markdown/parser de origem")
        dado.append(item)
    return codigo, dado


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--log", default=str(ROOT / "chroma_db_unifesp/interactions.jsonl"))
    ap.add_argument("--propor", action="store_true")
    ap.add_argument("--modelo", default="gemma4:31b-cloud")
    ap.add_argument("--out", help="pasta para lacunas_kg_codigo.jsonl / lacunas_kg_dado.jsonl")
    a = ap.parse_args()
    kg_mod, lac = _carregar()
    kg = construir_kg(kg_mod)
    turnos = [json.loads(l) for l in open(a.log, encoding="utf-8") if l.strip()]
    codigo, dado = gerar(kg, lac, turnos, llm_ollama(a.modelo) if a.propor else None)
    print(f"\n{len(codigo)} lacuna(s) de CÓDIGO, {len(dado)} de DADO")
    for w in codigo:
        print(f"  [código {w['frequencia']}x] {w['representante']}  ex.: {w['exemplos'][0]!r}")
    for d in dado:
        v = d.get("verificacao")
        marca = "sem proposta" if "proposta" not in d else ("VERIFICADA" if v["ok"] else
                                                            f"rejeitada: {v['motivos']}")
        print(f"  [dado {d['frequencia']}x] {d['representante']}  → {marca}")
        if "proposta" in d:
            print(f"      proposta: {d['proposta']}")
    if a.out:
        out = Path(a.out)
        out.mkdir(parents=True, exist_ok=True)
        for nome, itens in (("lacunas_kg_codigo.jsonl", codigo), ("lacunas_kg_dado.jsonl", dado)):
            with open(out / nome, "w", encoding="utf-8") as f:
                for i in itens:
                    f.write(json.dumps(i, ensure_ascii=False) + "\n")
        print(f"\nsalvo em {out}")


if __name__ == "__main__":
    main()
