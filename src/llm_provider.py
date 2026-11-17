"""
Provedor do LLM de geração: Ollama (local/cloud) ou Groq (API compatível com OpenAI).

    LLM_PROVIDER=ollama  (padrão) -> langchain_ollama.OllamaLLM, como antes
    LLM_PROVIDER=groq             -> GroqLLM abaixo; precisa de GROQ_API_KEY

Modelos no Groq:
    GROQ_MODEL      geração (padrão openai/gpt-oss-120b)
    GROQ_AUX_MODEL  chamadas curtas: roteador, reescrita, intent
                    (padrão openai/gpt-oss-20b; a cota do free tier é por modelo,
                    então separar os dois dobra o orçamento)

GroqLLM é um LLM de texto (invoke(str) -> str), o mesmo contrato do OllamaLLM,
então entra em `prompt | llm | parser` sem mudar quem o usa.

Medição: toda chamada soma em USO (chamadas, tokens, 429) e, se
FESPAI_LLM_USAGE_LOG apontar para um arquivo, grava uma linha JSON por chamada.
"""

from __future__ import annotations

import json
import os
import threading
import time
from typing import Any, Dict, List, Optional

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODEL_PADRAO = "openai/gpt-oss-120b"
GROQ_AUX_PADRAO = "openai/gpt-oss-20b"

# gpt-oss raciocina antes de responder e esses tokens contam em
# max_completion_tokens; sem folga, um num_predict pequeno (roteador: 150)
# esgota no raciocínio e a resposta volta vazia.
_FOLGA_RACIOCINIO = 1024

_lock = threading.Lock()
USO: Dict[str, Any] = {"chamadas": 0, "prompt_tokens": 0, "completion_tokens": 0,
                       "rate_limited": 0, "erros": 0, "por_papel": {}}


def provedor() -> str:
    return (os.getenv("LLM_PROVIDER") or "ollama").strip().lower()


def _registrar(papel: str, modelo: str, usage: Dict[str, int], dt: float,
               status: str) -> None:
    with _lock:
        USO["chamadas"] += 1
        USO["prompt_tokens"] += usage.get("prompt_tokens", 0)
        USO["completion_tokens"] += usage.get("completion_tokens", 0)
        if status == "429":
            USO["rate_limited"] += 1
        elif status != "ok":
            USO["erros"] += 1
        p = USO["por_papel"].setdefault(papel, {"chamadas": 0, "tokens": 0})
        p["chamadas"] += 1
        p["tokens"] += usage.get("total_tokens", 0)
    caminho = (os.getenv("FESPAI_LLM_USAGE_LOG") or "").strip()
    if caminho:
        linha = {"ts": time.strftime("%Y-%m-%dT%H:%M:%S"), "papel": papel,
                 "modelo": modelo, "status": status, "s": round(dt, 2), **usage}
        try:
            with _lock, open(caminho, "a", encoding="utf-8") as f:
                f.write(json.dumps(linha) + "\n")
        except OSError:
            pass


def uso_snapshot() -> Dict[str, Any]:
    with _lock:
        return json.loads(json.dumps(USO))


try:
    from langchain_core.language_models.llms import LLM as _BaseLLM
except Exception:  # testes sem langchain
    _BaseLLM = object


class GroqLLM(_BaseLLM):
    """LLM de texto sobre o endpoint OpenAI-compatível do Groq."""

    model: str = GROQ_MODEL_PADRAO
    temperature: float = 0.1
    num_predict: int = 2048
    timeout: float = 60
    reasoning_effort: Optional[str] = "low"
    papel: str = "geracao"
    max_retries: int = 2

    @property
    def _llm_type(self) -> str:
        return "groq"

    @property
    def _identifying_params(self) -> Dict[str, Any]:
        return {"model": self.model, "temperature": self.temperature}

    def _corpo(self, prompt: str, stop: Optional[List[str]]) -> Dict[str, Any]:
        corpo: Dict[str, Any] = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": self.temperature,
            "max_completion_tokens": self.num_predict + (
                _FOLGA_RACIOCINIO if "gpt-oss" in self.model else 0),
        }
        if stop:
            corpo["stop"] = stop[:4]
        if self.reasoning_effort and "gpt-oss" in self.model:
            corpo["reasoning_effort"] = self.reasoning_effort
            corpo["include_reasoning"] = False
        return corpo

    def _call(self, prompt: str, stop: Optional[List[str]] = None,
              run_manager: Any = None, **kwargs: Any) -> str:
        import requests

        chave = (os.getenv("GROQ_API_KEY") or "").strip()
        if not chave:
            raise RuntimeError("LLM_PROVIDER=groq mas GROQ_API_KEY não está definida")
        cab = {"Authorization": f"Bearer {chave}", "Content-Type": "application/json"}
        corpo = self._corpo(prompt, stop)
        reserva = (os.getenv("GROQ_AUX_MODEL") or GROQ_AUX_PADRAO).strip()
        for tentativa in range(self.max_retries + 2):
            t0 = time.perf_counter()
            r = requests.post(GROQ_URL, json=corpo, headers=cab, timeout=self.timeout)
            dt = time.perf_counter() - t0
            if r.status_code == 429:
                _registrar(self.papel, corpo["model"], {}, dt, "429")
                espera = float(r.headers.get("retry-after") or 2 ** tentativa)
                # O free tier limita TOKENS por minuto por modelo (8K no 120b):
                # uma rajada de perguntas estoura e o retry-after passa de 20 s.
                # Em vez de deixar o aluno esperando, a chamada vai na hora para o
                # modelo de reserva (cota própria); só espera se ele também estourar.
                if espera > 3 and corpo["model"] != reserva:
                    corpo = {**corpo, "model": reserva}
                    continue
                if tentativa <= self.max_retries and espera <= 30:
                    time.sleep(espera)
                    continue
                raise RuntimeError(f"Groq: limite de taxa atingido ({corpo['model']}); "
                                   f"retry-after={r.headers.get('retry-after')}")
            if r.status_code == 400 and "include_reasoning" in corpo and "reasoning" in r.text:
                # parâmetro não aceito por este modelo: tenta sem ele
                corpo.pop("include_reasoning", None)
                continue
            if r.status_code >= 400:
                _registrar(self.papel, corpo["model"], {}, dt, str(r.status_code))
                raise RuntimeError(f"Groq {r.status_code}: {r.text[:300]}")
            d = r.json()
            _registrar(self.papel, corpo["model"], d.get("usage") or {}, dt, "ok")
            return (d["choices"][0]["message"].get("content") or "").strip()
        raise RuntimeError("Groq: tentativas esgotadas")


def criar_llm(*, papel: str = "geracao", modelo_ollama: Optional[str] = None,
              temperature: float = 0.1, num_predict: int = 2048,
              timeout: float = 60, **ollama_kwargs: Any):
    """
    LLM de texto do provedor configurado.

    papel="geracao" usa GROQ_MODEL; qualquer outro papel (roteador, aux, juiz)
    usa GROQ_AUX_MODEL. No Ollama, `modelo_ollama` e `ollama_kwargs` vão
    direto para o OllamaLLM, preservando o comportamento anterior.
    """
    if provedor() == "groq":
        if papel == "geracao":
            modelo = (os.getenv("GROQ_MODEL") or GROQ_MODEL_PADRAO).strip()
        else:
            modelo = (os.getenv("GROQ_AUX_MODEL") or GROQ_AUX_PADRAO).strip()
        return GroqLLM(model=modelo, temperature=temperature, num_predict=num_predict,
                       timeout=timeout, papel=papel)

    from langchain_ollama import OllamaLLM

    kwargs = dict(model=modelo_ollama, temperature=temperature,
                  num_predict=num_predict, timeout=timeout, **ollama_kwargs)
    reasoning = kwargs.pop("reasoning", None)
    if reasoning is not None:
        try:
            return OllamaLLM(reasoning=reasoning, **kwargs)
        except Exception:
            pass
    return OllamaLLM(**kwargs)
