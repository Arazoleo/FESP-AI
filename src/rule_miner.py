"""
Minerador de regras Horn sobre o Knowledge Graph (camada aprendida do NSAI).

Descobre regras interpretáveis a partir das relações já presentes no KG, no
mesmo formato que o PyReasonEngine consome (Datalog anotado). Cada regra vem com
suas métricas AMIE-style:

    support     = nº de instâncias em que corpo E cabeça valem
    body        = nº de instâncias em que o corpo vale
    confidence  = support / body   (vira o bound [confidence, 1] no PyReason)

Foco em regras de comprimento 2:
    composição:      r1(x, y) ∧ r2(y, z) → r3(x, z)
    transitividade:  r(x, y)  ∧ r(y, z)  → r(x, z)      (caso r1=r2=r3)

Filosofia NSAI: as regras mineradas entram como camada de CRENÇA PARCIAL. Os
fatos duros curados mantêm crença 1.0; uma regra aprendida nunca sobrescreve um
fato curado, só sugere relações com a confiança declarada. Puro Python/NetworkX,
sem dependências novas, roda sem o PyReason instalado.

Uso:  python3 -m src.rule_miner   (constrói o KG e imprime as regras mineradas)
"""

import math
import re
import unicodedata
import weakref
from collections import Counter, defaultdict
from typing import Dict, List, Set, Tuple

# Peso do sinal textual (similaridade de ementas) no scorer de pré-requisito.
_W_EMENTA = 15.0
_STOP_PT = frozenset(
    "de da do e a o os as em para com que uma um no na dos das por ao se sua seu "
    "sao aos pelo pela como mais ou tambem sobre entre seus suas dessa desse este "
    "esta ser tem".split()
)
# Cache dos sinais de pré-requisito por KG (o TF-IDF das ementas é caro).
_SINAIS_CACHE: "weakref.WeakKeyDictionary" = weakref.WeakKeyDictionary()

# Relações consideradas como CABEÇA candidata (as que queremos explicar/prever).
# Documentais (MENCIONA/CONTEM/REFERENCIA) ficam de fora: não são alvo de regra.
CABECAS_ALVO = frozenset({
    "PREREQUISITO_DE", "REQUER_BASE", "ABORDA", "LECIONA", "ESPECIALISTA_EM",
    "ELETIVA_DE",
})
CORPO_RELACOES = frozenset({
    "PREREQUISITO_DE", "REQUER_BASE", "ABORDA", "LECIONA", "ESPECIALISTA_EM",
    "OFERECE", "ELETIVA_DE", "MATRIZ_DE",
})


def _coletar(kg) -> Dict[str, Set[Tuple[str, str]]]:
    """{relacao: {(u, v), ...}} a partir das arestas do KG."""
    rels: Dict[str, Set[Tuple[str, str]]] = defaultdict(set)
    for u, v, data in kg.graph.edges(data=True):
        r = data.get("relacao")
        if r:
            rels[r].add((u, v))
    return rels


def _indice_fwd(pares: Set[Tuple[str, str]]) -> Dict[str, Set[str]]:
    """u -> {v, ...} para juntar corpos rapidamente."""
    fwd: Dict[str, Set[str]] = defaultdict(set)
    for u, v in pares:
        fwd[u].add(v)
    return fwd


def minerar_regras(kg, min_support: int = 3, min_conf: float = 0.5,
                   min_body: int = 5) -> List[dict]:
    """
    Minera regras de composição (comprimento 2) do KG.

    Args:
        min_support: mínimo de instâncias corpo∧cabeça para reter a regra.
        min_conf:    confiança mínima (support/body).
        min_body:    mínimo de groundings do corpo (evita regra de amostra ínfima).
    """
    rels = _coletar(kg)
    presentes = [r for r in rels if r in CORPO_RELACOES]

    # Expande com relações INVERSAS (r_INV): permite regras que compartilham o
    # tail, como aborda(A,C) ∧ requer_base_inv(C,B), o padrão útil do domínio.
    expandido: Dict[str, Set[Tuple[str, str]]] = {}
    for r in presentes:
        expandido[r] = rels[r]
        expandido[r + "_INV"] = {(v, u) for (u, v) in rels[r]}
    fwd = {r: _indice_fwd(pares) for r, pares in expandido.items()}
    corpo_rels = list(expandido)

    regras: List[dict] = []
    for r1 in corpo_rels:
        for r2 in corpo_rels:
            if r1.replace("_INV", "") == r2.replace("_INV", "") and \
               r1.endswith("_INV") != r2.endswith("_INV"):
                continue  # r ∧ r_INV = laço trivial (x=z)
            # groundings do corpo: (x, z) tal que ∃y com r1(x,y) ∧ r2(y,z)
            corpo: Set[Tuple[str, str]] = set()
            for x, ys in fwd[r1].items():
                for y in ys:
                    for z in fwd[r2].get(y, ()):  # noqa: E1136
                        if x != z:                # descarta laços triviais
                            corpo.add((x, z))
            if len(corpo) < min_body:
                continue
            for r3 in rels:
                if r3 not in CABECAS_ALVO:
                    continue
                support = len(corpo & rels[r3])
                if support < min_support:
                    continue
                conf = support / len(corpo)
                if conf < min_conf:
                    continue
                regras.append({
                    "corpo": [(r1, "x", "y"), (r2, "y", "z")],
                    "cabeca": (r3, "x", "z"),
                    "support": support,
                    "body": len(corpo),
                    "confidence": round(conf, 3),
                    "transitiva": (r1 == r2 == r3),
                    "nova_relacao": r3 not in (r1, r2),
                })
    # ordena por confiança e depois por suporte
    regras.sort(key=lambda g: (-g["confidence"], -g["support"]))
    return regras


def _leg(r: str) -> str:
    return r[:-4] + "⁻¹" if r.endswith("_INV") else r


def formatar(regra: dict) -> str:
    """Representação legível: corpo → cabeça  [conf, support/body]."""
    corpo = " ∧ ".join(f"{_leg(r)}({a},{b})" for r, a, b in regra["corpo"])
    r, a, b = regra["cabeca"]
    return (f"{corpo} → {r}({a},{b})   "
            f"[conf {regra['confidence']:.0%}, sup {regra['support']}/{regra['body']}]")


def para_datalog(regra: dict, idx: int) -> Tuple[str, str, float]:
    """
    Converte para o formato do PyReasonEngine.RULES_DATALOG.
    Retorna (nome, regra_str, confidence). O bound [conf,1] é aplicado na
    injeção; aqui só entregamos a string Datalog e a confiança.
    """
    def _pred(r, a, b):
        return f"{r.lower()}({a}, {b})"
    corpo = ", ".join(_pred(r, a, b) for r, a, b in regra["corpo"])
    r, a, b = regra["cabeca"]
    nome = f"mined_{idx}_{r.lower()}"
    return nome, f"{_pred(r, a, b)} <-1 {corpo}", regra["confidence"]


# ── 1b. Aplicação das regras com propagação de crença ────────────────────────
def _conf_aresta(kg, u: str, v: str, rel: str) -> float:
    """Confiança da aresta (u -rel-> v); 1.0 se não anotada."""
    data = kg.graph.get_edge_data(u, v) or {}
    # MultiDiGraph: pode haver várias arestas u->v; pega a da relação certa.
    for _k, d in (data.items() if all(isinstance(x, dict) for x in data.values()) else [(0, data)]):
        if d.get("relacao") == rel:
            return float(d.get("confidence", 1.0))
    return 1.0


def aplicar_regras(kg, regras: List[dict], min_conf: float = 0.3) -> List[dict]:
    """
    Aplica as regras mineradas ao KG derivando relações INFERIDAS com crença
    (o que o PyReason faria: bound = confiança-da-regra × elo-mais-fraco-do-corpo).

    Retorna as inferências que NÃO são fatos curados (não sobrescreve verdade):
      [{cabeca, sujeito, objeto, crenca, via}]. Fatos curados mantêm [1,1].
    """
    rels = _coletar(kg)
    expand: Dict[str, Dict[str, Set[str]]] = {}
    for r in set(list(CORPO_RELACOES)):
        if r in rels:
            expand[r] = _indice_fwd(rels[r])
            expand[r + "_INV"] = _indice_fwd({(v, u) for (u, v) in rels[r]})

    inferidas: Dict[Tuple[str, str, str], dict] = {}
    for regra in regras:
        if regra["confidence"] < min_conf:
            continue
        (r1, _, _), (r2, _, _) = regra["corpo"]
        r3 = regra["cabeca"][0]
        if r1 not in expand or r2 not in expand:
            continue
        curadas = rels.get(r3, set())
        for x, ys in expand[r1].items():
            for y in ys:
                for z in expand[r2].get(y, ()):  # noqa: E1136
                    if x == z or (x, z) in curadas:
                        continue  # não inventa sobre fato já curado
                    b1 = _conf_aresta(kg, *( (x, y) if not r1.endswith("_INV") else (y, x)), r1.replace("_INV", ""))
                    b2 = _conf_aresta(kg, *( (y, z) if not r2.endswith("_INV") else (z, y)), r2.replace("_INV", ""))
                    crenca = round(regra["confidence"] * min(b1, b2), 3)
                    key = (r3, x, z)
                    if crenca > inferidas.get(key, {}).get("crenca", 0):
                        inferidas[key] = {
                            "cabeca": r3, "sujeito": x, "objeto": z,
                            "crenca": crenca, "via": _leg(r1) + "∧" + _leg(r2),
                        }
    return sorted(inferidas.values(), key=lambda d: -d["crenca"])


# ── 1b (real). Aplicar as regras NO PyReason, propagando bounds de crença ─────
def aplicar_regras_pyreason(kg, regras: List[dict], min_conf: float = 0.3,
                            timesteps: int = 3) -> List[dict]:
    """
    Injeta as regras mineradas no PyReason (o motor NSAI do projeto) e deixa ele
    derivar as relações inferidas propagando o bound [confidence, 1] de cada
    regra. Difere de `aplicar_regras` (forward-chaining Python) por usar o
    reasoner anotado de verdade. Retorna [{cabeca, sujeito, objeto, bound}].
    Levanta ImportError se o pyreason não estiver disponível.
    """
    import networkx as nx
    import pyreason as pr

    usadas = set()
    for g in regras:
        if g["confidence"] < min_conf:
            continue
        for (r, _, _) in g["corpo"]:
            usadas.add(r.replace("_INV", ""))
        usadas.add(g["cabeca"][0])

    # Subgrafo com IDs limpos (o parser do PyReason quebra com ':'/acentos) e
    # atributos escalares; adiciona a aresta inversa de cada relação usada.
    sg = nx.DiGraph()
    node_map: Dict[str, str] = {}

    def cid(nid: str) -> str:
        if nid not in node_map:
            node_map[nid] = f"n{len(node_map)}"
        return node_map[nid]

    for u, v, d in kg.graph.edges(data=True):
        r = d.get("relacao")
        if r in usadas:
            cu, cv = cid(u), cid(v)
            sg.add_edge(cu, cv, **{r.lower(): 1})
            sg.add_edge(cv, cu, **{r.lower() + "_inv": 1})

    pr.reset(); pr.reset_rules(); pr.reset_settings()
    pr.settings.verbose = False
    pr.settings.atom_trace = False
    pr.load_graph(sg)

    cabecas: Set[str] = set()
    for i, g in enumerate(regras):
        if g["confidence"] < min_conf:
            continue
        (r1, _, _), (r2, _, _) = g["corpo"]
        head = g["cabeca"][0].lower() + "_inf"
        p1, p2 = r1.lower(), r2.lower()
        rule_str = f"{head}(x, z) : [{g['confidence']}, 1] <-1 {p1}(x, y), {p2}(y, z)"
        pr.add_rule(pr.Rule(rule_str, f"mined_{i}", infer_edges=True))
        cabecas.add(head)

    interp = pr.reason(timesteps=timesteps)
    id2node = {v: k for k, v in node_map.items()}
    out: List[dict] = []
    for head in cabecas:
        dfs = pr.filter_and_sort_edges(interp, [head])
        if not dfs:
            continue
        for _, row in dfs[-1].iterrows():
            comp = row["component"]
            bound = list(row[head])
            out.append({
                "cabeca": head.replace("_inf", "").upper(),
                "sujeito": id2node.get(comp[0], comp[0]),
                "objeto": id2node.get(comp[1], comp[1]),
                "bound": [round(float(bound[0]), 3), round(float(bound[1]), 3)],
            })
    return sorted(out, key=lambda d: -d["bound"][0])


# ── 2. Ligar conceito ↔ área via docentes (fecha a lacuna do KG) ──────────────
def ligar_conceito_area(kg, min_evidencia: int = 2) -> List[dict]:
    """
    Deriva pertence_a(conceito, area) sem embeddings, usando só o KG:
        especialista_em(D, A) ∧ leciona(D, X) ∧ aborda(X, C) → pertence_a(C, A)
    Crença = fração das evidências do conceito C que apontam para a área A
    (distribuição de áreas por conceito). Liga o espaço granular (conceitos) ao
    temático (áreas), destravando a regra de especialista e recomendações.
    """
    rels = _coletar(kg)
    esp = _indice_fwd(rels.get("ESPECIALISTA_EM", set()))   # D -> {A}
    lec = _indice_fwd(rels.get("LECIONA", set()))           # D -> {X}
    abr = _indice_fwd(rels.get("ABORDA", set()))            # X -> {C}

    from collections import Counter
    evid: Dict[str, Counter] = defaultdict(Counter)          # C -> {A: peso}
    for d, areas in esp.items():
        for x in lec.get(d, ()):                             # noqa: E1136
            for c in abr.get(x, ()):                          # noqa: E1136
                for a in areas:
                    evid[c][a] += 1

    saida: List[dict] = []
    for c, cnt in evid.items():
        total = sum(cnt.values())
        if total < min_evidencia:
            continue
        for a, w in cnt.most_common(3):
            saida.append({
                "conceito": c, "area": a,
                "crenca": round(w / total, 3), "evidencia": w,
            })
    return sorted(saida, key=lambda d: -d["crenca"])


# ── Link prediction validado (held-out, sem circularidade) ───────────────────
def avaliar_especialista_holdout(kg, n_folds: int = 5, top_k: int = 3) -> dict:
    """
    Valida a predição de especialista_em(D, A) por k-fold sobre os DOCENTES.

    Em cada fold: o mapa conceito→área é derivado SÓ dos docentes de treino
    (pertence_a a partir dos especialistas de treino); depois prevê as áreas dos
    docentes de teste via leciona(D,X) ∧ aborda(X,C) ∧ pertence_a(C,A) e compara
    com os especialista_em REAIS deles. Sem circularidade (o mapa nunca viu o
    docente avaliado). Retorna precision/recall/F1 médios (top-k por docente).
    """
    from collections import Counter
    rels = _coletar(kg)
    esp = _indice_fwd(rels.get("ESPECIALISTA_EM", set()))   # D -> {A}
    lec = _indice_fwd(rels.get("LECIONA", set()))
    abr = _indice_fwd(rels.get("ABORDA", set()))
    docentes = sorted(d for d in esp if lec.get(d))         # docentes avaliáveis
    if len(docentes) < n_folds:
        return {"erro": "poucos docentes com especialista_em+leciona"}

    folds = [docentes[i::n_folds] for i in range(n_folds)]
    precs, recs = [], []
    for f in range(n_folds):
        teste = set(folds[f])
        treino = [d for d in docentes if d not in teste]
        # pertence_a(C, A) só do treino
        pa: Dict[str, Counter] = defaultdict(Counter)
        for d in treino:
            for x in lec.get(d, ()):                        # noqa: E1136
                for c in abr.get(x, ()):                     # noqa: E1136
                    for a in esp[d]:
                        pa[c][a] += 1
        # prevê e mede em cada docente de teste
        for d in teste:
            score: Counter = Counter()
            for x in lec.get(d, ()):                         # noqa: E1136
                for c in abr.get(x, ()):                      # noqa: E1136
                    tot = sum(pa[c].values())
                    if tot:
                        for a, w in pa[c].items():
                            score[a] += w / tot
            pred = {a for a, _ in score.most_common(top_k)}
            real = esp[d]
            if not pred:
                precs.append(0.0); recs.append(0.0); continue
            inter = len(pred & real)
            precs.append(inter / len(pred))
            recs.append(inter / len(real) if real else 0.0)

    import statistics as st
    p = st.mean(precs) if precs else 0.0
    r = st.mean(recs) if recs else 0.0
    f1 = 2 * p * r / (p + r) if (p + r) else 0.0
    return {"n_docentes": len(docentes), "folds": n_folds, "top_k": top_k,
            "precision": round(p, 3), "recall": round(r, 3), "f1": round(f1, 3)}


# ── Sinais para link prediction de pré-requisito (scorer combinado) ───────────
def _tokens_ementa(texto: str) -> List[str]:
    t = unicodedata.normalize("NFD", (texto or "").lower())
    t = "".join(c for c in t if unicodedata.category(c) != "Mn")
    return [w for w in re.findall(r"[a-z]{3,}", t) if w not in _STOP_PT]


def _sinais_prereq(kg) -> dict:
    """
    Pré-computa os sinais do link prediction de pré-requisito e CACHEIA por KG
    (o TF-IDF das ementas é caro para reconstruir a cada consulta):
    conceitos (aborda/base), IDF conceitual, termo, docentes e vetores TF-IDF
    normalizados das ementas (para o cosseno textual).
    """
    cached = _SINAIS_CACHE.get(kg)
    if cached is not None:
        return cached

    rels = _coletar(kg)
    aborda = _indice_fwd(rels.get("ABORDA", set()))
    req = _indice_fwd(rels.get("REQUER_BASE", set()))
    docs = _indice_fwd({(v, u) for (u, v) in rels.get("LECIONA", set())})
    discs = [n for n, d in kg.graph.nodes(data=True) if d.get("tipo") == "disciplina"]
    termo = {n: kg.graph.nodes[n].get("termo") for n in discs}
    n = max(1, len(discs))
    df: Dict[str, int] = defaultdict(int)
    for a in discs:
        for c in aborda.get(a, set()):
            df[c] += 1
    idf = {c: math.log(n / (df[c] or 1)) for c in df}

    # TF-IDF normalizado das ementas (para cosseno)
    ement = {a: _tokens_ementa(kg.graph.nodes[a].get("ementa", "")) for a in discs}
    dfw: Dict[str, int] = defaultdict(int)
    for a in discs:
        for w in set(ement[a]):
            dfw[w] += 1
    idfw = {w: math.log(n / (dfw[w] or 1)) for w in dfw}
    vec: Dict[str, Dict[str, float]] = {}
    for a in discs:
        tf = Counter(ement[a])
        v = {w: (1 + math.log(c)) * idfw[w] for w, c in tf.items()}
        norm = math.sqrt(sum(x * x for x in v.values())) or 1.0
        vec[a] = {w: x / norm for w, x in v.items()}

    dados = {"aborda": aborda, "req": req, "docs": docs, "discs": discs,
             "termo": termo, "idf": idf, "vec": vec,
             "prereq": rels.get("PREREQUISITO_DE", set())}
    try:
        _SINAIS_CACHE[kg] = dados
    except TypeError:
        pass  # KG não-weakref-able: sem cache, ainda funciona
    return dados


def _cos_ementa(a: str, b: str, vec: Dict[str, Dict[str, float]]) -> float:
    va, vb = vec.get(a, {}), vec.get(b, {})
    if len(va) > len(vb):
        va, vb = vb, va
    return sum(x * vb.get(w, 0.0) for w, x in va.items())


def _score_prereq(a: str, b: str, conc_b: Set[str], s: dict) -> float:
    """
    Score combinado de "A é pré-requisito de B" (melhor no held-out que só
    overlap): overlap conceitual ponderado por IDF, com fator de ordem curricular
    (termo: A antes de B) e bônus por docentes em comum.
    """
    overlap = s["aborda"].get(a, set()) & conc_b
    base = sum(s["idf"].get(c, 0.0) for c in overlap)
    em = _W_EMENTA * _cos_ementa(a, b, s["vec"]) if s.get("vec") else 0.0
    if base == 0.0 and em == 0.0:
        return 0.0
    ta, tb = s["termo"].get(a), s["termo"].get(b)
    fator = 1.0
    if ta and tb:
        fator = 1.5 if ta < tb else 0.15   # pré-requisito vem antes
    bonus = 0.5 * len(s["docs"].get(a, set()) & s["docs"].get(b, set()))
    return (base + em) * fator + bonus


# ── Sugestão de pré-requisitos prováveis (link prediction para o pipeline) ────
def sugerir_prereqs(kg, alvo_nome: str, top_k: int = 3,
                    min_crenca: float = 0.15) -> List[dict]:
    """
    Sugere pré-requisitos PROVÁVEIS (não curados) para uma disciplina. Ranqueia
    pelo scorer combinado (conceito+IDF+termo+docente); a crença reportada é a
    fração dos conceitos-base de B cobertos por A (interpretável).

    Camada APRENDIDA: exclui os pré-requisitos já curados (não sobrescreve
    verdade); o consumidor deve apresentar como sugestão com incerteza.
    """
    node = kg._find_node(alvo_nome, "disciplina")
    if not node:
        return []
    s = _sinais_prereq(kg)
    curados = {a for (a, b) in s["prereq"] if b == node}
    conc_b = s["req"].get(node, set()) | s["aborda"].get(node, set())
    if not conc_b:
        return []
    cand = []
    for a in s["discs"]:
        if a == node or a in curados:
            continue
        sc = _score_prereq(a, node, conc_b, s)
        if sc > 0:
            cand.append((a, sc))
    cand.sort(key=lambda x: -x[1])
    out = []
    for a, _sc in cand[:top_k]:
        cob = len(s["aborda"].get(a, set()) & conc_b)
        crenca = round(cob / len(conc_b), 3)
        if crenca >= min_crenca:
            out.append({
                "candidato": kg.graph.nodes[a].get("nome", a),
                "crenca": crenca, "conceitos": cob,
            })
    return out


# ── Link prediction de PRÉ-REQUISITO (alvo estruturado, sinal conceitual) ─────
def avaliar_prereq_holdout(kg, n_folds: int = 5, ks=(1, 3, 5, 10)) -> dict:
    """
    Prediz PREREQUISITO_DE faltante pelo sinal conceitual e valida held-out.

    Hipótese: A tende a ser pré-requisito de B se A ABORDA os conceitos que B
    REQUER como base. Em cada fold escondemos uma fatia das arestas prereq e,
    para cada alvo B, ranqueamos candidatos A por |aborda(A) ∩ requer_base(B)|,
    medindo recall@k e MRR sobre os prereqs escondidos. Sem circularidade (o
    sinal é conceitual, não usa as arestas prereq escondidas).
    """
    sig = _sinais_prereq(kg)
    prereq = sorted(sig["prereq"])
    if len(prereq) < n_folds:
        return {"erro": "poucas arestas PREREQUISITO_DE"}
    aborda, req, discs = sig["aborda"], sig["req"], sig["discs"]

    folds = [prereq[i::n_folds] for i in range(n_folds)]
    rec = {k: [] for k in ks}
    rr = []
    for f in range(n_folds):
        escondidas = folds[f]
        # alvo B -> conjunto de prereqs reais escondidos
        alvo: Dict[str, Set[str]] = defaultdict(set)
        for a, b in escondidas:
            alvo[b].add(a)
        for b, reais in alvo.items():
            conc_b = req.get(b, set()) | aborda.get(b, set())
            if not conc_b:
                for k in ks:
                    rec[k].append(0.0)
                rr.append(0.0)
                continue
            # ranqueia candidatos A pelo scorer combinado (conc+idf+termo+doc)
            ranking = []
            for a in discs:
                if a == b:
                    continue
                s = _score_prereq(a, b, conc_b, sig)
                if s > 0:
                    ranking.append((s, a))
            ranking.sort(key=lambda x: -x[0])
            ordem = [a for _, a in ranking]
            for k in ks:
                topk = set(ordem[:k])
                rec[k].append(len(topk & reais) / len(reais))
            # MRR do primeiro acerto
            mrr = 0.0
            for pos, a in enumerate(ordem, 1):
                if a in reais:
                    mrr = 1.0 / pos
                    break
            rr.append(mrr)

    import statistics as st
    out = {"n_arestas": len(prereq), "folds": n_folds,
           "mrr": round(st.mean(rr), 3) if rr else 0.0}
    for k in ks:
        out[f"recall@{k}"] = round(st.mean(rec[k]), 3) if rec[k] else 0.0
    return out


def _build_kg():
    """Constrói o KG da graduação a partir dos markdowns (para o CLI/teste)."""
    import os
    from .knowledge_graph import KnowledgeGraph
    kg = KnowledgeGraph()
    reg = "markdown_regimentos" if os.path.isdir("markdown_regimentos") else "markdown_disciplinas"
    kg.build_from_directories("markdown_disciplinas", reg, None, "markdown_cursos")
    return kg


if __name__ == "__main__":
    kg = _build_kg()
    regras = minerar_regras(kg)
    print(f"\n{len(regras)} regras mineradas (min_conf=0.5, min_support=3):\n")
    for g in regras[:30]:
        marca = " [transitiva]" if g["transitiva"] else (
            " [nova relação]" if g["nova_relacao"] else "")
        print("  " + formatar(g) + marca)
