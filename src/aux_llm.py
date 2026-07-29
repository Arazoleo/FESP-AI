"""
LLM auxiliar leve compartilhado (FESPAI_ROUTER_MODEL).

Chamadas auxiliares — classificação de intent/termo (IntentClassifier._llm_classify)
e reescrita de pergunta ambígua (ContextResolver.rewrite_with_llm) — produzem
saídas curtas (JSON ou uma linha) e não precisam do modelo de GERAÇÃO
(grande/lento, possivelmente cloud). Quando FESPAI_ROUTER_MODEL está setado,
essas chamadas usam este modelo pequeno com temperatura 0 e num_predict baixo.

Vazio = retorna None e o chamador usa o LLM principal (fallback).
A geração da resposta e o humanizer do KG continuam no modelo grande.
"""

import os

# Saídas auxiliares são curtas: JSON {"intent","term","completed"} ou uma
# pergunta reescrita de uma linha. 200 tokens cobrem com folga.
_AUX_LLM_NUM_PREDICT = 200

_aux_llm_singleton = {"key": None, "llm": None}


def get_aux_llm():
    """
    Instância própria (lazy, cacheada) do LLM auxiliar leve.

    Retorna None quando FESPAI_ROUTER_MODEL está vazio ou a construção falha —
    o chamador deve usar o LLM principal como fallback.
    """
    model = os.getenv("FESPAI_ROUTER_MODEL", "").strip()
    if not model:
        return None
    base_url = (os.getenv("OLLAMA_BASE_URL") or "").strip() or None
    key = (model, base_url)
    if _aux_llm_singleton["key"] == key:
        return _aux_llm_singleton["llm"]
    try:
        from langchain_ollama import OllamaLLM

        kwargs = dict(
            model=model,
            keep_alive=3600,
            num_predict=_AUX_LLM_NUM_PREDICT,
            temperature=0,
            timeout=30,
        )
        if base_url:
            kwargs["base_url"] = base_url
        try:
            # Desliga o modo "thinking" (qwen3, deepseek-r1): a saída auxiliar
            # é curta — raciocínio verboso só custa latência.
            llm = OllamaLLM(reasoning=False, **kwargs)
        except Exception:
            llm = OllamaLLM(**kwargs)
    except Exception:
        llm = None
    _aux_llm_singleton["key"] = key
    _aux_llm_singleton["llm"] = llm
    return llm
