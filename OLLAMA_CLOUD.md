# Testar RAG com modelo cloud do Ollama

O Ollama permite usar **modelos grandes na nuvem** (ex.: 120b) sem GPU local. O app continua falando com o Ollama no seu Mac; o Ollama redireciona esse modelo para a nuvem.

## Modelos cloud disponíveis (nome exato para `MODEL_NAME`)

| Modelo | Nome no `.env` | Contexto | Observação |
|--------|----------------|----------|------------|
| **Qwen 3.5** (grande) | `qwen3.5:397b-cloud` | 256K | Multimodal, benchmarks de ponta |
| **Qwen 3.5** (genérico) | `qwen3.5:cloud` | 256K | Versão cloud padrão |
| **Qwen3-Next** 80B | `qwen3-next:80b-cloud` | 256K | Raciocínio + tools, muito popular |
| **DeepSeek V3.2** | `deepseek-v3.2:cloud` | 160K | Eficiência + raciocínio forte |
| **MiniMax M2.5** | `minimax-m2.5:cloud` | 198K | Produtividade e código |
| **Kimi K2.5** | `kimi-k2.5:cloud` | 256K | Multimodal, agentic |
| **GPT-OSS** 120B | `gpt-oss:120b-cloud` | - | Modelo atual (OpenAI open-weight) |

Lista completa: [ollama.com/search?c=cloud](https://ollama.com/search?c=cloud)

## Passos

1. **Conta Ollama** (uma vez):
   ```bash
   ollama signin
   ```

2. **Baixar o modelo cloud** (uma vez). Exemplos:
   ```bash
   ollama pull gpt-oss:120b-cloud
   # ou alternativas (escolha um):
   ollama pull qwen3.5:cloud
   ollama pull qwen3-next:80b-cloud
   ollama pull deepseek-v3.2:cloud
   ollama pull minimax-m2.5:cloud
   ollama pull kimi-k2.5:cloud
   ```

3. **Configurar o projeto para usar o modelo cloud**:
   ```bash
   cp .env.example .env
   ```
   O `.env` já deixa `MODEL_NAME=gpt-oss:120b-cloud`. Para outro modelo, edite `MODEL_NAME` no `.env`.

4. **Subir e testar**:
   ```bash
   docker compose up -d
   ```
   O backend usa o modelo definido em `MODEL_NAME`. Abra o chat em http://localhost:3000 e teste.

## Voltar ao modelo local

No `.env`, troque para:
```bash
MODEL_NAME=ministral-3:8b
```
e reinicie o backend: `docker compose up -d --build backend`.
