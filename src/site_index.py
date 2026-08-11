"""
Índice vetorial persistente do corpus do site (collection própria no Chroma).

Substitui a busca por cosseno em memória do agente Web SJC: as seções do site
ficam numa collection persistida, reconstruída apenas quando o crawl (ts) ou a
assinatura de embedding mudam. A busca combina vetor + keyword via RRF.
"""

import json
import os
import re
import unicodedata
from pathlib import Path
from typing import Dict, List, Optional

COLLECTION = "site_sjc"


def _marker_path(persist_dir: str) -> Path:
    return Path(persist_dir) / "site_index_meta.json"


def _ler_marker(persist_dir: str) -> Dict:
    try:
        with open(_marker_path(persist_dir), encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _gravar_marker(persist_dir: str, meta: Dict):
    try:
        with open(_marker_path(persist_dir), "w", encoding="utf-8") as f:
            json.dump(meta, f, ensure_ascii=False)
    except Exception:
        pass


def _slug(url: str) -> str:
    from urllib.parse import urlparse, unquote

    path = unquote(urlparse(url or "").path).split("#", 1)[0]
    return re.sub(r"[-_/]+", " ", path).strip()


def _texto_indexavel(p: Dict) -> str:
    return f"{p.get('titulo', '')}. {_slug(p.get('url', ''))}. {p.get('texto', '')[:1500]}"


def ensure_site_collection(embeddings, persist_dir: str, cache: Dict, signature: str):
    """
    Garante a collection do site atualizada para o crawl atual. Retorna o
    handle do Chroma ou None (sem corpus ou erro), sempre com degradação segura.
    """
    pages = (cache or {}).get("pages") or []
    if not pages:
        return None
    try:
        from langchain_chroma import Chroma
    except Exception:
        return None

    ts = float(cache.get("ts", 0))
    marker = _ler_marker(persist_dir)
    try:
        db = Chroma(
            collection_name=COLLECTION,
            embedding_function=embeddings,
            persist_directory=persist_dir,
        )
        atual = (
            marker.get("ts") == ts
            and marker.get("signature") == signature
            and db._collection.count() == len(pages)
        )
        if atual:
            return db
        print(
            f"[SiteIndex] (re)construindo collection do site: {len(pages)} seções"
        )
        try:
            db.delete_collection()
        except Exception:
            pass
        from langchain_core.documents import Document

        docs = [
            Document(
                page_content=_texto_indexavel(p),
                metadata={
                    "idx": i,
                    "url": p.get("url", ""),
                    "titulo": p.get("titulo", ""),
                    "secao": p.get("secao", ""),
                },
            )
            for i, p in enumerate(pages)
        ]
        db = Chroma.from_documents(
            docs,
            embeddings,
            collection_name=COLLECTION,
            persist_directory=persist_dir,
            ids=[str(i) for i in range(len(pages))],
        )
        _gravar_marker(persist_dir, {
            "ts": ts, "signature": signature, "count": len(pages),
        })
        return db
    except Exception as e:
        print(f"[SiteIndex] indisponível ({e}); usando o ranking em memória.")
        return None


def buscar_site(db, question: str, k: int = 20) -> List[int]:
    """Índices das seções mais relevantes por busca vetorial (ordem de score)."""
    try:
        resultados = db.similarity_search(question, k=k)
        return [
            int(r.metadata.get("idx"))
            for r in resultados
            if r.metadata.get("idx") is not None
        ]
    except Exception:
        return []


def rrf_indices(listas: List[List[int]], k: int = 60, top_n: int = 20) -> List[int]:
    scores: Dict[int, float] = {}
    for lista in listas:
        for pos, idx in enumerate(lista):
            scores[idx] = scores.get(idx, 0.0) + 1.0 / (k + pos + 1)
    return [
        idx for idx, _ in sorted(scores.items(), key=lambda kv: -kv[1])[:top_n]
    ]
