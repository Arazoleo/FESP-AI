# Demo pública gratuita (Hugging Face Spaces + Vercel)

Arquitetura: o backend (FastAPI + Ollama local para embeddings + ChromaDB pré-construído) roda num Docker Space gratuito do Hugging Face (2 vCPU, 16 GB RAM, URL fixa). A geração de texto vai direto para o Ollama Cloud via API key, sem GPU. O frontend Next.js roda no Vercel (gratuito, sem hibernação), fazendo proxy server-side para o Space (sem CORS).

## 1. Pré-requisitos (uma vez)

- Conta no [huggingface.co](https://huggingface.co) (gratuita)
- Conta no [vercel.com](https://vercel.com) (login com GitHub)
- API key do Ollama Cloud: [ollama.com/settings/keys](https://ollama.com/settings/keys)
- `git-lfs` local: `brew install git-lfs`

## 2. Backend no Hugging Face Space

1. Crie o Space: [huggingface.co/new-space](https://huggingface.co/new-space)
   - Space SDK: **Docker** (Blank)
   - Hardware: **CPU basic** (2 vCPU, 16 GB, free)
   - Visibilidade: público
2. Em Settings do Space, seção Variables and secrets, adicione o **secret** `OLLAMA_API_KEY` com sua chave do ollama.com.
3. Publique o backend:

   ```bash
   ./deploy/push_space.sh https://huggingface.co/spaces/SEU_USUARIO/NOME-DO-SPACE
   ```

   O push pede login: usuário HF + um token de escrita ([huggingface.co/settings/tokens](https://huggingface.co/settings/tokens)).
4. Aguarde o build (10 a 15 min na primeira vez: instala dependências e baixa o `embeddinggemma`). O ChromaDB vai pré-construído, então o boot é rápido.
5. Teste: `https://SEU_USUARIO-NOME-DO-SPACE.hf.space/health`

Sobre o modelo: o Dockerfile usa `MODEL_NAME=gemma4:31b` (nome do catálogo cloud, sem o sufixo `-cloud` que só existe no daemon local). Se o chat retornar erro de modelo desconhecido, ajuste a variável `MODEL_NAME` nas configurações do Space (valores candidatos: `gemma4:31b-cloud`, ou outro do [catálogo cloud](https://ollama.com/search?c=cloud)).

## 3. Frontend no Vercel

1. Em [vercel.com/new](https://vercel.com/new), importe o repositório `Arazoleo/FESP-AI`.
2. Configure:
   - Root Directory: `frontend`
   - Framework: Next.js (detectado)
   - Environment Variable: `BACKEND_INTERNAL_URL` = `https://SEU_USUARIO-NOME-DO-SPACE.hf.space`
3. Deploy. A URL final fica tipo `fesp-ai.vercel.app` (renomeável em Settings > Domains).

## 4. Manter o backend acordado

O Space free hiberna após cerca de 48 h sem requisições (e acorda sozinho no primeiro acesso, em 1 a 2 min). O workflow `.github/workflows/keepalive.yml` faz um ping em `/health` a cada 12 h e impede a hibernação:

- No GitHub: Settings > Secrets and variables > Actions > aba **Variables** > New repository variable
- Nome: `DEMO_BACKEND_URL`, valor: `https://SEU_USUARIO-NOME-DO-SPACE.hf.space`

## 5. Atualizar a demo

Backend: rode o `push_space.sh` de novo (o Space rebuilda sozinho). Frontend: qualquer push no GitHub redeploya o Vercel automaticamente.
