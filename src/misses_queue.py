"""
Fila de casos "não encontrei" — insumo de curadoria de conteúdo.

Toda resposta final que casa os padrões de falha do retry-on-miss (mesmo
após a segunda chance) vira uma linha JSON em
{FESPAI_DATA_DIR|./chroma_db_unifesp}/misses_queue.jsonl. O endpoint
GET /misses expõe as últimas entradas para inspeção.
"""

import json
import os
from datetime import datetime
from typing import List, Optional

MISSES_PATH = os.path.join(
    os.getenv("FESPAI_DATA_DIR", "./chroma_db_unifesp"), "misses_queue.jsonl"
)

RESPONSE_TRUNCATE_CHARS = 300


def record_miss(
    question: str,
    enhanced_question: str,
    agentes: List[str],
    resposta: str,
    path: Optional[str] = None,
) -> None:
    """Registra um miss como JSON-line. Nunca propaga erro (best-effort)."""
    entry = {
        "ts": datetime.now().isoformat(timespec="seconds"),
        "question": question,
        "enhanced_question": enhanced_question,
        "agentes": agentes,
        "resposta_truncada": (resposta or "")[:RESPONSE_TRUNCATE_CHARS],
    }
    try:
        target = path or MISSES_PATH
        parent = os.path.dirname(target)
        if parent:
            os.makedirs(parent, exist_ok=True)
        with open(target, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception:
        pass


def read_misses(limit: int = 50, path: Optional[str] = None) -> List[dict]:
    """Últimas `limit` entradas da fila, mais recentes primeiro."""
    target = path or MISSES_PATH
    try:
        with open(target, encoding="utf-8") as f:
            lines = f.readlines()
    except (FileNotFoundError, OSError):
        return []
    out = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except (json.JSONDecodeError, ValueError):
            continue
    return list(reversed(out[-limit:]))
