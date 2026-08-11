"""
Retriever híbrido: BM25 (termos exatos/siglas) + busca vetorial (semântica), fundidos com RRF.

- BM25: garante que siglas (BCC, PAA, SO) e termos técnicos exatos não sejam ignorados.
- RRF (Reciprocal Rank Fusion): funde os rankings sem precisar calibrar scores.
"""

import re
from typing import List, Optional

from langchain_core.documents import Document
from langchain_core.retrievers import BaseRetriever
from langchain_core.callbacks import CallbackManagerForRetrieverRun
from typing import Any


def _tokenize_pt(text: str) -> List[str]:
    """Tokenização simples para PT-BR: palavras e siglas (2+ chars alfanum)."""
    if not text:
        return []
    text = text.lower().strip()
    tokens = re.findall(r"[a-zà-ú0-9]+", text)
    return [t for t in tokens if len(t) >= 1]


def _rrf_merge(
    ranked_lists: List[List[Document]],
    k: int = 60,
    top_n: Optional[int] = None,
    doc_key: str = "id",
) -> List[Document]:
    """
    Reciprocal Rank Fusion: score(doc) = sum 1/(k + rank_i).
    Ordena por score decrescente e retorna top_n documentos únicos (por doc_key em metadata).
    """
    scores: dict = {}
    doc_by_key: dict = {}

    for rank, doc in enumerate(ranked_lists[0] if ranked_lists else [], start=1):
        key = doc.metadata.get(doc_key) or id(doc.page_content)
        scores[key] = scores.get(key, 0) + 1.0 / (k + rank)
        doc_by_key[key] = doc

    for lst in ranked_lists[1:]:
        for rank, doc in enumerate(lst, start=1):
            key = doc.metadata.get(doc_key) or id(doc.page_content)
            scores[key] = scores.get(key, 0) + 1.0 / (k + rank)
            if key not in doc_by_key:
                doc_by_key[key] = doc

    sorted_keys = sorted(scores.keys(), key=lambda x: -scores[x])
    out = [doc_by_key[key] for key in sorted_keys]
    if top_n is not None:
        out = out[:top_n]
    return out


class HybridRetriever(BaseRetriever):
    """Combina retriever vetorial (Chroma) e BM25, fundindo resultados com RRF."""

    vector_retriever: BaseRetriever
    top_k: int = 10
    rrf_k: int = 60
    bm25_corpus: Optional[List[str]] = None
    bm25_ids: Optional[List[str]] = None
    bm25_model: Optional[Any] = None
    db: Optional[Any] = None

    def _get_relevant_documents(
        self,
        query: str,
        *,
        run_manager: Optional[CallbackManagerForRetrieverRun] = None,
    ) -> List[Document]:
        docs_v = self.vector_retriever.invoke(query, config={"callbacks": run_manager})

        if not self.bm25_model or not self.bm25_ids or not self.db:
            return docs_v[: self.top_k]

        tokenized_query = _tokenize_pt(query)
        if not tokenized_query:
            return docs_v[: self.top_k]

        scores = self.bm25_model.get_scores(tokenized_query)
        if hasattr(scores, "__len__") and len(scores) > 0:
            top_indices = sorted(range(len(scores)), key=lambda i: -scores[i])[: self.top_k * 2]
        else:
            top_indices = []
        bm25_ids = [self.bm25_ids[i] for i in top_indices if i < len(self.bm25_ids)]

        docs_b = []
        try:
            coll = getattr(self.db, "_collection", None) or getattr(self.db, "collection", None)
            if coll:
                res = coll.get(ids=bm25_ids, include=["documents", "metadatas"])
                ids_res = res.get("ids") or []
                docs_res = res.get("documents") or []
                metas_res = res.get("metadatas") or []
                for i, id_ in enumerate(bm25_ids):
                    if id_ in ids_res:
                        idx = ids_res.index(id_)
                        meta = metas_res[idx] if idx < len(metas_res) else {}
                        doc = Document(
                            page_content=docs_res[idx] if idx < len(docs_res) else "",
                            metadata={**meta, "id": id_},
                        )
                        docs_b.append(doc)
        except Exception:
            pass

        for d in docs_v:
            if "id" not in d.metadata and hasattr(d, "metadata"):
                d.metadata["id"] = d.metadata.get("ids", [None])[0] if isinstance(d.metadata.get("ids"), list) else d.metadata.get("ids") or id(d.page_content)

        lists = [docs_v, docs_b]
        merged = _rrf_merge(lists, k=self.rrf_k, top_n=self.top_k * 2, doc_key="id")
        candidatos = merged if merged else docs_v[: self.top_k * 2]
        from .reranker import rerank
        return rerank(query, candidatos, self.top_k)


def build_bm25_from_chroma(db) -> tuple:
    """
    Constrói índice BM25 a partir da coleção Chroma.
    Retorna (bm25_model, bm25_ids, corpus_tokenized) ou (None, None, None) se vazio.
    """
    try:
        from rank_bm25 import BM25Okapi
    except ImportError:
        return None, None, None

    try:
        coll = getattr(db, "_collection", None) or getattr(db, "collection", None)
        if coll is None:
            return None, None, None
        data = coll.get(include=["ids", "documents", "metadatas"])
        ids = data.get("ids") or []
        documents = data.get("documents") or []
        if not ids or not documents:
            return None, None, None
        corpus_tok = [_tokenize_pt(d) for d in documents]
        bm25 = BM25Okapi(corpus_tok)
        return bm25, ids, documents
    except Exception:
        return None, None, None
