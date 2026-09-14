"""
Router semântico de intents de FLUXO por nearest-neighbor.

Substitui os detectores lexicais (is_X_request / phrase-lists) por similaridade
ao exemplo mais próximo de cada intent — mesma técnica robusta usada em
oferta_real (NN, não centróide-médio; o centróide dilui clusters e vaza).

Configurado uma vez com o modelo de embeddings. `classificar()` devolve o rótulo
(alinhado aos fast_label do pipeline) só acima de um limiar de confiança; abaixo,
retorna None e o chamador cai no detector lexical (migração segura, sem perder
comportamento). Cada exemplo é uma frase natural — paráfrases são capturadas pela
semântica, não por lista de palavras.
"""

from typing import Optional, Tuple

# rótulo -> exemplos (frases naturais/informais). Rótulos = fast_label do pipeline.
FLOW_EXAMPLES = {
    "cr_consulta": [
        "qual o meu CR",
        "calcula meu coeficiente de rendimento",
        "qual meu coeficiente",
        "me diz meu cr atual",
    ],
    "progresso": [
        "quanto falta pra eu me formar",
        "quanto já cumpri do curso",
        "o que ainda preciso cursar pra terminar",
        "audita meu progresso no curso",
        "quantas disciplinas faltam pra eu concluir",
    ],
    "requisitos_curso": [
        "o que preciso pra colar grau",
        "quais os requisitos de integralização do curso",
        "quais as exigências pra formatura",
        "o que o curso exige pra eu me formar",
        "quantas horas preciso pra integralizar",
    ],
    "matricula_check": [
        "posso me matricular em compiladores",
        "consigo cursar banco de dados esse semestre",
        "já posso pegar cálculo 2",
        "tenho pré-requisito pra fazer redes",
    ],
    "trilha": [
        "monta minha grade",
        "em que ordem devo cursar as disciplinas",
        "planeja meus próximos semestres",
        "qual a sequência de disciplinas até me formar",
    ],
    "ac_auditoria": [
        "audita minhas atividades complementares",
        "quantas horas de AC já tenho pelo meu histórico",
        "confere minhas horas de atividades complementares",
    ],
    "ac_checklist": [
        "checklist de atividades complementares",
        "lista do que vale como atividade complementar",
        "quais atividades contam como AC",
    ],
    "interdisciplinares_lista": [
        "quais são as UCs eletivas interdisciplinares",
        "lista das disciplinas interdisciplinares",
        "quais eletivas interdisciplinares existem",
    ],
}

# Domínio (seleção de agente): MUITO mais separável de conteúdo que os intents
# de fluxo (negativos <0.30 vs positivos >0.50), então limiar mais baixo é seguro.
# montar_grade fica de fora (overlapa com 'trilha'); is_conversational e
# phrase_override seguem lexicais (heurística sutil/correção de rota).
DOMAIN_EXAMPLES = {
    "noticias": [
        "quais as notícias do campus",
        "novidades da unifesp",
        "o que está acontecendo no ict",
        "tem alguma novidade no campus",
        "últimas notícias da universidade",
        # eventos/congressos são anunciados nas notícias (não no site de ingresso)
        "tem algum congresso acontecendo",
        "quando é o congresso acadêmico da unifesp",
        "inscrições para o congresso acadêmico",
        "quais eventos e congressos vão acontecer no campus",
        "como participo do congresso acadêmico",
    ],
    "web_sjc": [
        "onde fica a secretaria",
        "horário de funcionamento do campus",
        "como faço rematrícula",
        "telefone da secretaria acadêmica",
        "como emito meu histórico escolar",
        "como funciona o restaurante universitário",
    ],
}

_FLOW = {"emb": None, "labels": [], "mat": None, "limiar": 0.66}
_DOM = {"emb": None, "labels": [], "mat": None, "limiar": 0.45}

# Distinção PRAZO (tempo/prorrogação → regimentos) vs REQUISITOS (carga/horas),
# contrastiva por nearest-neighbor (como _intencao_oferta), NÃO lexical.
PRAZO_EX = [
    "quanto tempo a mais posso estender o curso",
    "qual o prazo máximo de integralização",
    "posso prorrogar minha graduação por quantos anos",
    "por quantos semestres posso estender a graduação",
    "quanto tempo tenho para concluir o curso",
    "até quando posso me formar",
]
_PRAZO = {"emb": None, "prazo": None, "req": None}


def _nr(vecs):
    import numpy as np
    a = np.array(vecs, dtype="float32")
    a /= (np.linalg.norm(a, axis=1, keepdims=True) + 1e-9)
    return a


def eh_prazo(pergunta: str, piso: float = 0.33) -> bool:
    """True se a pergunta é de PRAZO/tempo (prorrogação, 'estender', 'quanto
    tempo a mais') e não de carga horária. Contrastivo prazo×requisitos COM
    piso absoluto: exige proximidade real ao cluster de prazo, senão perguntas
    não relacionadas ('oi', 'obrigado') cairiam como prazo por acaso."""
    if _PRAZO["prazo"] is None or not pergunta:
        return False
    try:
        import numpy as np
        q = np.array(_PRAZO["emb"].embed_query(pergunta), dtype="float32")
        n = np.linalg.norm(q)
        if n == 0:
            return False
        q = q / n
        s_prazo = float((_PRAZO["prazo"] @ q).max())
        return s_prazo >= piso and s_prazo > float((_PRAZO["req"] @ q).max())
    except Exception:
        return False


def _config(state: dict, examples: dict, embeddings_model, limiar: float) -> None:
    if embeddings_model is None or state["mat"] is not None:
        return
    try:
        import numpy as np
        pares = [(lab, ex) for lab, exs in examples.items() for ex in exs]
        a = np.array(embeddings_model.embed_documents([ex for _, ex in pares]),
                     dtype="float32")
        a /= (np.linalg.norm(a, axis=1, keepdims=True) + 1e-9)
        state["emb"] = embeddings_model
        state["labels"] = [lab for lab, _ in pares]
        state["mat"] = a
        state["limiar"] = limiar
    except Exception:
        state["emb"] = None


def _classify(state: dict, pergunta: str) -> Optional[Tuple[str, float]]:
    if state["mat"] is None or not pergunta:
        return None
    try:
        import numpy as np
        q = np.array(state["emb"].embed_query(pergunta), dtype="float32")
        nq = np.linalg.norm(q)
        if nq == 0:
            return None
        q = q / nq
        sims = state["mat"] @ q
        j = int(sims.argmax())
        score = float(sims[j])
        if score < state["limiar"]:
            return None
        return state["labels"][j], score
    except Exception:
        return None


def configurar(embeddings_model, limiar: float = 0.66) -> None:
    """Pré-computa os exemplos de FLUXO, DOMÍNIO e PRAZO (uma vez)."""
    _config(_FLOW, FLOW_EXAMPLES, embeddings_model, limiar)
    _config(_DOM, DOMAIN_EXAMPLES, embeddings_model, _DOM["limiar"])
    if embeddings_model is not None and _PRAZO["prazo"] is None:
        try:
            _PRAZO["emb"] = embeddings_model
            _PRAZO["prazo"] = _nr(embeddings_model.embed_documents(PRAZO_EX))
            _PRAZO["req"] = _nr(embeddings_model.embed_documents(
                FLOW_EXAMPLES["requisitos_curso"]))
        except Exception:
            _PRAZO["emb"] = None


def classificar(pergunta: str) -> Optional[Tuple[str, float]]:
    """(rótulo, score) do intent de FLUXO mais próximo acima do limiar; senão
    None (chamador cai no lexical). Nearest-neighbor, não lexical."""
    return _classify(_FLOW, pergunta)


def rotulo(pergunta: str) -> Optional[str]:
    """Só o rótulo de FLUXO (ou None)."""
    r = classificar(pergunta)
    return r[0] if r else None


def classificar_dominio(pergunta: str) -> Optional[Tuple[str, float]]:
    """(agente, score) do domínio mais próximo (noticias/web_sjc) acima do
    limiar; senão None. Rede semântica sobre os detectores de domínio lexicais."""
    return _classify(_DOM, pergunta)


def rotulo_dominio(pergunta: str) -> Optional[str]:
    r = classificar_dominio(pergunta)
    return r[0] if r else None
