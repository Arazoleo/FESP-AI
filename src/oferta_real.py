"""
Consulta determinística da OFERTA REAL do semestre (sala, dia, horário e
professor de cada turma), a partir do JSON produzido por gerar_oferta_agenda.py
(extraído da agenda de salas do campus). Substitui a heurística de paridade do
oferta.py quando a disciplina está na oferta corrente.

Fonte carimbada na resposta (agenda de salas do campus + data de coleta).
"""

import json
import re
import unicodedata
from pathlib import Path
from typing import Optional, Tuple

_JSON = Path(__file__).resolve().parent.parent / "jsons_regimentos" / "oferta_semestre.json"

DIAS_EXT = {"Seg": "segunda", "Ter": "terça", "Qua": "quarta", "Qui": "quinta",
            "Sex": "sexta", "Sáb": "sábado", "Dom": "domingo"}
_ORDEM = {d: i for i, d in enumerate(["Seg", "Ter", "Qua", "Qui", "Sex", "Sáb", "Dom"])}

_STOP = {"introducao", "a", "as", "o", "os", "de", "da", "do", "das", "dos",
         "e", "em", "para", "com", "the"}
# Fallback lexical (só quando não há modelo de embeddings — ex.: testes locais
# com stub). Em produção a intenção é decidida SEMANTICAMENTE (ver abaixo).
_GATILHOS = ("sala", "salas", "onde", "local", "dia", "dias", "horario",
             "que horas", "quando", "hora", "professor", "prof", "quem",
             "ministra", "leciona", "oferta", "ofertad", "grade", "aula",
             "aulas", "acontece")

# Exemplos semânticos da INTENÇÃO de oferta (sala/dia/horário/quem-dá-no-semestre).
# A pergunta é comparada por embedding ao centróide destes exemplos — sem listas
# de palavras. Alinha com o EmbeddingAgentRouter do projeto.
OFERTA_EXEMPLOS = [
    "qual a sala de redes neurais",
    "onde é a aula de cálculo numérico",
    "em que sala tem álgebra linear",
    "que dias tem aula de geometria analítica",
    "qual o horário de física",
    "que horas é a aula de compiladores",
    "quando é a aula de inferência",
    "quem está dando banco de dados neste semestre",
    "qual professor dá algoritmos este semestre",
    "que disciplinas o professor Quiles leciona agora",
    "quais matérias o professor está dando neste semestre",
    "o que tem aula na sala 302",
    "quais disciplinas acontecem na sala 407",
    "a grade de horários do semestre",
]
# Exemplos "contraste": conteúdo/ementa/pré-requisito — o classificador escolhe o
# centróide MAIS PRÓXIMO (nearest-centroid, como o EmbeddingAgentRouter), sem
# threshold fixo e sem lista de palavras.
CONTEUDO_EXEMPLOS = [
    "qual a ementa de redes neurais",
    "o que é geometria analítica",
    "do que trata inteligência artificial",
    "descreva a disciplina de algoritmos",
    "o que se estuda em compiladores",
    "quais os pré-requisitos de cálculo 2",
    "o que preciso cursar antes de banco de dados",
    "quantos créditos tem álgebra linear",
]

_cache = {"mtime": None, "dados": None}
_sem = {"emb": None, "c_of": None, "c_ct": None}


def configurar_semantica(embeddings_model, threshold: float = None):
    """Pré-computa os centróides de oferta e de conteúdo (uma vez)."""
    if embeddings_model is None or _sem["c_of"] is not None:
        return
    try:
        import numpy as np
        vo = embeddings_model.embed_documents(OFERTA_EXEMPLOS)
        vc = embeddings_model.embed_documents(CONTEUDO_EXEMPLOS)
        _sem["emb"] = embeddings_model
        _sem["c_of"] = np.mean(vo, axis=0).astype("float32")
        _sem["c_ct"] = np.mean(vc, axis=0).astype("float32")
    except Exception:
        _sem["emb"] = None


def _intencao_oferta(pergunta: str):
    """True se a pergunta está mais perto do centróide de OFERTA que do de
    conteúdo (nearest-centroid). None se não há modelo de embeddings."""
    if _sem["emb"] is None or _sem["c_of"] is None:
        return None
    try:
        import numpy as np
        q = np.array(_sem["emb"].embed_query(pergunta), dtype="float32")
        def _cos(c):
            n = np.linalg.norm(q) * np.linalg.norm(c)
            return float(np.dot(q, c) / n) if n else 0.0
        return _cos(_sem["c_of"]) > _cos(_sem["c_ct"])
    except Exception:
        return None


def _tem_intencao(pergunta: str) -> bool:
    """Intenção de oferta: semântica se houver modelo, senão fallback lexical."""
    sem = _intencao_oferta(pergunta)
    if sem is not None:
        return sem
    return any(g in _norm(pergunta) for g in _GATILHOS)


def _carregar() -> Optional[dict]:
    try:
        mt = _JSON.stat().st_mtime
    except OSError:
        return None
    if _cache["mtime"] != mt:
        try:
            _cache["dados"] = json.loads(_JSON.read_text(encoding="utf-8"))
            _cache["mtime"] = mt
        except Exception:
            return None
    return _cache["dados"]


_ROMANOS = [(" viii", " 8"), (" vii", " 7"), (" vi", " 6"), (" iv", " 4"),
            (" ix", " 9"), (" iii", " 3"), (" ii", " 2"), (" v", " 5"),
            (" i", " 1"), (" x", " 10")]


def _norm(s: str) -> str:
    n = unicodedata.normalize("NFD", (s or "").lower())
    n = "".join(c for c in n if unicodedata.category(c) != "Mn")
    n = " " + re.sub(r"[^a-z0-9]+", " ", n).strip() + " "
    for rom, ar in _ROMANOS:
        n = n.replace(rom + " ", ar + " ")
    return re.sub(r"\s+", " ", n).strip()


def _match_disciplina(pergunta: str):
    """Acha a disciplina da oferta mencionada na pergunta (nome, turmas) ou None.

    Casa por (a) nome completo na pergunta, (b) 2+ palavras significativas da
    disciplina presentes, ou (c) uma única palavra distintiva (>=6 letras).
    Vence quem tiver mais/maiores palavras em comum (ex.: "análise real" ganha
    de "...análise de regressão" quando a pergunta traz "real").
    """
    dados = _carregar()
    if not dados:
        return None
    qn = " " + _norm(pergunta) + " "
    qtoks = {t for t in qn.split() if len(t) > 3 and t not in _STOP}
    melhor, melhor_score = None, 0
    for nome, turmas in dados["disciplinas"].items():
        dn = _norm(nome)
        if f" {dn} " in qn:
            score = 100 + len(dn)
        else:
            dtoks = [t for t in dn.split() if len(t) > 3 and t not in _STOP]
            comuns = [t for t in dtoks if t in qtoks]
            # distintividade: >=2 palavras em comum OU uma palavra longa (>=6)
            if not comuns or not (len(comuns) >= 2 or max(map(len, comuns)) >= 6):
                continue
            score = sum(len(t) for t in comuns)
        if score > melhor_score:
            melhor, melhor_score = (nome, turmas), score
    return melhor


def _agenda_por_nome(nome_canonico: str):
    """Acha a entrada da oferta cujo nome bate com o nome canônico do KG."""
    dados = _carregar()
    if not dados:
        return None
    alvo = _norm(nome_canonico)
    melhor, melhor_len = None, 0
    for nome, turmas in dados["disciplinas"].items():
        dn = _norm(nome)
        if dn == alvo or alvo in dn or dn in alvo:
            if len(dn) > melhor_len:
                melhor, melhor_len = (nome, turmas), len(dn)
    return melhor


def _resolver_via_kg(kg, pergunta: str):
    """Usa o KG (nome/sigla/código) p/ resolver referência tipo 'PAA' → oferta."""
    if kg is None:
        return None
    # tokens curtos (2-6 letras), siglas em CAIXA ALTA primeiro
    cands = re.findall(r"[A-Za-zÀ-ÿ]{2,6}", pergunta)
    cands = sorted(set(cands), key=lambda t: (0 if t.isupper() else 1, -len(t)))
    for c in cands:
        try:
            nid = kg._find_node(c, tipo="disciplina")
        except Exception:
            nid = None
        if not nid:
            continue
        nome = (kg.graph.nodes.get(nid, {}) or {}).get("nome")
        if nome:
            achado = _agenda_por_nome(nome)
            if achado:
                return achado
    return None


def detectar(pergunta: str, kg=None) -> Optional[str]:
    """Disciplina se a pergunta é (semanticamente) de oferta E a entidade casa."""
    if not _tem_intencao(pergunta):
        return None
    m = _match_disciplina(pergunta) or _resolver_via_kg(kg, pergunta)
    return m[0] if m else None


def _fmt_encontros(encontros):
    """Agrupa encontros com mesmo horário/sala: 'segunda e quarta 13:30–15:30 (sala 302)'."""
    porslot = {}
    for e in encontros:
        chave = (e["inicio"], e["fim"], e["sala"])
        porslot.setdefault(chave, []).append(e["dia"])
    partes = []
    for (ini, fim, sala), dias in porslot.items():
        dias = sorted(set(dias), key=lambda d: _ORDEM.get(d, 9))
        nomes = [DIAS_EXT.get(d, d) for d in dias]
        quando = " e ".join(nomes) if len(nomes) <= 2 else ", ".join(nomes[:-1]) + " e " + nomes[-1]
        partes.append(f"{quando} das {ini} às {fim}, na {sala}")
    return "; ".join(partes)


def responder(pergunta: str, disciplina: Optional[str] = None, kg=None) -> Optional[str]:
    """Resposta determinística sobre a oferta da disciplina, ou None."""
    dados = _carregar()
    if not dados:
        return None
    if disciplina and disciplina in dados["disciplinas"]:
        nome, turmas = disciplina, dados["disciplinas"][disciplina]
    else:
        m = _match_disciplina(pergunta) or _resolver_via_kg(kg, pergunta)
        if not m:
            return None
        nome, turmas = m
    linhas = [f"Na oferta de {dados['semestre']}, **{nome}** está assim:"]
    for t in turmas:
        prof = t.get("professor") or "professor não informado na agenda"
        quando = _fmt_encontros(t.get("encontros", []))
        linhas.append(f"- **Turma {t['turma']}** — Prof. {prof} — {quando}.")
    linhas.append(
        f"\n_Fonte: agenda de salas do campus SJC (coletado em "
        f"{dados['coletado_em']}). Vale confirmar mudanças pontuais com a "
        f"coordenação._")
    return "\n".join(linhas)


def _fmt_lista(discs):
    discs = sorted(set(discs))
    if len(discs) <= 1:
        return discs[0] if discs else ""
    return "; ".join(discs[:-1]) + " e " + discs[-1]


# extração de ENTIDADE (grounding) — separada da intenção (que é semântica)
def _extrai_sala_ref(pergunta: str) -> Optional[str]:
    m = re.search(r"sala\s+([0-9]{2,4}[a-z]?)|lab[a-z. ]{0,18}([0-9]{2,4})",
                  _norm(pergunta))
    return m.group(0) if m else None


def _extrai_docente(pergunta: str) -> Optional[str]:
    m = re.search(r"prof(?:essor|essora|a)?\.?\s+([A-Za-zÀ-ÿ]+(?:\s+[A-Za-zÀ-ÿ]+){0,3})",
                  pergunta, re.I)
    if not m:
        return None
    _PARA = {"de", "da", "do", "que", "no", "na", "nesse", "neste", "esse", "este",
             "semestre", "ministra", "leciona", "ensina", "esta", "atualmente",
             "agora", "aula", "aulas", "e"}
    toks = []
    for w in m.group(1).split():
        if _norm(w) in _PARA:
            break
        toks.append(w)
    nome = " ".join(toks).strip()
    return nome or None


def detectar_raciocinio(pergunta: str, kg=None) -> bool:
    """Intenção de oferta (semântica) + entidade sala/docente aterrada no grafo."""
    if kg is None or not getattr(kg, "_oferta_semestre", ""):
        return False
    if not _tem_intencao(pergunta):
        return False
    return bool(_extrai_sala_ref(pergunta) or _extrai_docente(pergunta))


def responder_raciocinio(pergunta: str, kg=None) -> Optional[str]:
    """Responde cruzando a oferta com a sala ou o docente aterrado no grafo."""
    if kg is None:
        return None
    sala = _extrai_sala_ref(pergunta)
    if sala:
        discs, label = kg.disciplinas_na_sala(sala)
        if discs:
            return (f"Neste semestre ({kg._oferta_semestre}), na **{label or sala}** "
                    f"têm aula: {_fmt_lista(discs)}."
                    f"\n\n_Fonte: agenda de salas do campus SJC._")
    prof = _extrai_docente(pergunta)
    if prof:
        discs = kg.disciplinas_do_docente_no_semestre(prof)
        if discs:
            return (f"No semestre {kg._oferta_semestre}, Prof(a). {prof} ministra: "
                    f"**{_fmt_lista(discs)}**.\n\n_Fonte: agenda de salas do campus "
                    f"SJC. Vale confirmar com a coordenação._")
    return None


def esta_ofertada(disciplina: str) -> Optional[Tuple[str, str]]:
    """Se a disciplina consta na oferta corrente, retorna (nome, semestre)."""
    dados = _carregar()
    if not dados:
        return None
    m = _match_disciplina(disciplina)
    return (m[0], dados["semestre"]) if m else None
