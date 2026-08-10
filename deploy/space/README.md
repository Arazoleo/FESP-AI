---
title: FESP-AI Backend
emoji: 🎓
colorFrom: green
colorTo: gray
sdk: docker
app_port: 7860
pinned: false
---

# FESP-AI Backend

API do FESP-AI, assistente acadêmico neurossimbólico da UNIFESP (ICT/SJC).

- Documentação interativa: `/docs`
- Health check: `/health`
- Código-fonte: https://github.com/Arazoleo/FESP-AI

A geração usa o Ollama Cloud (segredo `OLLAMA_API_KEY` nas configurações do Space) e os embeddings rodam localmente no container com `embeddinggemma`.
