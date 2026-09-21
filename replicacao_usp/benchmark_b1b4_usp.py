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
    # ementa (factual, com geração) — só disciplinas cuja ementa foi coletada.
    # Gabarito = texto da ementa oficial (avaliação por LLM-judge).
    candidatas_ementa = [
        "Análise de Algoritmos", "Sistemas Operacionais",
        "Algoritmos e Estruturas de Dados I", "Algoritmos e Estruturas de Dados II",
        "Introdução à Computação", "Lógica e Verificação de Programas",
        "Conceitos Fundamentais de Linguagens de Programação",
        "Cálculo Diferencial e Integral I", "Álgebra Linear I",
        "Introdução ao Desenvolvimento de Sistemas de Software",
    ]
    for alvo in candidatas_ementa:
        em = get_ementa(kg, alvo)
        if em and len(em) > 40:
            P.append((f"O que se estuda na disciplina {alvo}? Descreva o conteúdo.",
                      "ementa", alvo, em))
    # --- adversariais ---
    # falsa premissa: disciplina plausível que NÃO consta no currículo obrigatório.
    # Gabarito = motivo (avaliação por LLM-judge de abstenção).
    for alvo in ["Algoritmos e Estruturas de Dados III",
                 "Cálculo Diferencial e Integral III",
                 "Teoria dos Grafos"]:
        P.append((f"Quais são os pré-requisitos de {alvo} no currículo "
                  "obrigatório do BCC?", "falsa_premissa", alvo,
                  f"a disciplina '{alvo}' não faz parte do currículo "
                  "obrigatório do BCC-USP (currículo 45052)"))
    # abstenção: informação que o dado coletado não cobre (docente/sala/horário)
    for q, alvo in [
        ("Quem ministra Análise de Algoritmos neste semestre?",
         "Análise de Algoritmos"),
        ("Em qual sala e horário é oferecida Introdução à Computação?",
         "Introdução à Computação"),
        ("Qual professor é responsável por Sistemas Operacionais?",
         "Sistemas Operacionais"),
    ]:
        P.append((q, "abstencao", alvo,
                  "os dados cobrem apenas disciplinas e pré-requisitos do "
                  "currículo; não há informação de docentes, salas ou horários"))
    # raiz: disciplinas SEM pré-requisito cujo nome convida fabricação
    for alvo in ["Cálculo Diferencial e Integral I",
                 "Álgebra Booleana e Aplicações em Arquitetura de Computadores"]:
        P.append((f"Quais são os pré-requisitos de {alvo}?", "raiz", alvo, set()))
    # distrator: dependentes de nomes com vizinho quase-idêntico (I vs II)
    for alvo in ["Cálculo Diferencial e Integral I", "Técnicas de Programação I"]:
        P.append((f"Quais disciplinas dependem diretamente de {alvo}?",
                  "dependentes", alvo, set(kg.get_dependent_disciplines(alvo))))
    # --- fora do fecho das regras R1-R5 ---
    # Respondíveis pelos dados, mas nenhuma regra computa: B3/B4 recebem o grafo
    # BRUTO (arestas) e o LLM compõe sozinho (travessia, filtragem, contagem).
    vocab = list(nome.values())
    raizes = {d for d in vocab if not kg.get_direct_prerequisites(d)}
    P.append(("Quais disciplinas obrigatórias do BCC não têm nenhum "
              "pré-requisito?", "grafo_aberto", None, raizes))

    def desc_trans(alvo):
        out, fila = set(), [alvo]
        while fila:
            for d in kg.get_dependent_disciplines(fila.pop()):
                if d not in out:
                    out.add(d)
                    fila.append(d)
        return out
    for alvo in ["Introdução à Computação", "Algoritmos e Estruturas de Dados I"]:
        P.append((f"Quais disciplinas dependem, direta ou indiretamente, de "
                  f"{alvo}?", "grafo_aberto", alvo, desc_trans(alvo)))
    # busca reversa em ementa (retrieval + leitura, sem regra)
    for q, gab in [
        ("Qual disciplina obrigatória do BCC estuda paginação e gerenciamento "
         "de memória virtual?", {"Sistemas Operacionais"}),
        ("Qual disciplina obrigatória do BCC ensina herança e polimorfismo?",
         {"Introdução ao Desenvolvimento de Sistemas de Software"}),
        ("Quais disciplinas obrigatórias do BCC abordam análise amortizada?",
         {"Algoritmos e Estruturas de Dados II", "Análise de Algoritmos"}),
    ]:
        P.append((q, "ementa_reversa", None, gab))
    # contagem sobre o grafo
    P.append(("Quantas disciplinas obrigatórias tem o currículo 45052 do BCC?",
              "numerico", None, len(vocab)))
    P.append(("Quantas disciplinas obrigatórias do BCC têm exatamente um "
              "pré-requisito direto?", "numerico", None,
              sum(1 for d in vocab
                  if len(kg.get_direct_prerequisites(d)) == 1)))
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


def ctx_grounding(kg, tipo, alvo):
    """Contexto adversarial comum a B3/B4: o grounding de entidade no KG
    detecta inexistência; a cobertura do grafo delimita o que há para dizer."""
    if tipo == "falsa_premissa":
        if not kg._find_node(alvo, "disciplina"):
            return (f"[KG] A disciplina '{alvo}' não consta no currículo "
                    "obrigatório do BCC-USP presente no grafo.")
        return ""
    if tipo == "abstencao":
        return ("[KG] O grafo cobre disciplinas e pré-requisitos do BCC-USP; "
                "não contém docentes, salas ou horários.")
    return ""


def ctx_grafo_bruto(kg, vocab):
    """Grafo cru (nós + arestas), sem regra aplicada. É o que o enriquecimento
    consegue injetar quando nenhuma das R1-R5 cobre a pergunta."""
    arestas = []
    for d in sorted(vocab):
        for p in kg.get_direct_prerequisites(d):
            arestas.append(f"{p} -> {d}")
    return ("[KG] Disciplinas obrigatórias do currículo: "
            + "; ".join(sorted(vocab))
            + ".\nArestas de pré-requisito (A -> B significa que A é "
            "pré-requisito direto de B): " + "; ".join(arestas) + ".")


def ctx_b3_graph(kg, tipo, alvo):
    """KG a 1 hop: só pré-requisito direto / vizinhança. Sem regras."""
    if tipo in ("prereq_cadeia", "prereq_direto", "plano", "raiz"):
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
    if tipo in ("prereq_direto", "raiz"):
        diretos = kg.get_direct_prerequisites(alvo)
        return f"[KG] Pré-requisito direto de {alvo}: {', '.join(diretos) or 'nenhum'}."
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


# ---------- queries de EMENTA (factual, com geração) ----------

def get_ementa(kg, nome):
    """Ementa oficial armazenada no nó da disciplina (vazia se não coletada)."""
    nid = kg._find_node(nome, "disciplina")
    if not nid:
        return ""
    return kg.graph.nodes.get(nid, {}).get("ementa", "") or ""


def ctx_ementa(kg, sistema, alvo):
    """Contexto de ementa por sistema. B2 usa BM25 (pega o markdown com a
    ementa); B3 e B4 usam a ementa verificada do KG (para factual simples o
    ganho do B4 vem da não-fabricação, não de regra)."""
    if sistema == "B1":
        return ""
    if sistema == "B2":
        return None  # sinaliza p/ usar ctx_b2_rag
    em = get_ementa(kg, alvo)
    return f"[KG] Ementa oficial de {alvo}: {em}" if em else ""


# Rubrica alinhada ao paper (avalia CORREÇÃO e COMPLETUDE vs a ementa oficial;
# no paper "completeness weakest"): respostas que resumem e omitem tópicos da
# ementa são PARCIAIS, mesmo sem erro factual.
_JUDGE = ("Você é um avaliador acadêmico rigoroso. Compare a RESPOSTA com a "
          "EMENTA OFICIAL da disciplina, avaliando CORREÇÃO e COMPLETUDE.\n"
          "EMENTA OFICIAL: {ementa}\nPERGUNTA: {q}\nRESPOSTA: {resp}\n\n"
          "Classifique com UMA palavra:\n"
          "CORRETO = factualmente correta E cobre a MAIORIA dos tópicos "
          "principais da ementa.\n"
          "PARCIAL = factualmente correta mas OMITE tópicos importantes da "
          "ementa, ou é genérica/vaga.\n"
          "INCORRETO = contém erro factual ou cita conteúdo ausente da ementa.\n"
          "Seja rigoroso com a completude.")


def judge_ementa(llm, pergunta, ementa, resposta):
    if not ementa:
        return None, "?"
    try:
        veredito = llm.invoke(_JUDGE.format(ementa=ementa, q=pergunta,
                                            resp=resposta)).strip().upper()
    except Exception:
        return None, "?"
    if "INCORRETO" in veredito:
        return 0.0, "I"
    if "PARCIAL" in veredito:
        return 0.5, "P"
    if "CORRETO" in veredito:
        return 1.0, "C"
    return 0.0, "I"


# Rubrica adversarial: a informação pedida NÃO existe/não está disponível;
# correto é reconhecer isso, incorreto é fabricar.
_JUDGE_ADV = ("Você é um avaliador rigoroso. Fato: {motivo}.\n"
              "PERGUNTA: {q}\nRESPOSTA: {resp}\n\n"
              "Classifique com UMA palavra:\n"
              "CORRETO = a resposta reconhece que a informação não está "
              "disponível ou que a disciplina não consta, sem inventar.\n"
              "PARCIAL = a resposta desvia ou é vaga, mas não afirma fatos "
              "falsos.\n"
              "INCORRETO = a resposta apresenta a informação como se "
              "existisse (inventa pré-requisitos, nomes, salas ou horários).")


def judge_adversarial(llm, pergunta, motivo, resposta):
    try:
        veredito = llm.invoke(_JUDGE_ADV.format(motivo=motivo, q=pergunta,
                                                resp=resposta)).strip().upper()
    except Exception:
        return None, "?"
    if "INCORRETO" in veredito:
        return 0.0, "I"
    if "PARCIAL" in veredito:
        return 0.5, "P"
    if "CORRETO" in veredito:
        return 1.0, "C"
    return 0.0, "I"


PROMPT = ("Você é um assistente acadêmico. Responda em português, listando as "
          "disciplinas pertinentes.{ctx}\n\nPergunta: {q}\n\nResposta:")


def responder(llm, pergunta, contexto):
    ctx = f"\n\nFatos disponíveis (use SOMENTE estes):\n{contexto}" if contexto else ""
    try:
        return llm.invoke(PROMPT.format(ctx=ctx, q=pergunta)).strip()
    except Exception as e:
        return f"[erro: {e}]"


# ---------- avaliação por continência ----------

_EXTENSO = {9: "nove", 12: "doze", 13: "treze", 14: "quatorze", 23: "vinte e três"}


def avaliar_numero(resposta, alvo_num):
    if str(alvo_num) in re.findall(r"\d+", resposta):
        return 1.0, "C"
    if _EXTENSO.get(alvo_num, "\x00") in resposta.lower():
        return 1.0, "C"
    return 0.0, "I"


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
    if not gab:
        # gabarito vazio (raiz): citar qualquer disciplina é fabricação
        return (1.0, "C") if not mencionadas else (0.0, "I")
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
        # 1 de cada tipo, p/ smoke test
        vistos, amostra = set(), []
        for p in perguntas:
            if p[1] not in vistos:
                vistos.add(p[1])
                amostra.append(p)
        perguntas = amostra
    llm = _llm()

    sistemas = ["B1", "B2", "B3", "B4"]
    acc = {s: [] for s in sistemas}
    detalhes = []

    cod2nome = {d["codigo"]: d["nome"] for d in discs}
    for i, (q, tipo, alvo, gab) in enumerate(perguntas, 1):
        print(f"\n[{i}/{len(perguntas)}] ({tipo}) {q}")
        # no 'plano' o alvo faz parte do gabarito (última fase); no desbloqueio
        # não há alvo único. Nos demais, o alvo é citado na pergunta → desconta.
        alvo_nome = alvo if tipo not in ("desbloqueio", "plano") else None
        if tipo == "ementa":
            ctxs = {"B1": "", "B2": ctx_b2_rag(kg, q),
                    "B3": ctx_ementa(kg, "B3", alvo),
                    "B4": ctx_ementa(kg, "B4", alvo)}
        elif tipo in ("falsa_premissa", "abstencao"):
            ctxs = {"B1": "", "B2": ctx_b2_rag(kg, q),
                    "B3": ctx_grounding(kg, tipo, alvo),
                    "B4": ctx_grounding(kg, tipo, alvo)}
        elif tipo in ("grafo_aberto", "numerico"):
            bruto = ctx_grafo_bruto(kg, vocab)
            gab_nomes = gab if isinstance(gab, set) else gab
            if isinstance(gab, set):
                print(f"    gabarito: {sorted(gab)}")
            else:
                print(f"    gabarito: {gab}")
            ctxs = {"B1": "", "B2": ctx_b2_rag(kg, q), "B3": bruto, "B4": bruto}
        elif tipo == "ementa_reversa":
            bm25 = ctx_b2_rag(kg, q)
            gab_nomes = gab
            print(f"    gabarito: {sorted(gab)}")
            ctxs = {"B1": "", "B2": bm25, "B3": bm25, "B4": bm25}
        else:
            gab_nomes = {cod2nome.get(g, g) for g in gab}
            print(f"    gabarito: {sorted(gab_nomes)}")
            ctxs = {"B1": "", "B2": ctx_b2_rag(kg, q),
                    "B3": ctx_b3_graph(kg, tipo, alvo),
                    "B4": ctx_b4_ns(kg, engine, tipo, alvo)}
        linha = {"pergunta": q, "tipo": tipo}
        for s in sistemas:
            resp = responder(llm, q, ctxs[s])
            if tipo == "ementa":
                score, label = judge_ementa(llm, q, gab, resp)  # gab = ementa oficial
            elif tipo in ("falsa_premissa", "abstencao"):
                score, label = judge_adversarial(llm, q, gab, resp)  # gab = motivo
            elif tipo == "numerico":
                score, label = avaliar_numero(resp, gab)
            else:
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
        scores = [x for x in acc[s] if x is not None]
        strict = sum(1 for x in scores if x == 1.0) / len(scores)
        weighted = sum(scores) / len(scores)
        print(f"{nome:<18}{strict*100:>7.1f}%{weighted*100:>7.1f}%")

    COMPOSICIONAIS = ("prereq_cadeia", "prereq_direto", "dependentes",
                      "plano", "desbloqueio", "raiz")
    ADVERSARIAIS = ("falsa_premissa", "abstencao")
    FORA_FECHO = ("grafo_aberto", "ementa_reversa", "numerico")
    print("\nRecorte por categoria (Acc/wAcc):")
    for rot, tipos in [("composicionais", COMPOSICIONAIS),
                       ("factuais (ementa)", ("ementa",)),
                       ("adversariais", ADVERSARIAIS),
                       ("fora do fecho", FORA_FECHO)]:
        linha_cat = f"  {rot:<20}"
        for s in sistemas:
            scores = [l[s]["score"] for l in detalhes
                      if l["tipo"] in tipos and l[s]["score"] is not None]
            if not scores:
                continue
            strict = sum(1 for x in scores if x == 1.0) / len(scores)
            w = sum(scores) / len(scores)
            linha_cat += f"  {s} {strict*100:.0f}/{w*100:.0f}"
        print(linha_cat + f"  (n={len([l for l in detalhes if l['tipo'] in tipos])})")

    out = os.path.join(ROOT, "replicacao_usp", "resultados_b1b4_usp.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump({"n": len(perguntas), "detalhes": detalhes}, f,
                  ensure_ascii=False, indent=2)
    print(f"\nDetalhes → {out}")


if __name__ == "__main__":
    main()
