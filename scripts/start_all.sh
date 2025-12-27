#!/bin/bash
# Script para iniciar tudo: Ollama nativo + Docker (Frontend e Backend)

set -e

echo "Iniciando FESP-AI completo..."
echo ""

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Passo 1/2: Iniciando Ollama nativo (Metal)"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
./scripts/start_ollama_native.sh

echo ""
echo "Aguardando Ollama estabilizar..."
sleep 3

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Passo 2/2: Iniciando containers Docker"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
docker-compose up -d

echo ""
echo "Aguardando servicos estarem prontos..."
sleep 5

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Verificando status dos servicos..."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

if curl -s http://localhost:11434/api/tags > /dev/null 2>&1; then
    echo "Ollama (Metal): http://localhost:11434"
else
    echo "Ollama nao esta respondendo"
fi

if curl -s http://localhost:8000/health > /dev/null 2>&1; then
    echo "Backend: http://localhost:8000"
else
    echo "Backend ainda inicializando... (pode levar alguns segundos)"
fi

if curl -s http://localhost:3000 > /dev/null 2>&1; then
    echo "Frontend: http://localhost:3000"
else
    echo "Frontend ainda inicializando... (pode levar alguns segundos)"
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "FESP-AI iniciado com sucesso!"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "URLs:"
echo "   - Ollama (Metal): http://localhost:11434"
echo "   - Backend API:    http://localhost:8000"
echo "   - Frontend:       http://localhost:3000"
echo ""
echo "Comandos uteis:"
echo "   - Ver logs:       docker-compose logs -f"
echo "   - Parar tudo:     docker-compose down"
echo "   - Status Ollama:  ollama ps"
echo ""

