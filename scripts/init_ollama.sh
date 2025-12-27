#!/bin/bash
# Script para inicializar modelos do Ollama no container

echo "Aguardando Ollama estar pronto..."
sleep 10

echo "Baixando modelos do Ollama..."

# Baixar modelo LLM
ollama pull qwen2.5:7b

# Baixar modelo de embeddings
ollama pull mxbai-embed-large

echo "Modelos instalados com sucesso!"

