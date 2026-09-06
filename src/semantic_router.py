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

_S = {"emb": None, "labels": [], "mat": None}


def configurar(embeddings_model, limiar: float = 0.66) -> None:
    """Pré-computa a matriz normalizada de exemplos (uma vez)."""
    if embeddings_model is None or _S["mat"] is not None:
        return
    try:
        import numpy as np
        pares = [(lab, ex) for lab, exs in FLOW_EXAMPLES.items() for ex in exs]
        vecs = embeddings_model.embed_documents([ex for _, ex in pares])
        a = np.array(vecs, dtype="float32")
        a /= (np.linalg.norm(a, axis=1, keepdims=True) + 1e-9)
        _S["emb"] = embeddings_model
        _S["labels"] = [lab for lab, _ in pares]
        _S["mat"] = a
        _S["limiar"] = limiar
    except Exception:
        _S["emb"] = None


def classificar(pergunta: str) -> Optional[Tuple[str, float]]:
    """(rótulo, score) do intent de fluxo mais próximo, se acima do limiar;
    senão None (o chamador cai no detector lexical). Não lexical: nearest-neighbor
    sobre exemplos."""
    if _S["mat"] is None or not pergunta:
        return None
    try:
        import numpy as np
        q = np.array(_S["emb"].embed_query(pergunta), dtype="float32")
        nq = np.linalg.norm(q)
        if nq == 0:
            return None
        q = q / nq
        sims = _S["mat"] @ q
        j = int(sims.argmax())
        score = float(sims[j])
        if score < _S.get("limiar", 0.62):
            return None
        return _S["labels"][j], score
    except Exception:
        return None


def rotulo(pergunta: str) -> Optional[str]:
    """Só o rótulo (ou None) — açúcar para o roteamento."""
    r = classificar(pergunta)
    return r[0] if r else None
