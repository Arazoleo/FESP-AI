# FESP-AI

Sistema RAG (Retrieval-Augmented Generation) para consulta de informacoes academicas da UNIFESP Campus Sao Jose dos Campos.

## Sobre

Este projeto utiliza ChromaDB como banco vetorial e Ollama como LLM local para responder perguntas sobre:

- Disciplinas do BCT e cursos de formacao especifica
- Regimento interno do campus
- Plano de evacuacao
- Cursos sequenciais
- Perfil academico e identidade do campus

## Estrutura

```
FESP-AI/
├── jsons_disciplinas/     # 86 arquivos JSON de disciplinas
├── jsons_regimentos/      # Documentos institucionais
├── llm.py                 # Sistema RAG principal
└── ajudauni_downloader/   # Scripts auxiliares
```

## Requisitos

- Python 3.9+
- Ollama rodando localmente
- Modelo: qwen2.5:14b
- Embeddings: nomic-embed-text

## Instalacao

```bash
python -m venv venv
source venv/bin/activate
pip install langchain-ollama langchain-community chromadb
```

## Uso

### Modo interativo

```bash
python llm.py
```

Comandos disponiveis:
- `sync` - Atualiza o banco vetorial com novos arquivos
- `status` - Mostra quantidade de documentos indexados
- `sair` - Encerra o programa

### Uso programatico

```python
from llm import RAGUnifesp

rag = RAGUnifesp()
rag.sync()

resposta = rag.query("Qual a carga horaria de Banco de Dados?")
print(resposta)
```

## Sincronizacao automatica

O sistema detecta automaticamente:
- Novos arquivos JSON adicionados
- Arquivos modificados
- Arquivos removidos

Basta rodar `rag.sync()` ou digitar `sync` no modo interativo.

## Adicionar novos documentos

1. Crie um arquivo JSON na pasta apropriada:
   - `jsons_disciplinas/` para disciplinas
   - `jsons_regimentos/` para documentos institucionais

2. Execute `sync` para indexar

## Exemplos de perguntas

- "Quais sao os pre-requisitos de Algoritmos II?"
- "O que e o BCT?"
- "Qual o ponto de encontro em caso de incendio?"
- "Quais cursos sequenciais existem?"
- "Quais sao as camaras do ICT?"
