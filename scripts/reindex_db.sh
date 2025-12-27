#!/bin/bash
# Script para forçar a reindexação do banco vetorial
# Útil após mudanças no parser ou configurações

set -e

echo "Forcando reindexacao do banco vetorial..."

if docker ps | grep -q "fesp-ai-backend"; then
    echo "Executando reindexacao no container Docker..."
    docker exec fesp-ai-backend python -c "
from src.rag import RAGUnifesp
rag = RAGUnifesp()
print('Recriando banco vetorial...')
rag.sync(force=True)
print('Banco reindexado com sucesso!')
"
else
    echo "Executando reindexacao localmente..."
    python -c "
from src.rag import RAGUnifesp
rag = RAGUnifesp()
print('Recriando banco vetorial...')
rag.sync(force=True)
print('Banco reindexado com sucesso!')
"
fi

echo ""
echo "Reindexacao concluida!"
echo "Agora voce pode testar perguntas sobre docentes novamente."

