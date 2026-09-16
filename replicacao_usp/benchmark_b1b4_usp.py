"""
Benchmark B1-B4 sobre o currículo USP BCC (replicação p/ o paper CTIC).

Replica a ablação da Table 2 do paper num SEGUNDO currículo, com o MESMO padrão:
  B1 LLM-only     : LLM sem contexto
  B2 Standard RAG : BM25 sobre os markdowns do currículo → LLM
  B3 Graph-RAG    : contexto do KG a 1 hop (pré-req direto), SEM regras → LLM
  B4 NS (ours)    : KG + regras neurossimbólicas (fecho transitivo R1, plano R5,
                    dependentes, desbloqueio) → LLM

O que muda entre sistemas é SÓ o contexto; o KG, o LLM e as perguntas são os
mesmos. Gabaritos derivados dos dados OFICIAIS (JupiterWeb). Avaliação por
continência automática (conjunto de disciplinas do currículo citado na resposta
vs gabarito): strict = conjuntos iguais; weighted dá 0.5 a parcial.

Roda no container. Uso: python replicacao_usp/benchmark_b1b4_usp.py [--quick]
"""

import os
import re
import sys
import json
from pathlib import Path

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src.knowledge_graph import KnowledgeGraph
from src.neurosymbolic_validator import _build_default_engine

USP_DIR = os.path.join(ROOT, "markdown_usp_bcc")
JSON = os.path.join(ROOT, "replicacao_usp", "curso_usp_bcc.json")


def _llm():
    from langchain_ollama import OllamaLLM
    return OllamaLLM(
        model=os.getenv("MODEL_NAME", "gemma4:31b-cloud"),
        base_url=os.getenv("OLLAMA_BASE_URL", "http://host.docker.internal:11434"),
        temperature=0.1, num_predict=400,
    )


def build_kg():
    kg = KnowledgeGraph()
    for md in sorted(Path(USP_DIR).glob("*.md")):
        kg._process_discipline_file(md)
    return kg


# ---------- perguntas + gabarito (derivado dos dados oficiais) ----------

def montar_perguntas(kg, engine, discs):
    nome = {d["codigo"]: d["nome"] for d in discs}
    def n(cod):
        return nome[cod]

    P = []
    # prereq em cadeia (transitivo) — onde as regras importam
    for alvo in ["Análise de Algoritmos", "Sistemas Operacionais",
                 "Funções Diferenciáveis e Séries",
                 "Conceitos Fundamentais de Linguagens de Programação"]:
        P.append((f"Quais são todos os pré-requisitos (a cadeia completa) de {alvo}?",
                  "prereq_cadeia", alvo, set(kg.get_all_ancestors(alvo))))
    # prereq direto
    for alvo in ["Álgebra Linear I", "Laboratório de Métodos Numéricos",
                 "Cálculo Diferencial e Integral II"]:
        P.append((f"Qual é o pré-requisito direto de {alvo}?",
                  "prereq_direto", alvo, set(kg.get_direct_prerequisites(alvo))))
    # dependentes
    for alvo in ["Introdução à Computação", "Algoritmos e Estruturas de Dados I"]:
        P.append((f"Quais disciplinas dependem diretamente de {alvo}?",
                  "dependentes", alvo, set(kg.get_dependent_disciplines(alvo))))
    # plano mínimo
    for alvo in ["Análise de Algoritmos", "Sistemas Operacionais"]:
        plano = engine.plan_minimal_path(alvo, []) or []
        P.append((f"Qual o plano de estudos mínimo, do zero, para chegar a {alvo}?",
                  "plano", alvo, {d for fase in plano for d in fase}))
    # desbloqueio
    cursado = ["Introdução à Computação", "Cálculo Diferencial e Integral I",
               "Vetores e Geometria"]
    P.append(("Já cursei Introdução à Computação, Cálculo Diferencial e Integral I "
              "e Vetores e Geometria. Quais disciplinas eu desbloqueei?",
              "desbloqueio", ",".join(cursado), set(engine.derive_unlocked(cursado))))
    return P


# ---------- contexto por sistema ----------

def ctx_b2_rag(kg, pergunta, k=4):
    """BM25 simples sobre os markdowns (título+corpo)."""
    docs = []
    for md in sorted(Path(USP_DIR).glob("*.md")):
        docs.append((md.stem, md.read_text(encoding="utf-8")))
    def toks(s):
        return re.findall(r"\w+", s.lower())
    import math
    N = len(docs)
    df = {}
    dtok = [toks(title + " " + b) for title, b in docs]
    for dt in dtok:
        for w in set(dt):
            df[w] = df.get(w, 0) + 1
    q = toks(pergunta)
    avg = sum(len(dt) for dt in dtok) / N
    scores = []
    for i, dt in enumerate(dtok):
        s = 0.0
        for w in q:
            if w not in df:
                continue
            tf = dt.count(w)
            if tf == 0:
                continue
            idf = math.log((N - df[w] + 0.5) / (df[w] + 0.5) + 1)
            s += idf * (tf * 2.2) / (tf + 1.2 * (0.25 + 0.75 * len(dt) / avg))
        scores.append((s, i))
    scores.sort(reverse=True)
    top = [docs[i][1] for _, i in scores[:k]]
    return "\n\n".join(top)


def ctx_b3_graph(kg, tipo, alvo):
    """KG a 1 hop: só pré-requisito direto / vizinhança. Sem regras."""
    if tipo in ("prereq_cadeia", "prereq_direto", "plano"):
        diretos = kg.get_direct_prerequisites(alvo)
        return f"Pré-requisito(s) direto(s) de {alvo}: {', '.join(diretos) or 'nenhum'}."
    if tipo == "dependentes":
        deps = kg.get_dependent_disciplines(alvo)
        return f"Disciplinas cujo pré-requisito direto é {alvo}: {', '.join(deps) or 'nenhuma'}."
    if tipo == "desbloqueio":
        return "Consulte os pré-requisitos diretos de cada disciplina do currículo."
    return ""


def ctx_b4_ns(kg, engine, tipo, alvo):
    """KG + regras: fecho transitivo, plano, dependentes, desbloqueio."""
    if tipo == "prereq_cadeia":
        anc = sorted(kg.get_all_ancestors(alvo))
        return f"[R1 fecho transitivo] Pré-requisitos completos de {alvo}: {', '.join(anc)}."
    if tipo == "prereq_direto":
        return f"[KG] Pré-requisito direto de {alvo}: {', '.join(kg.get_direct_prerequisites(alvo))}."
    if tipo == "dependentes":
        return f"[KG] Dependentes diretos de {alvo}: {', '.join(kg.get_dependent_disciplines(alvo))}."
    if tipo == "plano":
        plano = engine.plan_minimal_path(alvo, []) or []
        fases = "; ".join(f"fase {i}: {', '.join(f)}" for i, f in enumerate(plano, 1))
        return f"[R5 plano mínimo] {fases}."
    if tipo == "desbloqueio":
        cursado = alvo.split(",")
        unlocked = sorted(engine.derive_unlocked(cursado))
        return f"[R2 desbloqueio] Disciplinas desbloqueadas: {', '.join(unlocked)}."
    return ""


PROMPT = ("Você é um assistente acadêmico. Responda em português, listando as "
          "disciplinas pertinentes.{ctx}\n\nPergunta: {q}\n\nResposta:")


def responder(llm, pergunta, contexto):
    ctx = f"\n\nFatos disponíveis (use SOMENTE estes):\n{contexto}" if contexto else ""
    try:
        return llm.invoke(PROMPT.format(ctx=ctx, q=pergunta)).strip()
    except Exception as e:
        return f"[erro: {e}]"


# ---------- avaliação por continência ----------

def avaliar(kg, resposta, gabarito, vocab, alvo_nome=None):
    resp_norm = kg._normalize_text(resposta)
    # limite de palavra: evita "Cálculo I" casar dentro de "Cálculo II" etc.
    def mencionou(nome):
        pat = r"\b" + re.escape(kg._normalize_text(nome)) + r"\b"
        return re.search(pat, resp_norm) is not None
    mencionadas = {d for d in vocab if mencionou(d)}
    if alvo_nome:
        mencionadas.discard(alvo_nome)   # o alvo aparece na pergunta, não é extra
    gab = set(gabarito)
    acertos = mencionadas & gab
    extras = (mencionadas - gab)
    if acertos == gab and not extras:
        return 1.0, "C"
    if acertos == gab and extras:
        return 0.5, "P"   # completo mas com ruído (mencionou disciplina alheia)
    if acertos and acertos < gab:
        return 0.5, "P"
    return 0.0, "I"


def main():
    quick = "--quick" in sys.argv
    discs = json.load(open(JSON, encoding="utf-8"))["disciplinas"]
    vocab = [d["nome"] for d in discs]
    kg = build_kg()
    engine = _build_default_engine(kg)
    perguntas = montar_perguntas(kg, engine, discs)
    if quick:
        perguntas = perguntas[:4]
    llm = _llm()

    sistemas = ["B1", "B2", "B3", "B4"]
    acc = {s: [] for s in sistemas}
    detalhes = []

    for i, (q, tipo, alvo, gab) in enumerate(perguntas, 1):
        # nomes do gabarito (codigos → nomes)
        cod2nome = {d["codigo"]: d["nome"] for d in discs}
        gab_nomes = {cod2nome.get(g, g) for g in gab}
        print(f"\n[{i}/{len(perguntas)}] ({tipo}) {q}")
        print(f"    gabarito: {sorted(gab_nomes)}")
        ctxs = {
            "B1": "",
            "B2": ctx_b2_rag(kg, q),
            "B3": ctx_b3_graph(kg, tipo, alvo),
            "B4": ctx_b4_ns(kg, engine, tipo, alvo),
        }
        linha = {"pergunta": q, "tipo": tipo}
        # no 'plano' o alvo faz parte do gabarito (última fase); no desbloqueio
        # não há alvo único. Nos demais, o alvo é citado na pergunta → desconta.
        alvo_nome = alvo if tipo not in ("desbloqueio", "plano") else None
        for s in sistemas:
            resp = responder(llm, q, ctxs[s])
            score, label = avaliar(kg, resp, gab_nomes, vocab, alvo_nome)
            acc[s].append(score)
            linha[s] = {"label": label, "score": score, "resposta": resp[:300]}
            print(f"    {s}: {label} ({score})")
        detalhes.append(linha)

    print("\n" + "=" * 60)
    print(f"BENCHMARK B1-B4 no currículo USP BCC ({len(perguntas)} perguntas)")
    print("=" * 60)
    print(f"{'Sistema':<18}{'Acc':>8}{'wAcc':>8}")
    for s, nome in [("B1", "B1 LLM-only"), ("B2", "B2 Standard RAG"),
                    ("B3", "B3 Graph-RAG"), ("B4", "B4 NS (ours)")]:
        scores = acc[s]
        strict = sum(1 for x in scores if x == 1.0) / len(scores)
        weighted = sum(scores) / len(scores)
        print(f"{nome:<18}{strict*100:>7.1f}%{weighted*100:>7.1f}%")

    out = os.path.join(ROOT, "replicacao_usp", "resultados_b1b4_usp.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump({"n": len(perguntas), "detalhes": detalhes}, f,
                  ensure_ascii=False, indent=2)
    print(f"\nDetalhes → {out}")


if __name__ == "__main__":
    main()
