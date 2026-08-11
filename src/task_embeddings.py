"""
Prefixos de tarefa para modelos de embedding assimétricos.

Modelos como o embeddinggemma foram treinados para busca assimétrica: a query
deve ser embedada com um prefixo de tarefa e o documento com outro. Sem os
prefixos, a aproximação entre pergunta coloquial e texto formal perde
qualidade. Este wrapper aplica os prefixos corretos por modelo e é transparente
para modelos que não os usam.
"""

from typing import List, Tuple


def prefixes_for_model(model_name: str) -> Tuple[str, str]:
    m = (model_name or "").lower()
    if "embeddinggemma" in m:
        return ("title: none | text: ", "task: search result | query: ")
    if "e5" in m:
        return ("passage: ", "query: ")
    return ("", "")


def embedding_signature(model_name: str) -> str:
    doc_prefix, query_prefix = prefixes_for_model(model_name)
    marcador = "task-prefix-v1" if (doc_prefix or query_prefix) else "plain"
    return f"{model_name}|{marcador}"


class TaskPrefixEmbeddings:
    def __init__(self, inner, model_name: str):
        self._inner = inner
        self._doc_prefix, self._query_prefix = prefixes_for_model(model_name)

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        if not self._doc_prefix:
            return self._inner.embed_documents(texts)
        return self._inner.embed_documents(
            [f"{self._doc_prefix}{t}" for t in texts]
        )

    def embed_query(self, text: str) -> List[float]:
        if not self._query_prefix:
            return self._inner.embed_query(text)
        return self._inner.embed_query(f"{self._query_prefix}{text}")

    def __getattr__(self, name):
        return getattr(self._inner, name)
