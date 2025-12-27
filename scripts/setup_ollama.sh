#!/bin/bash
# Script para configurar modelos do Ollama no container Docker

echo "=========================================="
echo "Configurando modelos do Ollama"
echo "=========================================="

CONTAINER_NAME="fesp-ai-ollama"

# Verificar se o container está rodando
if ! docker ps | grep -q $CONTAINER_NAME; then
    echo "Erro: Container $CONTAINER_NAME não está rodando!"
    echo "Execute: docker-compose up -d ollama"
    exit 1
fi

echo "Aguardando Ollama estar pronto..."
sleep 5

# Verificar se Ollama está respondendo
for i in {1..10}; do
    if docker exec $CONTAINER_NAME curl -f http://localhost:11434/api/tags > /dev/null 2>&1; then
        echo "Ollama está pronto!"
        break
    fi
    echo "Aguardando... ($i/10)"
    sleep 3
done

# Baixar modelo LLM
echo ""
echo "Baixando modelo LLM: qwen2.5:7b"
echo "Isso pode levar vários minutos..."
docker exec $CONTAINER_NAME ollama pull qwen2.5:7b

if [ $? -eq 0 ]; then
    echo "✓ Modelo qwen2.5:7b instalado com sucesso!"
else
    echo "✗ Erro ao baixar qwen2.5:7b"
    exit 1
fi

# Baixar modelo de embeddings
echo ""
echo "Baixando modelo de embeddings: mxbai-embed-large"
echo "Isso pode levar vários minutos..."
docker exec $CONTAINER_NAME ollama pull mxbai-embed-large

if [ $? -eq 0 ]; then
    echo "✓ Modelo mxbai-embed-large instalado com sucesso!"
else
    echo "✗ Erro ao baixar mxbai-embed-large"
    exit 1
fi

echo ""
echo "=========================================="
echo "✓ Todos os modelos foram instalados!"
echo "=========================================="
echo ""
echo "Você pode verificar os modelos instalados com:"
echo "  docker exec $CONTAINER_NAME ollama list"
echo ""

