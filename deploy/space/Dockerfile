FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y --no-install-recommends curl ca-certificates && rm -rf /var/lib/apt/lists/*

RUN curl -fsSL https://ollama.com/install.sh | sh

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

ENV HOME=/app \
    OLLAMA_MODELS=/app/.ollama-models \
    NUMBA_CACHE_DIR=/app/.numba_cache \
    OLLAMA_BASE_URL=http://127.0.0.1:11434 \
    OLLAMA_LLM_BASE_URL=https://ollama.com \
    MODEL_NAME=gemma4:31b \
    EMBEDDING_MODEL=embeddinggemma \
    FESPAI_HUMANIZE_KG=1 \
    FESPAI_CLAIM_CHECK=0 \
    FESPAI_SECOND_CHANCE=0 \
    FESPAI_LLM_ROUTE=1 \
    FESPAI_ROUTER_MODEL= \
    PORT=7860

RUN bash -c 'ollama serve & i=0; until curl -sf http://127.0.0.1:11434 >/dev/null; do i=$((i+1)); [ $i -gt 60 ] && exit 1; sleep 1; done; ollama pull embeddinggemma'

RUN chmod -R 777 /app

EXPOSE 7860

CMD ["bash", "start.sh"]
