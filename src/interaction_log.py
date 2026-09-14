"""
Log de interações para post-hoc de uso — Fase 1 do loop de auto-correção
(produção → triagem → fix → PR humano-gated).

Uma linha JSONL por turno do /chat: ts, cid (HASHEADO), pergunta, agente, intent,
latência e flag de miss. Privacidade: o conversation_id nunca é gravado em claro
(sha1 truncado); NÃO grava histórico acadêmico/PDF nem outra PII — só a pergunta
e metadados de roteamento. Append-only e à prova de falha (nunca quebra o /chat).

Complementa o misses_queue.jsonl (que só grava falhas) com o quadro completo do
que os usuários fazem, base para a triagem (eval/triage_misses.py).
"""

import json
import os
import hashlib
from datetime import datetime
from typing import List, Optional

LOG_PATH = os.path.join(
    os.getenv("FESPAI_DATA_DIR", "./chroma_db_unifesp"), "interactions.jsonl"
)


def _hash_cid(conversation_id: str) -> str:
    if not conversation_id:
        return ""
    return hashlib.sha1(conversation_id.encode("utf-8")).hexdigest()[:12]


def log_turn(conversation_id: str, question: str, active_agent: str,
             intent: str, latency_ms: Optional[float], is_miss: bool,
             path: Optional[str] = None) -> None:
    """Registra um turno. Silencioso em erro — telemetria nunca derruba o chat."""
    if os.getenv("FESPAI_INTERACTION_LOG", "1") == "0":
        return
    try:
        target = path or LOG_PATH
        parent = os.path.dirname(target)
        if parent:
            os.makedirs(parent, exist_ok=True)
        entry = {
            "ts": datetime.now().isoformat(timespec="seconds"),
            "cid": _hash_cid(conversation_id),
            "question": (question or "").strip()[:500],
            "agent": active_agent or "",
            "intent": intent or "",
            "latency_ms": int(latency_ms) if latency_ms is not None else None,
            "miss": bool(is_miss),
        }
        with open(target, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception:
        pass


def read_log(limit: Optional[int] = None, path: Optional[str] = None) -> List[dict]:
    target = path or LOG_PATH
    if not os.path.exists(target):
        return []
    out: List[dict] = []
    try:
        with open(target, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        out.append(json.loads(line))
                    except Exception:
                        continue
    except Exception:
        return out
    return out[-limit:] if limit else out
