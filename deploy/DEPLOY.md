# Demo pública gratuita (Tailscale Funnel + Vercel)

Arquitetura: o backend continua rodando no seu Mac (docker compose + Ollama, como hoje), mas exposto pelo **Tailscale Funnel** em vez do ngrok. O Funnel é gratuito, não pede cartão, tem **URL fixa** (`https://SEU-MAC.SEU-TAILNET.ts.net`) e não tem o limite de sessão de 2 horas que derruba o ngrok free. O frontend Next.js roda no **Vercel** (gratuito, sempre no ar) com uma URL apresentável, fazendo proxy server-side para o Funnel (sem CORS).

O ponto único de atenção: o Mac precisa ficar ligado com o backend de pé (mesma condição do ngrok atual). Se o Mac reiniciar, o Docker (restart automático) e o Funnel (configuração persistente) voltam sozinhos.

## 1. Backend: Tailscale Funnel no Mac (uma vez, ~10 min)

1. Instale e faça login:

   ```bash
   brew install --cask tailscale
   open -a Tailscale
   ```

   Entre com Google ou GitHub na janela que abrir.

2. Suba o backend e o túnel:

   ```bash
   ./deploy/funnel.sh
   ```

   Na primeira vez, o comando imprime um link para habilitar o Funnel no painel do Tailscale (um clique). Rode de novo depois de habilitar.

3. O script imprime a URL pública fixa, algo como `https://macbook-air-de-leonardo.tail1234.ts.net`. Teste: abra `SUA_URL/health`.

A configuração do Funnel fica salva: depois de reiniciar o Mac, basta o Tailscale e o Docker subirem (ambos iniciam com o login) que a mesma URL volta ao ar.

## 2. Frontend no Vercel

1. Em [vercel.com/new](https://vercel.com/new), faça login com GitHub e importe o repositório `Arazoleo/FESP-AI`.
2. Configure:
   - Root Directory: `frontend`
   - Framework: Next.js (detectado automaticamente)
   - Environment Variable: `BACKEND_INTERNAL_URL` = URL do Funnel (ex.: `https://macbook-air-de-leonardo.tail1234.ts.net`)
3. Deploy. A URL final fica tipo `fesp-ai.vercel.app` (renomeável em Settings > Domains). É essa que vai para o revisor.

Como o proxy é server-side (route handler do Next), o navegador do revisor só fala com o Vercel: sem CORS e sem expor a URL do seu Mac.

## 3. Monitoramento

O workflow `.github/workflows/keepalive.yml` pinga `/health` a cada 12 h e falha se o backend estiver fora do ar (você recebe email do GitHub Actions). Para ativar:

- No GitHub: Settings > Secrets and variables > Actions > aba **Variables** > New repository variable
- Nome: `DEMO_BACKEND_URL`, valor: a URL do Funnel

## 4. Atualizar a demo

Backend: `docker compose up -d --build backend` no Mac. Frontend: qualquer push no GitHub redeploya o Vercel sozinho.

## Alternativa 100% nuvem: Hugging Face Space (requer verificação de cartão)

Se um dia quiser tirar o Mac da jogada: os arquivos em `deploy/space/` sobem o backend num Docker Space (CPU Basic, 2 vCPU/16 GB, sem cobrança), com embeddings locais no container e geração via API do Ollama Cloud (`OLLAMA_API_KEY` como secret). O HF pede um método de pagamento para liberar Spaces Docker em contas novas, mas o tier CPU Basic em si não é cobrado. Publicação: `./deploy/push_space.sh https://huggingface.co/spaces/USUARIO/NOME` (requer `git-lfs`). No Vercel, basta trocar `BACKEND_INTERNAL_URL` pela URL do Space.
