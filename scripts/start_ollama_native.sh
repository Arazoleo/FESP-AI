#!/bin/bash
# Script para iniciar Ollama nativamente no Mac (com suporte Metal)
# Isso permite usar a GPU do Mac para acelerar os modelos

set -e

echo "Iniciando Ollama nativo com suporte Metal..."

if ! command -v ollama &> /dev/null; then
    echo "Ollama nao encontrado."
    echo "Instalando Ollama via Homebrew..."
    
    if command -v brew &> /dev/null; then
        brew install ollama
    else
        echo "Homebrew nao encontrado."
        echo "Por favor, instale o Ollama manualmente: https://ollama.ai/download"
        echo "Ou instale o Homebrew primeiro: https://brew.sh"
        exit 1
    fi
fi

if curl -s http://localhost:11434/api/tags > /dev/null 2>&1; then
    echo "Ollama ja esta rodando!"
else
    echo "Iniciando servidor Ollama..."
    ollama serve > /tmp/ollama.log 2>&1 &
    OLLAMA_PID=$!
    
    echo "Aguardando Ollama estar pronto..."
    MAX_WAIT=30
    for i in $(seq 1 $MAX_WAIT); do
        if curl -s http://localhost:11434/api/tags > /dev/null 2>&1; then
            echo "Ollama esta pronto!"
            break
        fi
        if [ $i -eq $MAX_WAIT ]; then
            echo "Timeout: Ollama nao iniciou apos ${MAX_WAIT}s"
            echo "Verifique os logs: tail -f /tmp/ollama.log"
            exit 1
        fi
        sleep 1
        echo -n "."
    done
    echo ""
fi

echo "Verificando modelos necessarios..."

MODELS_INSTALLED=$(ollama list 2>/dev/null || echo "")

if ! echo "$MODELS_INSTALLED" | grep -q "qwen2.5:7b"; then
    echo "Baixando modelo qwen2.5:7b (isso pode demorar alguns minutos)..."
    ollama pull qwen2.5:7b
    echo "qwen2.5:7b instalado!"
else
    echo "qwen2.5:7b ja esta instalado"
fi

if ! echo "$MODELS_INSTALLED" | grep -q "mxbai-embed-large"; then
    echo "Baixando modelo mxbai-embed-large (isso pode demorar alguns minutos)..."
    ollama pull mxbai-embed-large
    echo "mxbai-embed-large instalado!"
else
    echo "mxbai-embed-large ja esta instalado"
fi

echo ""
echo "Verificando configuracao..."
if ollama ps 2>/dev/null | grep -q "gpu\|metal" || [ -n "$(ollama ps 2>/dev/null)" ]; then
    echo "Ollama esta configurado e pronto!"
else
    echo "Ollama esta rodando (Metal sera usado automaticamente se disponivel)"
fi

echo ""
echo "Ollama nativo configurado e pronto para usar Metal!"
echo "   URL: http://localhost:11434"
echo ""
echo "Dica: Para verificar se Metal esta ativo, execute: ollama ps"
echo "Para ver logs: tail -f /tmp/ollama.log"

