"""
Reranking com cross-encoder: reordena os candidatos do retriever híbrido
lendo query e trecho JUNTOS, o que captura relevância que o bi-encoder perde.

Opcional e com degradação segura: sem a dependência instalada (ou com
FESPAI_RERANKER=0), o ranking do RRF segue intacto.
"""

import os
from typing import Any, List, Optional

_MODEL_PADRAO = "cross-encoder/mmarco-mMiniLMv2-L12-H384-v1"
_estado = {"scorer": None, "falhou": False}


def get_scorer() -> Optional[Any]:
    if os.getenv("FESPAI_RERANKER", "1") == "0":
        return None
    if _estado["falhou"]:
        return None
    if _estado["scorer"] is None:
        try:
            from sentence_transformers import CrossEncoder

            modelo = os.getenv("FESPAI_RERANKER_MODEL", _MODEL_PADRAO)
            _estado["scorer"] = CrossEncoder(modelo, max_length=512)
            print(f"[Reranker] cross-encoder carregado: {modelo}")
        except Exception as e:
            print(f"[Reranker] indisponível ({e}); seguindo com o ranking do RRF.")
            _estado["falhou"] = True
            return None
    return _estado["scorer"]


def rerank(query: str, docs: List[Any], top_k: int, scorer: Any = None) -> List[Any]:
    if len(docs) <= 1:
        return docs[:top_k]
    scorer = scorer or get_scorer()
    if scorer is None:
        return docs[:top_k]
    try:
        pares = [
            (query, (getattr(d, "page_content", None) or str(d))[:1200])
            for d in docs
        ]
        scores = scorer.predict(pares)
        ordem = sorted(range(len(docs)), key=lambda i: -float(scores[i]))
        return [docs[i] for i in ordem[:top_k]]
    except Exception:
        return docs[:top_k]
