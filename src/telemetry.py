"""
Telemetria leve do loop neurossimbólico (contadores em memória).

Mede quantas vezes cada mecanismo de defesa/correção atua — números de
ablação para o paper ("sem grounding: X% de erro; com: Y%") e diagnóstico
em produção via GET /telemetry.
"""

from collections import Counter

_counters: Counter = Counter()


def incr(evento: str, n: int = 1) -> None:
    _counters[evento] += n


def snapshot() -> dict:
    return dict(_counters)


def reset() -> None:
    _counters.clear()
