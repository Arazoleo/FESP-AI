"""
Raciocinador NSAI do FESP-AI, inteiramente no PyReason (lógica anotada, bounds [l,u]).

Cinco capacidades, todas no MESMO motor e com a mesma política de crença
(curado = [1,1]; aprendido = [l,1] com l < 1; nada aprendido vira fato duro):

1. Crença nativa: as dependências entre disciplinas (pré-requisito curado OU
   sugerido por link prediction) são propagadas pelo PyReason com semântica de
   Gödel — mínimo ao longo do caminho, máximo entre caminhos. Implementado com
   NÍVEIS discretos de crença em vez de função de anotação: cláusula
   `dep(x,y):[L,1]` só casa se a crença do elo for >= L, e a cabeça recebe
   [L,1]; várias regras disparando se intersectam e fica o maior L. (Funções de
   anotação entram no kernel do numba como dispatchers e quebram o cache entre
   processos: cada boot recompilaria ~10 min.)

2. Regras aprendidas com confiança CALIBRADA: as regras do rule_miner são
   reavaliadas em validação cruzada (arestas da cabeça escondidas); a precisão
   no held-out (suavizada por Laplace) vira o bound da regra no PyReason. Cada
   rodada é registrada em REGISTRO, então uma regra ganha ou perde confiança
   ao longo do tempo e é desativada se cair abaixo do piso.

3. Tempo: `projetar()` roda o PyReason com um timestep por SEMESTRE. Regras
   ground, uma por disciplina, exigem a conjunção exata dos pré-requisitos
   aprovados e a oferta naquele semestre (paridade do termo nas matrizes).
   Resultado: o semestre mais cedo em que cada disciplina pode ser concluída.

4. Explicação: atom_trace ligado; cada conclusão guarda a regra e os átomos
   das cláusulas que a produziram, expandidos recursivamente em `explicar_*`.

5. Inconsistência entre fontes: fatos de fontes diferentes sobre o mesmo átomo
   com bounds disjuntos são detectados pelo PyReason (inconsistency_check) e
   reportados com as fontes, em vez de uma fonte vencer em silêncio:
     - ordem: ficha da UC diz "A é pré-requisito de B" × matriz põe A no mesmo
       termo ou depois de B;
     - oferta: matriz prevê a UC neste semestre (paridade do termo) × agenda de
       salas do semestre não tem turma.
"""

from __future__ import annotations

import json
import math
import os
import random
import threading
import time
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

import networkx as nx

try:
    from .pyreason_engine import PYREASON_LOCK
except ImportError:  # módulo carregado fora do pacote (testes)
    from pyreason_engine import PYREASON_LOCK

NIVEIS: Tuple[float, ...] = (1.0, 0.6, 0.4, 0.2)
PISO_REGRA = 0.1          # regra calibrada abaixo disso é desativada
MIN_PREDICOES = 5         # regra que quase não prevê nada não é calibrável
LIMITE_CREDITOS = 24      # planner.DEFAULT_MAX_CREDITOS

ROOT = Path(__file__).resolve().parents[1]
REGISTRO = Path(os.getenv("FESPAI_NSAI_REGISTRO",
                          ROOT / "chroma_db_unifesp" / "regras_nsai.jsonl"))
OFERTA_JSON = ROOT / "jsons_regimentos" / "oferta_semestre.json"


def nivel(p: float) -> Optional[float]:
    """Maior nível de crença <= p (None se abaixo do menor nível)."""
    for L in NIVEIS:
        if p >= L - 1e-9:
            return L
    return None


def _pr_novo(persistent: bool = True):
    import pyreason as pr

    pr.reset()
    pr.reset_rules()
    pr.reset_settings()
    pr.settings.verbose = False
    pr.settings.memory_profile = False
    pr.settings.atom_trace = True
    pr.settings.persistent = persistent
    pr.settings.allow_ground_rules = True
    pr.settings.inconsistency_check = True
    return pr


def _bound(v) -> Tuple[float, float]:
    try:
        return float(v[0]), float(v[1])
    except Exception:
        return 0.0, 1.0


# ─────────────────────────────── 2. calibração ───────────────────────────────

class _KGParcial:
    """Visão do KG sem as arestas escondidas (o que aplicar_regras precisa)."""

    def __init__(self, kg, escondidas: Set[Tuple[str, str, str]]):
        g = nx.MultiDiGraph()
        g.add_nodes_from(kg.graph.nodes(data=True))
        for u, v, d in kg.graph.edges(data=True):
            if (d.get("relacao"), u, v) not in escondidas:
                g.add_edge(u, v, **d)
        self.graph = g


def calibrar_regras(kg, folds: int = 5, semente: int = 13,
                    regras: Optional[List[dict]] = None) -> List[dict]:
    """
    Reavalia cada regra minerada em validação cruzada sobre as arestas da
    cabeça. precisão = acertos / previsões novas; confiança calibrada =
    (acertos + 1) / (previsões + 2). Mundo aberto: previsões corretas mas
    ausentes do KG contam como erro, então a calibração é conservadora.
    """
    try:
        from .rule_miner import aplicar_regras, minerar_regras
    except ImportError:
        from rule_miner import aplicar_regras, minerar_regras

    regras = regras if regras is not None else minerar_regras(kg, min_conf=0.15)
    if not regras:
        return []
    cabecas = {r["cabeca"][0] for r in regras}
    por_rel: Dict[str, List[Tuple[str, str]]] = defaultdict(list)
    for u, v, d in kg.graph.edges(data=True):
        if d.get("relacao") in cabecas:
            por_rel[d["relacao"]].append((u, v))

    rnd = random.Random(semente)
    particoes: Dict[str, List[List[Tuple[str, str]]]] = {}
    for rel, arestas in por_rel.items():
        arestas = sorted(arestas)
        rnd.shuffle(arestas)
        particoes[rel] = [arestas[i::folds] for i in range(folds)]

    stats = [{"acertos": 0, "previsoes": 0, "escondidas": 0} for _ in regras]
    for f in range(folds):
        escondidas = {(rel, u, v) for rel, parts in particoes.items() for (u, v) in parts[f]}
        parcial = _KGParcial(kg, escondidas)
        for i, regra in enumerate(regras):
            rel = regra["cabeca"][0]
            alvo = {(u, v) for (r, u, v) in escondidas if r == rel}
            prev = {(d["sujeito"], d["objeto"])
                    for d in aplicar_regras(parcial, [regra], min_conf=0.0)}
            stats[i]["acertos"] += len(prev & alvo)
            stats[i]["previsoes"] += len(prev)
            stats[i]["escondidas"] += len(alvo)

    saida = []
    for regra, s in zip(regras, stats):
        prec = s["acertos"] / s["previsoes"] if s["previsoes"] else 0.0
        cal = (s["acertos"] + 1) / (s["previsoes"] + 2)
        ativa = s["previsoes"] >= MIN_PREDICOES and cal >= PISO_REGRA
        saida.append({
            **regra,
            "precisao_holdout": round(prec, 3),
            "recall_holdout": round(s["acertos"] / s["escondidas"], 3) if s["escondidas"] else 0.0,
            "previsoes_holdout": s["previsoes"],
            "confianca_calibrada": round(cal, 3),
            "ativa": ativa,
        })
    return saida


def _chave_regra(regra: dict) -> str:
    corpo = "∧".join(f"{r}({a},{b})" for r, a, b in regra["corpo"])
    r, a, b = regra["cabeca"]
    return f"{corpo}→{r}({a},{b})"


def registrar(calibradas: List[dict], caminho: Path = REGISTRO) -> List[dict]:
    """Anexa a rodada ao registro e devolve cada regra com a variação vs. a rodada anterior."""
    anteriores: Dict[str, float] = {}
    try:
        for linha in caminho.read_text(encoding="utf-8").splitlines():
            d = json.loads(linha)
            anteriores[d["regra"]] = d["confianca_calibrada"]
    except (OSError, ValueError):
        pass
    agora = time.strftime("%Y-%m-%dT%H:%M:%S")
    linhas, saida = [], []
    for r in calibradas:
        chave = _chave_regra(r)
        ant = anteriores.get(chave)
        reg = {"ts": agora, "regra": chave,
               "confianca_amie": r.get("confidence"),
               "confianca_calibrada": r["confianca_calibrada"],
               "precisao_holdout": r["precisao_holdout"],
               "recall_holdout": r["recall_holdout"],
               "previsoes_holdout": r["previsoes_holdout"],
               "ativa": r["ativa"],
               "variacao": None if ant is None else round(r["confianca_calibrada"] - ant, 3)}
        linhas.append(json.dumps(reg, ensure_ascii=False))
        saida.append(reg)
    try:
        caminho.parent.mkdir(parents=True, exist_ok=True)
        with open(caminho, "a", encoding="utf-8") as f:
            f.write("\n".join(linhas) + "\n")
    except OSError:
        pass
    return saida


# ───────────────────────────── dados auxiliares ──────────────────────────────

def _termos(kg) -> Dict[str, Dict[str, int]]:
    """{disc_id: {matriz_id: termo}} a partir das arestas INCLUI."""
    t: Dict[str, Dict[str, int]] = defaultdict(dict)
    for u, v, d in kg.graph.edges(data=True):
        if d.get("relacao") == "INCLUI":
            try:
                t[v][u] = int(d.get("termo"))
            except (TypeError, ValueError):
                pass
    return t


def _creditos(kg, disc_id: str) -> Optional[int]:
    for u, v, d in kg.graph.in_edges(disc_id, data=True):
        if d.get("relacao") == "INCLUI" and d.get("creditos"):
            try:
                return int(float(d["creditos"]))
            except (TypeError, ValueError):
                pass
    return None


def _paridade(termos: Dict[str, int]) -> Optional[int]:
    """1 = termo ímpar (1º semestre do ano), 2 = par; None se as matrizes divergem."""
    ps = {1 if t % 2 else 2 for t in termos.values()}
    return ps.pop() if len(ps) == 1 else None


def _semestre_atual() -> Tuple[int, int]:
    try:
        sem = json.loads(OFERTA_JSON.read_text(encoding="utf-8"))["semestre"]
        a, s = sem.split("/")
        return int(a), int(s)
    except Exception:
        lt = time.localtime()
        return lt.tm_year, 1 if lt.tm_mon <= 6 else 2


def _avanca(ano: int, sem: int, k: int) -> Tuple[int, int]:
    idx = ano * 2 + (sem - 1) + k
    return idx // 2, idx % 2 + 1


def _oferta_atual(kg) -> Tuple[Optional[str], Set[str]]:
    """(rótulo do semestre, ids das disciplinas com turma na agenda)."""
    try:
        dados = json.loads(OFERTA_JSON.read_text(encoding="utf-8"))
    except Exception:
        return None, set()
    ids = set()
    for nome in dados.get("disciplinas", {}):
        nid = kg._find_node(nome, "disciplina")
        if nid:
            ids.add(nid)
    return dados.get("semestre"), ids


# ───────────────────────────── o raciocinador ────────────────────────────────

class RaciocinadorNSAI:
    def __init__(self, kg):
        self.kg = kg
        self.pronto = False
        self.erro: Optional[str] = None
        self.duracao: Dict[str, float] = {}
        self.regras: List[dict] = []            # calibradas + registro
        self.dep: Dict[Tuple[str, str], float] = {}          # (a,b) nomes -> crença
        self._prova: Dict[Tuple[str, str, str], Tuple[str, list, list]] = {}
        self.inferidas: List[dict] = []
        self.inconsistencias: List[dict] = []
        self._id: Dict[str, str] = {}           # kg id -> id limpo
        self._kg: Dict[str, str] = {}           # id limpo -> kg id
        self._sugestoes: Dict[Tuple[str, str], float] = {}
        self._fontes: Dict[Tuple[str, Tuple[str, ...]], List[str]] = defaultdict(list)

    # ── ids ──
    def _cid(self, nid: str) -> str:
        if nid not in self._id:
            c = f"n{len(self._id)}"
            self._id[nid] = c
            self._kg[c] = nid
        return self._id[nid]

    def _nome(self, c: str) -> str:
        nid = self._kg.get(c, c)
        return self.kg.graph.nodes.get(nid, {}).get("nome", nid)

    # ── construção ──
    def construir(self, calibrar: bool = True) -> "RaciocinadorNSAI":
        try:
            t0 = time.time()
            if calibrar:
                cal = calibrar_regras(self.kg)
                hist = {h["regra"]: h for h in registrar(cal)}
                self.regras = [{**r, "variacao": hist.get(_chave_regra(r), {}).get("variacao")}
                               for r in cal]
            self.duracao["calibracao"] = round(time.time() - t0, 1)
            t0 = time.time()
            with PYREASON_LOCK:
                self._programa_global()
            self.duracao["programa_global"] = round(time.time() - t0, 1)
            self.pronto = True
        except Exception as e:  # nunca derruba o app: as respostas degradam sem a camada
            self.erro = f"{type(e).__name__}: {e}"
        return self

    def _programa_global(self) -> None:
        kg = self.kg
        pr = _pr_novo(persistent=True)
        g = nx.DiGraph()
        discs = [n for n, d in kg.graph.nodes(data=True) if d.get("tipo") == "disciplina"]
        for n in discs:
            g.add_node(self._cid(n))

        # curados
        prereqs = [(u, v) for u, v, d in kg.graph.edges(data=True)
                   if d.get("relacao") == "PREREQUISITO_DE"]
        for u, v in prereqs:
            g.add_edge(self._cid(u), self._cid(v), prereq=1)

        # (1) sugestões de link prediction como fatos com crença [L,1]
        try:
            from .rule_miner import sugerir_prereqs
        except ImportError:
            from rule_miner import sugerir_prereqs
        fatos: List[Tuple[str, str]] = []
        for v in discs:
            nome_v = kg.graph.nodes[v].get("nome", v)
            try:
                sugs = sugerir_prereqs(kg, nome_v, top_k=3)
            except Exception:
                sugs = []
            for s in sugs:
                nome_u, crenca = s.get("candidato"), float(s.get("crenca", 0))
                u = kg._find_node(nome_u, "disciplina") if nome_u else None
                L = nivel(crenca)
                if not u or L is None or u == v:
                    continue
                cu, cv = self._cid(u), self._cid(v)
                g.add_edge(cu, cv)
                self._sugestoes[(cu, cv)] = crenca
                fatos.append((f"prereq_sug({cu},{cv}):[{L},1]", f"linkpred_{cu}_{cv}"))

        # (2) regras aprendidas calibradas: relações do corpo como atributos
        ativas = [r for r in self.regras if r.get("ativa")]
        usadas = {r.replace("_INV", "") for g_ in ativas for (r, _, _) in g_["corpo"]}
        usadas |= {g_["cabeca"][0] for g_ in ativas}
        for u, v, d in kg.graph.edges(data=True):
            r = d.get("relacao")
            if r in usadas:
                cu, cv = self._cid(u), self._cid(v)
                g.add_edge(cu, cv, **{r.lower(): 1})
                g.add_edge(cv, cu, **{r.lower() + "_inv": 1})

        # (5a) ordem: ficha × matriz
        termos = _termos(kg)
        for u, v in prereqs:
            for m, tu in termos.get(u, {}).items():
                tv = termos.get(v, {}).get(m)
                if tv is not None and tu >= tv:
                    cu, cv = self._cid(u), self._cid(v)
                    nome = f"matriz_{len(fatos)}"
                    self._fontes[("antes", (cu, cv))].append(
                        f"matriz {m.split(':', 1)[-1]}: {self._nome(cu)} no termo {tu}, "
                        f"{self._nome(cv)} no termo {tv}")
                    fatos.append((f"antes({cu},{cv}):[0,0]", nome))

        # (5b) oferta: matriz (paridade) × agenda do semestre
        rotulo, na_agenda = _oferta_atual(kg)
        if rotulo:
            sem = int(rotulo.split("/")[1])
            for n in discs:
                par = _paridade(termos.get(n, {}))
                if par is None or not termos.get(n):
                    continue
                c = self._cid(n)
                if par == sem:
                    fatos.append((f"ofertada({c})", f"matriz_paridade_{c}"))
                    self._fontes[("ofertada", (c,))].append(
                        f"matriz: termo {sorted(set(termos[n].values()))} → oferta no {sem}º semestre")
                    if n not in na_agenda:
                        fatos.append((f"ofertada({c}):[0,0]", f"agenda_sem_turma_{c}"))
                        self._fontes[("ofertada", (c,))].append(
                            f"agenda de salas {rotulo}: nenhuma turma")

        pr.load_graph(g)
        for texto, nome in fatos:
            # Fatos de FONTE (ordem, oferta) não podem ser static: com static o
            # primeiro fato congela o átomo e o segundo é ignorado em silêncio
            # (uma fonte "vence" sem aviso). Sem static, o PyReason detecta os
            # bounds disjuntos, registra a inconsistência e deixa [0,1].
            fonte = texto.startswith(("antes(", "ofertada("))
            pr.add_fact(pr.Fact(texto, nome, 0, 0, static=not fonte))

        # Caminho = elos curados* + no máximo UM elo sugerido + elos curados*.
        # Palpite não se encadeia com palpite: sem isso, sugestões de 10-20%
        # ligavam quase toda disciplina a toda outra (6.4 mil dependências).
        pr.add_rule(pr.Rule("curado(x,y) <-0 prereq(x,y)", "dep_curado", infer_edges=True))
        pr.add_rule(pr.Rule("curado(x,z) <-0 prereq(x,y), curado(y,z)", "dep_curado_trans",
                            infer_edges=True))
        pr.add_rule(pr.Rule("dep(x,y) <-0 curado(x,y)", "dep_de_curado", infer_edges=True))
        for L in NIVEIS[1:]:
            c = f":[{L},1]"
            pr.add_rule(pr.Rule(f"sug(x,y){c} <-0 prereq_sug(x,y){c}", f"dep_sugerido_{L}",
                                infer_edges=True))
            pr.add_rule(pr.Rule(f"sug(x,z){c} <-0 curado(x,y), sug(y,z){c}",
                                f"dep_curado_antes_{L}", infer_edges=True))
            pr.add_rule(pr.Rule(f"sug(x,z){c} <-0 sug(x,y){c}, curado(y,z)",
                                f"dep_curado_depois_{L}", infer_edges=True))
            pr.add_rule(pr.Rule(f"dep(x,y){c} <-0 sug(x,y){c}", f"dep_incerta_{L}",
                                infer_edges=True))
        pr.add_rule(pr.Rule("antes(x,y) <-0 prereq(x,y)", "ficha_prereq"))
        self._regras_mineradas: Dict[str, dict] = {}
        for i, r in enumerate(ativas):
            (r1, _, _), (r2, _, _) = r["corpo"]
            head = r["cabeca"][0].lower() + "_inf"
            nome = f"aprendida_{i}"
            self._regras_mineradas[nome] = r
            pr.add_rule(pr.Rule(
                f"{head}(x,z):[{r['confianca_calibrada']},1] <-1 {r1.lower()}(x,y), {r2.lower()}(y,z)",
                nome, infer_edges=True))

        # Regras <-0: tudo converge no ponto fixo do timestep 0; as regras
        # aprendidas são <-1 e precisam de um passo a mais.
        interp = pr.reason(timesteps=1)
        self._extrair(pr, interp, ativas)

    def _extrair(self, pr, interp, ativas) -> None:
        # bounds finais (persistente: a última mudança de cada átomo vale)
        finais: Dict[Tuple[str, Tuple[str, ...]], Tuple[float, float]] = {}
        labels_edge = ["dep", "antes"] + [r["cabeca"][0].lower() + "_inf" for r in ativas]
        for df in pr.filter_and_sort_edges(interp, labels_edge):
            for row in df.to_dict("records"):
                comp = tuple(row["component"])
                for lab in labels_edge:
                    if lab in row and row[lab] is not None:
                        b = _bound(row[lab])
                        if b != (0.0, 1.0) or lab == "antes":
                            finais[(lab, comp)] = b
        for df in pr.filter_and_sort_nodes(interp, ["ofertada"]):
            for row in df.to_dict("records"):
                finais[("ofertada", (row["component"],))] = _bound(row["ofertada"])

        # prova (4): regra + átomos das cláusulas da derivação que fixou o bound
        node_tr, edge_tr = pr.get_rule_trace(interp)
        inconsist: Dict[Tuple[str, Tuple[str, ...]], str] = {}
        for tr, eh_edge in ((edge_tr, True), (node_tr, False)):
            if tr is None or len(tr) == 0:
                continue
            col = "Edge" if eh_edge else "Node"
            for row in tr.to_dict("records"):
                comp = tuple(row[col]) if eh_edge else (row[col],)
                chave = (row["Label"], comp)
                if row.get("Consistent") is False or row.get("Inconsistency Message"):
                    inconsist[chave] = row.get("Inconsistency Message") or "inconsistente"
                if row.get("Triggered By") == "Rule":
                    clauses = [row[k] for k in sorted(row) if k.startswith("Clause-") and row[k]]
                    novo = _bound(_parse_bound(row.get("New Bound")))
                    ant = self._prova.get((row["Label"],) + comp)
                    if ant is None or novo[0] >= ant[3]:
                        self._prova[(row["Label"],) + comp] = (row["Occurred Due To"], clauses, novo, novo[0])

        for (lab, comp), b in finais.items():
            if lab == "dep" and b[0] > 0:
                self.dep[(comp[0], comp[1])] = b[0]
            elif lab.endswith("_inf") and b[0] > 0:
                prova = self._prova.get((lab,) + comp)
                regra = self._regras_mineradas.get(prova[0]) if prova else None
                self.inferidas.append({
                    "relacao": lab[:-4].upper(), "sujeito": self._nome(comp[0]),
                    "objeto": self._nome(comp[1]), "bound": [round(b[0], 3), round(b[1], 3)],
                    "regra": _chave_regra(regra) if regra else None})

        # códigos de UC repetidos entre fichas (lint do KG, não do PyReason):
        # a resolução de pré-requisito por código fica ambígua
        try:
            for item in self.kg.lint().get("codigos_duplicados", []):
                codigo, nomes = item.split(": ", 1)
                self.inconsistencias.append({
                    "tipo": "codigo_duplicado", "disciplinas": nomes.split(" | "),
                    "fontes": [f"ficha de {n}: Código {codigo}" for n in nomes.split(" | ")],
                    "bound_final": None, "pyreason": None, "detector": "lint do KG"})
        except Exception:
            pass

        for (lab, comp), msg in inconsist.items():
            if lab not in ("antes", "ofertada"):
                continue
            fontes = list(self._fontes.get((lab, comp), []))
            if lab == "antes":
                fontes.insert(0, f"ficha de {self._nome(comp[1])}: {self._nome(comp[0])} é pré-requisito")
            self.inconsistencias.append({
                "tipo": "ordem" if lab == "antes" else "oferta",
                "disciplinas": [self._nome(c) for c in comp],
                "fontes": fontes,
                "bound_final": list(finais.get((lab, comp), (0.0, 1.0))),
                "pyreason": msg[:200], "detector": "pyreason (inconsistency_check)",
            })
        self.inferidas.sort(key=lambda d: -d["bound"][0])

    # ── consultas (1) e (4) ──
    def _c(self, nome: str) -> Optional[str]:
        nid = self.kg._find_node(nome, "disciplina")
        return self._id.get(nid) if nid else None

    def crenca_dependencia(self, antes_de: str, depois: str) -> Optional[float]:
        a, b = self._c(antes_de), self._c(depois)
        return self.dep.get((a, b)) if a and b else None

    def explicar_dependencia(self, antes_de: str, depois: str) -> List[str]:
        """Passos da prova de dep(antes_de, depois), lidos do rule trace do PyReason."""
        a, b = self._c(antes_de), self._c(depois)
        return self._explicar("dep", a, b, set()) if a and b else []

    # rótulo de cada cláusula, por prefixo do nome da regra
    _CLAUSULAS = (
        ("dep_curado_trans", ("prereq", "curado")),
        ("dep_curado_antes", ("curado", "sug")),
        ("dep_curado_depois", ("sug", "curado")),
        ("dep_de_curado", ("curado",)),
        ("dep_incerta", ("sug",)),
        ("dep_sugerido", ("prereq_sug",)),
        ("dep_curado", ("prereq",)),
    )

    def _explicar(self, label: str, a: str, b: str, vistos: set) -> List[str]:
        if label == "prereq":
            return [f"{self._nome(a)} → {self._nome(b)}: pré-requisito na ficha de "
                    f"{self._nome(b)} (curado, [1,1])"]
        if label == "prereq_sug":
            c = self._sugestoes.get((a, b), 0.0)
            L = nivel(c) or 0.0
            return [f"{self._nome(a)} → {self._nome(b)}: sugerido por link prediction "
                    f"(crença {c:.0%}, NÃO curado, [{L},1])"]
        if (label, a, b) in vistos or len(vistos) > 40:
            return []
        vistos.add((label, a, b))
        prova = self._prova.get((label, a, b))
        if not prova:
            return []
        regra, clauses = prova[0], prova[1]
        labels = next((ls for pref, ls in self._CLAUSULAS if regra.startswith(pref)), ())
        passos: List[str] = []
        for cl, lab in zip(clauses, labels):
            par = cl[0] if cl else None
            if isinstance(par, (tuple, list)) and len(par) == 2:
                passos += self._explicar(lab, par[0], par[1], vistos)
        return passos

    def inconsistencias_de(self, nome: str) -> List[dict]:
        n = self.kg._normalize_text(self.kg.graph.nodes.get(
            self.kg._find_node(nome, "disciplina") or "", {}).get("nome", nome))
        return [i for i in self.inconsistencias
                if any(self.kg._normalize_text(d) == n for d in i["disciplinas"])]

    # ── (3) projeção temporal ──
    def projetar(self, concluidas: List[str], alvo: Optional[str] = None,
                 horizonte: int = 14) -> Optional[dict]:
        kg = self.kg
        alvo_id = kg._find_node(alvo, "disciplina") if alvo else None
        if alvo and not alvo_id:
            return None
        conc_ids: Set[str] = set()
        nao_resolvidas = []
        for c in concluidas or []:
            nid = kg._find_node(c, "disciplina")
            if nid:
                conc_ids.add(nid)
            else:
                nao_resolvidas.append(c)

        pre: Dict[str, Set[str]] = defaultdict(set)
        for u, v, d in kg.graph.edges(data=True):
            if d.get("relacao") == "PREREQUISITO_DE":
                pre[v].add(u)

        def ancestrais(n: str) -> Set[str]:
            out, pilha = set(), [n]
            while pilha:
                for p in pre.get(pilha.pop(), ()):
                    if p not in out:
                        out.add(p)
                        pilha.append(p)
            return out

        # quem concluiu X concluiu os pré-requisitos de X
        implicitas = set()
        for c in list(conc_ids):
            implicitas |= ancestrais(c) - conc_ids
        conc_ids |= implicitas
        escopo = ({alvo_id} | ancestrais(alvo_id)) if alvo_id else set(pre) | {p for s in pre.values() for p in s}
        escopo |= conc_ids & escopo

        termos = _termos(kg)
        ano, sem = _semestre_atual()
        ids = {n: f"d{i}" for i, n in enumerate(sorted(escopo))}
        volta = {v: k for k, v in ids.items()}

        with PYREASON_LOCK:
            # Não persistente: `oferta` vale só no seu semestre (com persistência
            # o fato de t0 vazaria para todos os semestres e a paridade sumiria);
            # `aprovado` é carregado adiante pela regra `manter_aprovado`.
            pr = _pr_novo(persistent=False)
            g = nx.DiGraph()
            g.add_nodes_from(ids.values())
            pr.load_graph(g)
            pr.add_rule(pr.Rule("aprovado(x) <-1 aprovado(x)", "manter_aprovado"))
            for n in escopo & conc_ids:
                pr.add_fact(pr.Fact(f"aprovado({ids[n]})", f"concluida_{ids[n]}", 0, 0))
            for n in escopo - conc_ids:
                par = _paridade(termos.get(n, {}))
                for t in range(horizonte):
                    _, s_prox = _avanca(ano, sem, t + 1)
                    if par is None or par == s_prox:
                        pr.add_fact(pr.Fact(f"oferta({ids[n]})", f"oferta_{ids[n]}_{t}", t, t))
                corpo = [f"aprovado({ids[p]})" for p in sorted(pre.get(n, ())) if p in ids]
                corpo.append(f"oferta({ids[n]})")
                pr.add_rule(pr.Rule(f"aprovado({ids[n]}) <-1 " + ", ".join(corpo), f"cursar_{ids[n]}"))
            interp = pr.reason(timesteps=horizonte)
            quando: Dict[str, int] = {}
            for t, df in enumerate(pr.filter_and_sort_nodes(interp, ["aprovado"])):
                for row in df.to_dict("records"):
                    if _bound(row["aprovado"])[0] >= 1 and row["component"] not in quando:
                        quando[row["component"]] = t

        plano: Dict[int, List[str]] = defaultdict(list)
        for c, t in quando.items():
            n = volta[c]
            if n not in conc_ids and t > 0:
                plano[t].append(n)
        semestres = []
        for t in sorted(plano):
            a, s = _avanca(ano, sem, t)
            discs = sorted(kg.graph.nodes[n].get("nome", n) for n in plano[t])
            cred = [_creditos(kg, n) for n in plano[t]]
            total = sum(c for c in cred if c) if any(cred) else None
            semestres.append({"semestre": f"{a}/{s}", "disciplinas": discs, "creditos": total,
                              "acima_do_limite": bool(total and total > LIMITE_CREDITOS)})
        alvo_t = quando.get(ids.get(alvo_id)) if alvo_id else None
        inalcancaveis = sorted(kg.graph.nodes[n].get("nome", n)
                               for n in escopo - conc_ids if ids[n] not in quando)
        return {
            "semestre_atual": f"{ano}/{sem}",
            "alvo": kg.graph.nodes[alvo_id].get("nome") if alvo_id else None,
            "alvo_concluido_em": (lambda a_s: f"{a_s[0]}/{a_s[1]}")(_avanca(ano, sem, alvo_t)) if alvo_t else None,
            "ja_concluido": bool(alvo_id and alvo_id in conc_ids),
            "semestres": semestres,
            "implicitas": sorted(kg.graph.nodes[n].get("nome", n) for n in implicitas),
            "nao_resolvidas": nao_resolvidas,
            "inalcancaveis": inalcancaveis,
            "premissas": ("aprovação em toda UC cursada; oferta pela paridade do termo nas "
                          "matrizes (UC sem paridade única: todo semestre); sem limite de "
                          f"créditos (semestres acima de {LIMITE_CREDITOS} créditos estão marcados)"),
        }

    def resumo(self) -> dict:
        return {
            "pronto": self.pronto, "erro": self.erro, "duracao_s": self.duracao,
            "dependencias": len(self.dep),
            "dependencias_incertas": sum(1 for b in self.dep.values() if b < 1.0),
            "regras_ativas": sum(1 for r in self.regras if r.get("ativa")),
            "regras_total": len(self.regras),
            "inferidas": len(self.inferidas),
            "inconsistencias": len(self.inconsistencias),
        }


def _parse_bound(texto) -> Tuple[float, float]:
    if isinstance(texto, (list, tuple)):
        return texto
    try:
        a, b = str(texto).strip("[] ").split(",")
        return float(a), float(b)
    except Exception:
        return (0.0, 1.0)


# ───────────────────────────── singleton do app ──────────────────────────────
# O /reindex (a cada 15 min, pela ingestão de e-mail) recria o KG do zero mesmo
# sem mudança. O raciocinador é indexado pelo CONTEÚDO do KG: se nada mudou,
# a instância pronta é reaproveitada (só troca a referência ao objeto novo).

_por_impressao: Dict[str, RaciocinadorNSAI] = {}
_construindo: Set[str] = set()
_lock_inst = threading.Lock()


def impressao(kg) -> str:
    fp = getattr(kg, "_nsai_impressao", None)
    if fp:
        return fp
    import hashlib

    h = hashlib.sha1()
    for t in sorted((str(u), str(v), str(d.get("relacao", "")), str(d.get("termo", "")))
                    for u, v, d in kg.graph.edges(data=True)):
        h.update("\x1f".join(t).encode("utf-8"))
        h.update(b"\x1e")
    try:
        h.update(OFERTA_JSON.read_bytes())
    except OSError:
        pass
    fp = h.hexdigest()
    try:
        kg._nsai_impressao = fp
    except Exception:
        pass
    return fp


def construir(kg) -> RaciocinadorNSAI:
    """Constrói (bloqueante) e registra o raciocinador deste KG."""
    fp = impressao(kg)
    r = RaciocinadorNSAI(kg).construir()
    if r.pronto:
        _por_impressao[fp] = r
    return r


def obter(kg, iniciar: bool = True) -> Optional[RaciocinadorNSAI]:
    """
    Raciocinador pronto para este KG, ou None enquanto não há um (as respostas
    degradam sem a camada). Com `iniciar`, dispara a construção em background.
    """
    if kg is None:
        return None
    fp = impressao(kg)
    r = _por_impressao.get(fp)
    if r is not None and r.pronto:
        r.kg = kg
        return r
    if iniciar:
        with _lock_inst:
            if fp in _construindo:
                return None
            _construindo.add(fp)

        def _tarefa():
            try:
                construir(kg)
            finally:
                _construindo.discard(fp)

        threading.Thread(target=_tarefa, name="nsai-reasoner", daemon=True).start()
    return None
