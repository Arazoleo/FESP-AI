"""
Resposta sobre um GRUPO de docentes (anáfora 'eles/elas' sobre a lista de
docentes já citada). Sem regex de nome nem lista de palavras:

- a lista de docentes é o conjunto de ENTIDADES já aterradas no context tracker;
- "a pergunta nomeia um docente específico?" → grounding no grafo
  (graph_rag._find_docente_in_text); se sim, não é o grupo (fluxo normal);
- "é contato ou disciplinas?" → similaridade semântica (nearest-centroid), como
  o EmbeddingAgentRouter — não por palavras-chave.
"""

CONTATO_EX = [
    "como falo com eles", "qual o email deles", "como entro em contato com eles",
    "quero o contato dos professores", "qual o telefone deles",
    "como acho o contato deles", "tem o email desses professores",
]
DISC_EX = [
    "quais disciplinas eles dão", "o que eles lecionam neste semestre",
    "quais matérias eles ensinam", "quais as áreas de pesquisa deles",
    "em que eles trabalham",
]

_C = {"emb": None, "contato": None, "disc": None}


def configurar(embeddings_model):
    if embeddings_model is None or _C["contato"] is not None:
        return
    try:
        import numpy as np
        _C["emb"] = embeddings_model
        _C["contato"] = np.mean(
            embeddings_model.embed_documents(CONTATO_EX), axis=0).astype("float32")
        _C["disc"] = np.mean(
            embeddings_model.embed_documents(DISC_EX), axis=0).astype("float32")
    except Exception:
        _C["emb"] = None


def _intent_grupo(pergunta):
    """'contato' | 'disciplinas' | None (sem modelo) — por similaridade."""
    if _C["emb"] is None or _C["contato"] is None:
        return None
    try:
        import numpy as np
        q = np.array(_C["emb"].embed_query(pergunta), dtype="float32")

        def cos(c):
            n = np.linalg.norm(q) * np.linalg.norm(c)
            return float(np.dot(q, c) / n) if n else 0.0

        return "contato" if cos(_C["contato"]) >= cos(_C["disc"]) else "disciplinas"
    except Exception:
        return None


def responder_grupo(graph_rag, pergunta, docentes_list):
    """Responde por TODOS os docentes da lista, se a pergunta se refere ao grupo."""
    if graph_rag is None:
        return None
    kg = getattr(graph_rag, "kg", None)
    if kg is None:
        return None
    # defesa: nome de docente nunca cruza linha (evita ruído herdado do parsing)
    docentes_list = [n.splitlines()[0].strip() for n in (docentes_list or []) if n and n.strip()]
    # grounding: a lista herdada do context tracker pode conter NOMES DE
    # DISCIPLINA (bullets de cadeias de pré-req parecem nomes próprios) — só
    # entram os que aterram num docente real do grafo.
    def _eh_docente(nome):
        try:
            return bool(kg._find_docente_id(nome))
        except Exception:
            return False
    docentes_list = [n for n in docentes_list if _eh_docente(n)]
    intent = _intent_grupo(pergunta)
    if intent is None:
        return None

    # a pergunta nomeia UM docente específico? (grounding no grafo)
    try:
        nomeado = graph_rag._find_docente_in_text(pergunta)
    except Exception:
        nomeado = ""
    if nomeado:
        # contato de um docente específico: responde pelo KG (determinístico,
        # não depende do roteador). Só intercepta quando TENHO email/sala; senão
        # deixa o agente seguir - não afirmo ausência de quem não conheço.
        if intent != "contato":
            return None
        try:
            info = kg.get_docente_info(nomeado)
        except Exception:
            info = None
        if not info or not (info.get("email") or info.get("sala")):
            return None
        p = []
        if info.get("email"):
            p.append(f"email {info['email']}")
        if info.get("sala"):
            p.append(f"sala {info['sala']}")
        return f"O contato de **{info.get('nome', nomeado)}**: " + ", ".join(p) + "."

    if intent == "contato":
        linhas, falta = [], []
        for nome in docentes_list:
            info = None
            try:
                info = kg.get_docente_info(nome)
            except Exception:
                info = None
            if info and (info.get("email") or info.get("sala")):
                p = []
                if info.get("email"):
                    p.append(f"email {info['email']}")
                if info.get("sala"):
                    p.append(f"sala {info['sala']}")
                linhas.append(f"- **{info.get('nome', nome)}**: " + ", ".join(p) + ".")
            else:
                falta.append(nome)
        if not linhas:
            return None
        txt = "Aqui estão os contatos que tenho na base:\n" + "\n".join(linhas)
        if falta:
            txt += ("\n\nNão tenho o contato de " + ", ".join(falta) +
                    " na base — vale conferir no site do instituto ou na secretaria.")
        return txt

    # disciplinas do semestre de cada docente do grupo
    linhas = []
    for nome in docentes_list:
        try:
            ds = kg.disciplinas_do_docente_no_semestre(nome)
        except Exception:
            ds = []
        if ds:
            display = nome
            try:  # nome canônico do grafo (ex.: "Didier Vega" -> "Didier Vega-Oliveros")
                info = kg.get_docente_info(nome)
                if info and info.get("nome"):
                    display = info["nome"]
            except Exception:
                pass
            linhas.append(f"- **{display}**: " + ", ".join(ds))
    if not linhas:
        return None
    return "Neste semestre:\n" + "\n".join(linhas)
