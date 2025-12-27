# Stage 1: Build
FROM node:18-alpine AS builder

WORKDIR /app

# Copiar arquivos de dependências
COPY package*.json ./
COPY tsconfig.json ./
COPY next.config.js ./
COPY tailwind.config.js ./
COPY postcss.config.js ./

# Instalar dependências (npm install funciona sem package-lock.json)
RUN npm install --legacy-peer-deps

# Copiar código fonte
COPY app/ ./app/

# Criar diretório public (Next.js pode precisar, mesmo que vazio)
RUN mkdir -p ./public

# Build da aplicação
RUN npm run build

# Stage 2: Production
FROM node:18-alpine AS runner

WORKDIR /app

ENV NODE_ENV=production

# Copiar arquivos necessários do builder
COPY --from=builder /app/package*.json ./
COPY --from=builder /app/next.config.js ./
COPY --from=builder /app/.next ./.next
COPY --from=builder /app/app ./app
# Criar diretório public (Next.js pode precisar)
RUN mkdir -p ./public
COPY --from=builder /app/node_modules ./node_modules

# Expor porta
EXPOSE 3000

ENV PORT=3000
ENV HOSTNAME="0.0.0.0"

# Comando para iniciar
CMD ["npm", "start"]
