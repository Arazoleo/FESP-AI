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
    "qual a carga horária de compiladores",
    "quantas horas tem a disciplina de banco de dados",
    "a disciplina de cálculo tem quantas horas no total",
    "carga horária total de álgebra linear",
    "quantas horas de carga tem redes neurais",
    # contato de docente NÃO é oferta (email/telefone/currículo)
    "qual o email do professor",
    "como entro em contato com a professora",
    "qual o telefone do docente",
    "qual o lattes do professor",
    "quem é o coordenador do curso",
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
    """Usa o KG p/ resolver SIGLA tipo 'PAA'/'GA' → disciplina → oferta.

    Só testa tokens em CAIXA ALTA (siglas) — nomes por extenso já são casados por
    _match_disciplina; testar qualquer palavra gerava falso-positivo (ex.: uma
    pergunta sobre um docente resolvia a uma disciplina qualquer)."""
    if kg is None:
        return None
    # siglas em CAIXA ALTA, com número/romano opcional: "AED", "AED 1", "AED II"
    cands = []
    for sig, num in re.findall(r"\b([A-ZÀ-Ý]{2,6})(?:\s+([IVX]{1,3}|\d))?\b", pergunta):
        if num:
            cands.append(f"{sig} {num}")   # "AED 1" (mais específico primeiro)
        cands.append(sig)
    cands = list(dict.fromkeys(cands))
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


def detectar(pergunta: str, kg=None, contexto=None) -> Optional[str]:
    """Disciplina se a pergunta é (semanticamente) de oferta E a entidade casa.

    Se a intenção é de oferta mas NENHUMA entidade aparece (follow-up curto tipo
    'qual dia e sala', 'e o horário'), usa a última disciplina do contexto da
    sessão — resolve a anáfora sem tracker lexical."""
    if not _tem_intencao(pergunta):
        return None
    m = _match_disciplina(pergunta) or _resolver_via_kg(kg, pergunta)
    if m:
        return m[0]
    if contexto and contexto.get("disciplina"):
        return contexto["disciplina"]
    return None


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


def _todas_disciplinas(pergunta: str):
    """Disciplinas da oferta mencionadas, UMA por trecho casado da pergunta.

    Agrupa por SPAN (o pedaço da pergunta que casou): se duas disciplinas casam o
    mesmo trecho (ex.: 'redes neurais' → Introdução vs Aplicações), fica só a
    melhor (bônus p/ quem está no catálogo de graduação). Trechos distintos
    ('X e Y') geram disciplinas distintas → pergunta composta."""
    dados = _carregar()
    if not dados:
        return []
    qn = " " + _norm(pergunta) + " "
    por_span = {}  # span -> (nome, score)
    for nome, turmas in dados["disciplinas"].items():
        dn = _norm(nome)
        span, score = None, 0
        if f" {dn} " in qn:
            span, score = dn, 100 + len(dn)
        else:
            toks = [t for t in dn.split() if len(t) > 3 and t not in _STOP]
            for i in range(len(toks) - 1):
                sh = f"{toks[i]} {toks[i+1]}"
                if f" {sh} " in qn:
                    span, score = sh, len(sh)
                    break
        if not span:
            continue
        if turmas and turmas[0].get("no_catalogo"):
            score += 1  # desempate: prefere a de graduação
        if span not in por_span or score > por_span[span][1]:
            por_span[span] = (nome, score)
    return [n for n, _ in sorted(por_span.values(), key=lambda x: -x[1])]


def _fmt_disciplina(nome, turmas):
    linhas = [f"**{nome}**:"]
    for t in turmas:
        prof = t.get("professor") or "professor não informado na agenda"
        quando = _fmt_encontros(t.get("encontros", []))
        linhas.append(f"- **Turma {t['turma']}** — Prof. {prof} — {quando}.")
    return "\n".join(linhas)


def responder(pergunta: str, disciplina: Optional[str] = None, kg=None) -> Optional[str]:
    """Resposta determinística sobre a oferta de uma OU MAIS disciplinas."""
    dados = _carregar()
    if not dados:
        return None
    if disciplina and disciplina in dados["disciplinas"]:
        alvos = [disciplina]
    else:
        alvos = _todas_disciplinas(pergunta)  # pega composta "X e Y"
        if not alvos:
            m = _resolver_via_kg(kg, pergunta)
            alvos = [m[0]] if m else []
    if not alvos:
        return None
    blocos = [_fmt_disciplina(n, dados["disciplinas"][n]) for n in alvos[:4]]
    sem = dados["semestre"]
    if len(blocos) == 1:
        texto = f"Na oferta de {sem}, {blocos[0]}"
    else:
        texto = f"Na oferta de {sem}:\n\n" + "\n\n".join(blocos)
    return (f"{texto}\n\n_Fonte: agenda de salas do campus SJC (coletado em "
            f"{dados['coletado_em']}). Vale confirmar mudanças pontuais com a "
            f"coordenação._")


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


_PARA_NOME = {"de", "da", "do", "que", "no", "na", "nesse", "neste", "esse", "este",
              "semestre", "ministra", "leciona", "ensina", "esta", "esta", "estao",
              "atualmente", "agora", "aula", "aulas", "e", "dando", "da", "dao"}


def _limpa_nome(bruto: str) -> str:
    toks = []
    for w in (bruto or "").split():
        if _norm(w) in _PARA_NOME:
            break
        toks.append(w)
    return " ".join(toks).strip()


def _extrai_docente(pergunta: str, kg=None) -> Optional[str]:
    """Aterra o nome do docente no KG (índice de docentes) — sem exigir 'prof'.

    Candidatos: o nome após 'prof', e qualquer palavra Capitalizada; o KG decide
    quem é docente. Assim 'quais disciplinas o Didier dá' funciona."""
    m = re.search(r"prof(?:essor|essora|a)?\.?\s+([A-Za-zÀ-ÿ]+(?:\s+[A-Za-zÀ-ÿ]+){0,2})",
                  pergunta, re.I)
    prof_nome = _limpa_nome(m.group(1)) if m else None
    if kg is None:
        return prof_nome
    cands = ([prof_nome] if prof_nome else [])
    cands += re.findall(r"\b([A-ZÀ-Ý][a-zà-ÿ]{2,})\b", pergunta)  # nomes Capitalizados
    vistos = set()
    for c in cands:
        nome = _limpa_nome(c)
        chave = _norm(nome)
        if not nome or chave in vistos:
            continue
        vistos.add(chave)
        try:
            if kg._find_docente_id(nome):
                return nome
        except Exception:
            pass
    return None


def detectar_raciocinio(pergunta: str, kg=None) -> bool:
    """Intenção de oferta (semântica) + entidade sala/docente aterrada no grafo."""
    if kg is None or not getattr(kg, "_oferta_semestre", ""):
        return False
    if not _tem_intencao(pergunta):
        return False
    return bool(_extrai_sala_ref(pergunta) or _extrai_docente(pergunta, kg))


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
    prof = _extrai_docente(pergunta, kg)
    if prof:
        discs = kg.disciplinas_do_docente_no_semestre(prof)
        if discs:
            return (f"No semestre {kg._oferta_semestre}, Prof(a). {prof} ministra: "
                    f"**{_fmt_lista(discs)}**.\n\n_Fonte: agenda de salas do campus "
                    f"SJC. Vale confirmar com a coordenação._")
    return None


_sigmap = {"key": None, "map": None}


def _sigla_map(kg):
    """Mapa {base_da_sigla -> {disciplinas}} das disciplinas ofertadas (cacheado)."""
    dados = _carregar()
    if not dados or kg is None:
        return {}
    if _sigmap["key"] == _cache["mtime"] and _sigmap["map"] is not None:
        return _sigmap["map"]
    m = {}
    for nome in dados["disciplinas"]:
        try:
            nid = kg._find_node(nome, "disciplina")
        except Exception:
            nid = None
        if not nid:
            continue
        sig = _norm((kg.graph.nodes.get(nid, {}) or {}).get("sigla") or "")
        for variante in re.split(r"\bou\b|[,/]", sig):
            palavras = variante.split()
            if palavras:
                m.setdefault(palavras[0], set()).add(nome)
    _sigmap["key"] = _cache["mtime"]
    _sigmap["map"] = m
    return m


def detectar_ambiguo(pergunta: str, kg=None):
    """Sigla base (ex.: 'AED') que mapeia p/ 2+ disciplinas e não resolve sozinha."""
    if kg is None or not _tem_intencao(pergunta):
        return None
    smap = _sigla_map(kg)
    for sig in re.findall(r"\b([A-ZÀ-Ý]{2,6})\b", pergunta):
        b = _norm(sig)
        if b in smap and len(smap[b]) >= 2:
            try:
                resolve = kg._find_node(sig, "disciplina")
            except Exception:
                resolve = None
            if not resolve:  # a sigla sozinha é ambígua
                return sorted(smap[b])
    return None


def responder_ambiguo(pergunta: str, kg=None) -> Optional[str]:
    """Follow-up de desambiguação: pergunta qual disciplina o usuário quer."""
    cands = detectar_ambiguo(pergunta, kg)
    if not cands:
        return None
    lst = " ou ".join(f"**{c}**" for c in cands)
    return (f"Essa sigla pode ser {lst}. De qual você quer a informação da oferta "
            f"(sala, dia, horário ou professor)?")


def esta_ofertada(disciplina: str) -> Optional[Tuple[str, str]]:
    """Se a disciplina consta na oferta corrente, retorna (nome, semestre)."""
    dados = _carregar()
    if not dados:
        return None
    m = _match_disciplina(disciplina)
    return (m[0], dados["semestre"]) if m else None
