"""
Testes das melhorias de retrieval: prefixos de tarefa por modelo, assinatura
de embedding (rebuild automático), reranker plugável e fusão RRF do índice do
site. Executa sem LLM/backend/modelos.
"""

import importlib.util
import sys
import types as _types
from pathlib import Path

ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT))

if "src" not in sys.modules:
    _pkg = _types.ModuleType("src")
    _pkg.__path__ = [str(ROOT / "src")]
    _pkg.__package__ = "src"
    sys.modules["src"] = _pkg


def _mod(name, path):
    spec = importlib.util.spec_from_file_location(name, ROOT / path)
    m = importlib.util.module_from_spec(spec)
    m.__package__ = "src"
    sys.modules[name] = m
    spec.loader.exec_module(m)
    return m


te = _mod("src.task_embeddings", "src/task_embeddings.py")
rr = _mod("src.reranker", "src/reranker.py")
si = _mod("src.site_index", "src/site_index.py")

GREEN, RED, BOLD, RESET = "\033[92m", "\033[91m", "\033[1m", "\033[0m"
_passed, _failed = 0, 0


def check(desc, cond, detail=""):
    global _passed, _failed
    if cond:
        _passed += 1
        print(f"  {GREEN}PASS{RESET} {desc}")
    else:
        _failed += 1
        print(f"  {RED}FAIL{RESET} {desc}" + (f" - {detail}" if detail else ""))


print(f"\n{BOLD}1. Prefixos de tarefa por modelo{RESET}")


class FakeInner:
    def __init__(self):
        self.docs = None
        self.query = None

    def embed_documents(self, texts):
        self.docs = texts
        return [[0.0] for _ in texts]

    def embed_query(self, text):
        self.query = text
        return [0.0]


inner = FakeInner()
w = te.TaskPrefixEmbeddings(inner, "embeddinggemma")
w.embed_documents(["ementa de cálculo"])
w.embed_query("o que estudo em cálculo?")
check("documento com prefixo do embeddinggemma",
      inner.docs == ["title: none | text: ementa de cálculo"], str(inner.docs))
check("query com prefixo de busca",
      inner.query == "task: search result | query: o que estudo em cálculo?",
      str(inner.query))

inner2 = FakeInner()
w2 = te.TaskPrefixEmbeddings(inner2, "multilingual-e5-large")
w2.embed_documents(["x"])
w2.embed_query("y")
check("e5 usa passage:/query:",
      inner2.docs == ["passage: x"] and inner2.query == "query: y")

inner3 = FakeInner()
w3 = te.TaskPrefixEmbeddings(inner3, "bge-m3")
w3.embed_documents(["x"])
w3.embed_query("y")
check("modelo sem prefixo passa intacto",
      inner3.docs == ["x"] and inner3.query == "y")

print(f"\n{BOLD}2. Assinatura de embedding{RESET}")
check("assinatura muda com prefixos ativos",
      te.embedding_signature("embeddinggemma") != te.embedding_signature("bge-m3"))
check("assinatura registra a versão dos prefixos",
      "task-prefix-v1" in te.embedding_signature("embeddinggemma"))
check("modelo plain marcado como plain",
      "plain" in te.embedding_signature("bge-m3"))

print(f"\n{BOLD}3. Reranker plugável{RESET}")


class Doc:
    def __init__(self, texto):
        self.page_content = texto


class FakeScorer:
    def predict(self, pares):
        return [len(p[1]) for p in pares]


docs = [Doc("a"), Doc("aaa"), Doc("aa")]
out = rr.rerank("q", docs, top_k=2, scorer=FakeScorer())
check("reordena pelo score do cross-encoder",
      [d.page_content for d in out] == ["aaa", "aa"], str([d.page_content for d in out]))
check("um documento só passa direto",
      rr.rerank("q", [docs[0]], top_k=5, scorer=FakeScorer()) == [docs[0]])


class ScorerQuebrado:
    def predict(self, pares):
        raise RuntimeError("boom")


out2 = rr.rerank("q", docs, top_k=2, scorer=ScorerQuebrado())
check("falha do scorer degrada para o ranking original",
      [d.page_content for d in out2] == ["a", "aaa"])

import os
os.environ["FESPAI_RERANKER"] = "0"
check("FESPAI_RERANKER=0 desliga o reranker", rr.get_scorer() is None)
del os.environ["FESPAI_RERANKER"]

print(f"\n{BOLD}4. RRF do índice do site{RESET}")
merged = si.rrf_indices([[1, 2, 3], [3, 4, 1]], top_n=3)
check("índice presente nas duas listas sobe", merged[0] in (1, 3), str(merged))
check("top_n respeitado", len(merged) == 3)
check("lista única passa na ordem", si.rrf_indices([[5, 6]], top_n=5) == [5, 6])
check("texto indexável inclui título e slug",
      "Materiais" in si._texto_indexavel(
          {"titulo": "Materiais", "url": "https://x.br/materiais/ac-bct", "texto": "corpo"}
      ) and "ac bct" in si._texto_indexavel(
          {"titulo": "Materiais", "url": "https://x.br/materiais/ac-bct", "texto": "corpo"}
      ))

total = _passed + _failed
cor = GREEN if _failed == 0 else RED
print(f"\n{BOLD}{cor}{_passed}/{total} testes passaram{RESET}\n")
sys.exit(0 if _failed == 0 else 1)
