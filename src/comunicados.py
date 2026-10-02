"""
Comunicados institucionais recebidos por email (markdown_comunicados/).

Responde pedidos ORIENTADOS A TEMPO que a busca semântica genérica não cobre:
"o que tem no email hoje", "chegou algum aviso novo?", "tem estágio novo?".
Lê os .md direto do disco (sempre fresco: o ingestor grava a cada ~15 min e
não depende de reindex) e ordena por DATA, não só por similaridade.

- intenção "pedido de comunicados" → nearest-neighbor contrastivo com piso e
  margem (mesma técnica de oferta_real/semantic_router; abstém fora do domínio);
- janela de tempo ("hoje", "ontem", "essa semana", "dd/mm") → extração de slot;
- tema ("estágio", "biblioteca") → similaridade pergunta×comunicado; sem tema
  forte, lista tudo da janela.

Privacidade: só existem aqui avisos em massa às listas institucionais (o
ingestor descarta email pessoal); a resposta deixa isso explícito.
"""

import re
import unicodedata
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple

try:
    from zoneinfo import ZoneInfo
    _TZ = ZoneInfo("America/Sao_Paulo")
except Exception:  # pragma: no cover
    _TZ = None

DIR = Path(__file__).resolve().parent.parent / "markdown_comunicados"
SYNC_FILE = DIR / ".ultima_sync"

PEDIDO_EX = [
    "o que tem no email hoje",
    "o que chegou no email hoje",
    "tem algum comunicado novo",
    "quais os comunicados de hoje",
    "quais os últimos comunicados",
    "chegou algum aviso da unifesp",
    "o que a universidade mandou por email essa semana",
    "tem algum email novo da coordenação",
    "quais avisos chegaram ontem",
    "novidades no email institucional",
    "você tem acesso aos emails da unifesp",
    "tem alguma oportunidade de estágio nova",
    "saiu algum edital novo",
    "tem vaga nova de estágio",
    "teve algum aviso sobre a biblioteca recentemente",
    "tem algo novo da DAE",
    "algum comunicado sobre eventos",
    "o que a secretaria mandou de aviso",
]
# Contraste: o que NÃO é pedido de comunicado (email de docente, notícias do
# site, conteúdo acadêmico, conversa). Sem esta classe o detector seria de
# mundo fechado e capturaria qualquer pergunta.
OUTRO_EX = [
    "qual o email do professor",
    "qual o email da professora Lilian Berton",
    "como entro em contato com a coordenação",
    "quais as notícias do campus",
    "últimas notícias da universidade",
    "qual a ementa de compiladores",
    "quem leciona banco de dados",
    "quais os pré-requisitos de cálculo",
    "quantas horas de atividades complementares preciso",
    "como faço trancamento de matrícula",
    "oi tudo bem",
    "obrigado",
    "o que é o BCT",
    "onde fica a secretaria",
    "tem estágio obrigatório no curso",
    "o BCC tem estágio",
    "como funciona o estágio no BCT",
    "me manda um email",
    "qual o email da secretaria",
]

# Follow-up sobre comunicados JÁ LISTADOS no turno anterior ("detalhe mais",
# "qual o link", "e o segundo?"). Contraste: pergunta NOVA de outro assunto.
FOLLOW_EX = [
    "detalhe mais",
    "me fala mais sobre isso",
    "explica melhor",
    "quero saber mais",
    "como acesso isso",
    "qual o link",
    "e o segundo?",
    "abre o primeiro",
    "o que diz esse comunicado",
    "resume pra mim",
    "como faço pra me inscrever",
    "até quando vai",
    "mais detalhes do primeiro",
]
NOVO_EX = [
    "como faço para colar grau",
    "qual a ementa de compiladores",
    "quem é o coordenador do BCT",
    "oi tudo bem",
    "obrigado",
    "o que chegou ontem no email",
    "quais as notícias do campus",
    "quem leciona banco de dados",
    "quantas horas de atividades complementares preciso",
    "qual o email do professor",
]

PISO = 0.60
MARGEM = 0.06
# Tema RELATIVO: quanto a pergunta casa com cada comunicado ALÉM do que uma
# pergunta genérica ("o que chegou no email") casa. Subtrai o componente
# "cara de email/aviso" e sobra o assunto. Calibrado (embeddinggemma):
# genéricas ≤0.095, temáticas ≥0.169 ("estágio", "biblioteca", "DAE", "RU").
REF_GENERICA = ["o que chegou no email", "quais os comunicados recentes", "tem algum aviso novo"]
TEMA_DELTA = 0.14

_S = {"emb": None, "pos": None, "neg": None, "ref": None, "fup": None, "novo": None}
_cache = {"chave": None, "itens": []}
_vec = {}


def _fold(s: str) -> str:
    s = unicodedata.normalize("NFKD", (s or "").casefold())
    return "".join(c for c in s if not unicodedata.combining(c))


def _agora() -> datetime:
    return datetime.now(_TZ).replace(tzinfo=None) if _TZ else datetime.now()


def _nr(vecs):
    import numpy as np
    a = np.array(vecs, dtype="float32")
    a /= (np.linalg.norm(a, axis=-1, keepdims=True) + 1e-9)
    return a


def configurar(embeddings_model) -> None:
    if embeddings_model is None or _S["pos"] is not None:
        return
    try:
        # pergunta × pergunta-exemplo é tarefa simétrica: mesmo caminho (query)
        _S["pos"] = _nr([embeddings_model.embed_query(e) for e in PEDIDO_EX])
        _S["neg"] = _nr([embeddings_model.embed_query(e) for e in OUTRO_EX])
        _S["ref"] = _nr([embeddings_model.embed_query(e) for e in REF_GENERICA])
        _S["fup"] = _nr([embeddings_model.embed_query(e) for e in FOLLOW_EX])
        _S["novo"] = _nr([embeddings_model.embed_query(e) for e in NOVO_EX])
        _S["emb"] = embeddings_model
    except Exception:
        _S["emb"] = None


def score_pedido(pergunta: str) -> Optional[Tuple[float, float]]:
    """(sim ao pedido de comunicado, sim ao contraste) ou None sem modelo."""
    if _S["emb"] is None or not pergunta:
        return None
    try:
        q = _nr(_S["emb"].embed_query(pergunta))
        return float((_S["pos"] @ q).max()), float((_S["neg"] @ q).max())
    except Exception:
        return None


def eh_pedido(pergunta: str) -> bool:
    """Pedido de comunicados: perto dos exemplos (piso) E vencendo o contraste
    (margem). Janela de tempo explícita ('hj', 'ontem', 'essa semana') é sinal
    forte por si: com o piso, dispensa a margem ('oq tem no email hj' fica a
    0.09 de 'me manda um email', que é contraste)."""
    sc = score_pedido(pergunta)
    if sc is None:
        return False
    pos, neg = sc
    if pos < PISO:
        return False
    return pos - neg >= MARGEM or janela(pergunta)[0] is not None


# ── leitura dos .md ──────────────────────────────────────────────────────
_RUIDO = re.compile(
    r"^(-{3,}|de:|from:|date:|data:|subject:|assunto:|to:|para:|cc:|\[image|<http|"
    r"https?://|\*?forwarded|enviado|sent:|em .* escreveu)",
    re.IGNORECASE,
)


def _limpa_titulo(t: str) -> str:
    t = re.sub(r"^(?:\s*(?:fwd?|enc|res|re)\s*:\s*)+", "", t, flags=re.IGNORECASE)
    return t.strip() or "Comunicado"


def _parse(path: Path) -> Optional[Dict]:
    try:
        txt = path.read_text(encoding="utf-8")
    except Exception:
        return None
    titulo, remetente, data, lista = "", "", None, ""
    for l in txt.splitlines()[:12]:
        s = l.strip()
        low = s.lower()
        if low.startswith("# comunicado institucional:"):
            titulo = s.split(":", 1)[1].strip()
        elif low.startswith("> remetente:"):
            remetente = s.split(":", 1)[1].strip()
        elif low.startswith("> lista:"):
            lista = s.split(":", 1)[1].strip()
        elif low.startswith("> data:"):
            try:
                data = datetime.strptime(s.split(":", 1)[1].strip(), "%d/%m/%Y %H:%M")
            except ValueError:
                data = None
    if data is None:
        m = re.match(r"(\d{4}-\d{2}-\d{2})", path.name)
        if not m:
            return None
        data = datetime.strptime(m.group(1), "%Y-%m-%d")
    nome_rem = re.sub(r"\s*<[^>]+>", "", remetente).strip().strip('"').strip()
    corpo = txt.split("## Conteúdo", 1)[-1]
    linhas = []
    for l in corpo.splitlines():
        s = l.strip().strip("*").strip()
        if len(s) < 25 or _RUIDO.match(s):
            continue
        linhas.append(s)
        if sum(len(x) for x in linhas) > 220:
            break
    resumo = " ".join(linhas)
    if len(resumo) > 220:
        resumo = resumo[:217].rsplit(" ", 1)[0] + "…"
    return {
        "arquivo": path.name,
        "titulo": _limpa_titulo(titulo or path.stem),
        "remetente": nome_rem or remetente,
        "lista": lista,
        "data": data,
        "resumo": resumo,
        "texto_busca": f"{_limpa_titulo(titulo)}. Enviado por {nome_rem or remetente}. {resumo}",
    }


def carregar() -> List[Dict]:
    """Comunicados do disco, do mais recente ao mais antigo (cache por mtime)."""
    try:
        arqs = sorted(DIR.glob("*.md"))
        chave = (len(arqs), max((a.stat().st_mtime for a in arqs), default=0))
    except Exception:
        return []
    if _cache["chave"] != chave:
        itens = [i for i in (_parse(a) for a in arqs) if i]
        itens.sort(key=lambda i: i["data"], reverse=True)
        _cache.update(chave=chave, itens=itens)
    return _cache["itens"]


def ultima_sync() -> Optional[datetime]:
    try:
        return datetime.fromisoformat(SYNC_FILE.read_text().strip())
    except Exception:
        return None


# ── janela de tempo (extração de slot) ──────────────────────────────────
def janela(pergunta: str, agora: datetime = None) -> Tuple[Optional[datetime], Optional[datetime], str]:
    """(início, fim, rótulo) pedido na pergunta; (None, None, '') se não há."""
    agora = agora or _agora()
    hoje = agora.replace(hour=0, minute=0, second=0, microsecond=0)
    q = _fold(pergunta)
    m = re.search(r"\b(\d{1,2})/(\d{1,2})(?:/(\d{2,4}))?\b", q)
    if m:
        ano = int(m.group(3)) if m.group(3) else hoje.year
        ano = ano + 2000 if ano < 100 else ano
        try:
            d = datetime(ano, int(m.group(2)), int(m.group(1)))
            return d, d + timedelta(days=1), f"de {d:%d/%m}"
        except ValueError:
            pass
    if re.search(r"\b(?:hoje|hj)\b", q):
        return hoje, hoje + timedelta(days=1), f"de hoje ({hoje:%d/%m})"
    if re.search(r"\b(?:ontem|onti)\b", q):
        d = hoje - timedelta(days=1)
        return d, hoje, f"de ontem ({d:%d/%m})"
    m = re.search(r"\bultim[oa]s\s+(\d{1,2})\s+dias\b", q)
    if m:
        n = int(m.group(1))
        return hoje - timedelta(days=n - 1), hoje + timedelta(days=1), f"dos últimos {n} dias"
    if re.search(r"\b(?:semana|smn)\b", q):
        return hoje - timedelta(days=6), hoje + timedelta(days=1), "dos últimos 7 dias"
    if re.search(r"\bmes\b", q):
        return hoje - timedelta(days=29), hoje + timedelta(days=1), "dos últimos 30 dias"
    return None, None, ""


def _sims(pergunta: str, itens: List[Dict]) -> List[float]:
    emb = _S["emb"]
    if emb is None or not itens:
        return [0.0] * len(itens)
    try:
        _garante_vetores(itens)
        q = _nr(emb.embed_query(pergunta))
        return [float(_vec[i["arquivo"]] @ q) for i in itens]
    except Exception:
        return [0.0] * len(itens)


def _garante_vetores(itens: List[Dict]) -> None:
    falta = [i for i in itens if i["arquivo"] not in _vec]
    if falta:
        vs = _S["emb"].embed_documents([i["texto_busca"] for i in falta])
        for i, v in zip(falta, vs):
            _vec[i["arquivo"]] = _nr(v)


def _deltas(pergunta: str, itens: List[Dict]) -> List[float]:
    """Similaridade da pergunta a cada comunicado MENOS a da melhor pergunta
    genérica de referência: >0 alto só quando há ASSUNTO na pergunta."""
    if _S["emb"] is None or _S["ref"] is None or not itens:
        return [0.0] * len(itens)
    try:
        s = _sims(pergunta, itens)
        return [si - float((_S["ref"] @ _vec[i["arquivo"]]).max()) for si, i in zip(s, itens)]
    except Exception:
        return [0.0] * len(itens)


def _fmt(i: Dict) -> str:
    quando = i["data"].strftime("%d/%m %H:%M") if i["data"].hour or i["data"].minute \
        else i["data"].strftime("%d/%m")
    linha = f"- **{i['titulo']}** — {i['remetente'] or 'UNIFESP'}, {quando}"
    if i["resumo"]:
        linha += f"\n  {i['resumo']}"
    return linha


def responder(pergunta: str, agora: datetime = None, max_itens: int = 8) -> Optional[Dict]:
    """{texto, fontes, itens} ou None (sem comunicados no disco)."""
    itens = carregar()
    if not itens:
        return None
    agora = agora or _agora()
    ini, fim, rotulo = janela(pergunta, agora)
    hoje = agora.replace(hour=0, minute=0, second=0, microsecond=0)

    # Tema: só conta se algum comunicado recente casa forte com a pergunta.
    recentes = [i for i in itens if i["data"] >= hoje - timedelta(days=60)]
    deltas = dict(zip((i["arquivo"] for i in recentes), _deltas(pergunta, recentes)))
    melhor = max(deltas.values(), default=0.0)
    tematico = melhor >= TEMA_DELTA

    if ini is not None:
        alvo = [i for i in itens if ini <= i["data"] < fim]
    elif tematico:
        alvo = recentes
    else:
        rotulo = "mais recentes"
        alvo = itens[:max_itens]

    if tematico:
        # fica com o que é DO TEMA (perto do melhor), ordenado por data
        corte = max(0.08, melhor * 0.5)
        do_tema = [i for i in alvo if deltas.get(i["arquivo"], 0.0) >= corte]
        if not do_tema and ini is not None:
            # janela pedida sem nada do tema: diz isso e mostra o mais recente
            # DO TEMA (não o que chegou na janela sobre outro assunto)
            tema_rec = sorted((i for i in recentes if deltas.get(i["arquivo"], 0.0) >= corte),
                              key=lambda i: i["data"], reverse=True)[:3]
            if tema_rec:
                texto = (f"Nenhum comunicado {rotulo} é sobre isso. "
                         "Os mais recentes sobre o assunto foram:\n\n"
                         + "\n".join(_fmt(i) for i in tema_rec))
                return {"texto": texto + _rodape(), "fontes": _fontes(tema_rec), "itens": tema_rec}
        alvo = do_tema

    alvo = sorted(alvo, key=lambda i: i["data"], reverse=True)[:max_itens]

    rodape = _rodape()

    if not alvo:
        if ini is not None:
            ultimos = itens[:3]
            texto = (f"Não chegou nenhum comunicado {rotulo} nas listas que acompanho. "
                     "Os mais recentes foram:\n\n" + "\n".join(_fmt(i) for i in ultimos))
            return {"texto": texto + rodape, "fontes": _fontes(ultimos), "itens": ultimos}
        return None

    if tematico and ini is None:
        cab = "Encontrei estes comunicados sobre isso (do mais recente ao mais antigo):"
    elif tematico:
        cab = f"Comunicados {rotulo} sobre isso:"
    else:
        cab = f"Comunicados {rotulo}:"
    texto = cab + "\n\n" + "\n".join(_fmt(i) for i in alvo)
    return {"texto": texto + rodape, "fontes": _fontes(alvo), "itens": alvo}


def _rodape() -> str:
    sync = ultima_sync()
    r = ("\n\n_Fonte: comunicados enviados às listas institucionais de alunos "
         "(não leio email pessoal)._")
    if sync:
        r += f" _Última verificação: {sync:%d/%m %H:%M}._"
    return r


def _fontes(itens: List[Dict]) -> List[str]:
    return [f"Comunicado: {i['titulo']} ({i['remetente'] or 'UNIFESP'}, {i['data']:%d/%m/%Y})"
            for i in itens]


# ── follow-up sobre comunicados já mostrados ────────────────────────────
_ORDINAIS = {
    "primeiro": 0, "primeira": 0, "1": 0, "1o": 0, "1º": 0,
    "segundo": 1, "segunda": 1, "2": 1, "2o": 1, "2º": 1,
    "terceiro": 2, "terceira": 2, "3": 2, "3o": 2, "3º": 2,
    "quarto": 3, "quarta": 3, "4": 3, "quinto": 4, "quinta": 4, "5": 4,
    "ultimo": -1, "ultima": -1,
}


def por_arquivos(nomes: List[str]) -> List[Dict]:
    idx = {i["arquivo"]: i for i in carregar()}
    return [idx[n] for n in nomes if n in idx]


def escolher(pergunta: str, itens: List[Dict]) -> List[Dict]:
    """Itens que a pergunta aponta: ordinal ('o segundo') ou assunto que casa
    com um deles bem mais que com os outros. [] = não aponta nenhum."""
    if not itens:
        return []
    toks = re.findall(r"[\wº]+", _fold(pergunta))
    for t in toks:
        if t in _ORDINAIS:
            j = _ORDINAIS[t]
            if -len(itens) <= j < len(itens):
                return [itens[j]]
    if len(itens) > 1:
        d = _deltas(pergunta, itens)
        j = max(range(len(itens)), key=lambda k: d[k])
        resto = [x for k, x in enumerate(d) if k != j]
        if d[j] >= TEMA_DELTA and d[j] - max(resto, default=0.0) >= 0.08:
            return [itens[j]]
    return []


def eh_followup(pergunta: str, itens: List[Dict]) -> bool:
    """A pergunta continua o assunto dos comunicados mostrados no turno
    anterior? Ordinal/assunto de um deles, ou follow-up genérico ('detalhe
    mais') mais perto dos exemplos de continuação que de pergunta nova."""
    if not itens:
        return False
    if escolher(pergunta, itens):
        return True
    if _S["emb"] is None or _S["fup"] is None:
        return False
    try:
        q = _nr(_S["emb"].embed_query(pergunta))
        f, n = float((_S["fup"] @ q).max()), float((_S["novo"] @ q).max())
        return f >= 0.55 and f - n >= 0.05
    except Exception:
        return False


_URL_LONGA = re.compile(r"<?https?://\S{90,}>?")


def texto_completo(item: Dict, limite: int = 7000) -> str:
    """Corpo do comunicado sem links de rastreamento enormes."""
    try:
        txt = (DIR / item["arquivo"]).read_text(encoding="utf-8")
    except Exception:
        return item.get("resumo", "")
    corpo = txt.split("## Conteúdo", 1)[-1]
    corpo = _URL_LONGA.sub("", corpo)
    corpo = re.sub(r"\[image:[^\]]*\]", "", corpo)
    corpo = re.sub(r"\n{3,}", "\n\n", corpo).strip()
    return corpo[:limite]


_PROMPT_DETALHE = """Você é o assistente da UNIFESP ICT (campus São José dos Campos). O aluno pediu
mais detalhes sobre comunicado(s) institucional(is) recebido(s) por email.
Responda em PORTUGUÊS BRASILEIRO, de forma direta, usando SOMENTE o texto abaixo.
Destaque o que importa para o aluno (o que é, prazos/datas, como participar/acessar,
links legíveis que aparecem no texto). Não invente nada. Não use emojis.

{comunicados}

Pergunta do aluno: {pergunta}

Resposta:"""


def detalhar(pergunta: str, itens: List[Dict], llm) -> Optional[Dict]:
    """Resposta detalhada sobre os comunicados (LLM sobre o texto completo)."""
    if not itens:
        return None
    blocos = []
    for i in itens[:3]:
        blocos.append(f"### {i['titulo']}\nRemetente: {i['remetente']} | Data: {i['data']:%d/%m/%Y %H:%M}\n\n"
                      + texto_completo(i, 7000 // max(1, min(3, len(itens)))))
    texto = None
    if llm is not None:
        try:
            raw = llm.invoke(_PROMPT_DETALHE.format(comunicados="\n\n---\n\n".join(blocos), pergunta=pergunta))
            texto = (getattr(raw, "content", raw) or "").strip()
        except Exception:
            texto = None
    if not texto:
        texto = "\n\n".join(f"**{i['titulo']}** — {i['remetente']}, {i['data']:%d/%m}\n\n"
                             + texto_completo(i, 1500) for i in itens[:3])
    cab = " / ".join(f"{i['titulo']} ({i['remetente'] or 'UNIFESP'}, {i['data']:%d/%m})" for i in itens[:3])
    return {"texto": f"{texto}\n\n_Comunicado: {cab}._", "fontes": _fontes(itens[:3]), "itens": itens[:3]}


def info_arquivo(source: str) -> Optional[Dict]:
    """Título/data REAIS de um comunicado a partir do caminho do chunk (o slug
    do nome do arquivo perde acento e caixa)."""
    nome = (source or "").rsplit("/", 1)[-1]
    return next((i for i in carregar() if i["arquivo"] == nome), None)
