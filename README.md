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
├── src/
│   ├── __init__.py        # Exports principais
│   ├── config.py          # Configuracoes
│   ├── parsers.py         # Parsers de JSON
│   ├── rag.py             # Classe RAG principal
│   ├── cli.py             # Interface de linha de comando
│   └── api.py             # API FastAPI para chat web
├── frontend/              # Frontend Next.js
│   ├── app/               # Páginas e componentes
│   └── package.json       # Dependências Node.js
├── jsons_disciplinas/     # 86 arquivos JSON de disciplinas
├── jsons_regimentos/      # Documentos institucionais
├── main.py                # Ponto de entrada CLI
├── start_api.py           # Script para iniciar API
└── ajudauni_downloader/   # Scripts auxiliares
```

## Requisitos

- Python 3.9+
- Ollama rodando localmente
- Modelo LLM: qwen2.5:7b (configurável em `src/config.py`)
- Embeddings: mxbai-embed-large (configurável em `src/config.py`)

## Instalacao

```bash
python -m venv venv
source venv/bin/activate  # No Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### Baixar modelos do Ollama

```bash
ollama pull qwen2.5:7b
ollama pull mxbai-embed-large
```

## Uso

### Modo interativo (CLI)

```bash
python main.py
```

Comandos disponiveis:
- `sync` - Atualiza o banco vetorial com novos arquivos
- `status` - Mostra quantidade de documentos indexados
- `sair` - Encerra o programa

### Interface Web (Chat)

1. **Iniciar a API backend:**

```bash
python start_api.py
```

A API estará disponível em `http://localhost:8000`

2. **Iniciar o frontend:**

```bash
cd frontend
npm install
npm run dev
```

O frontend estará disponível em `http://localhost:3000`

**Nota:** Certifique-se de que o Ollama está rodando antes de iniciar a API.

### Uso programatico

```python
from src import RAGUnifesp

rag = RAGUnifesp()
rag.sync()

resposta = rag.query("Qual a carga horaria de Banco de Dados?")
print(resposta)
```

### API REST

A API FastAPI fornece os seguintes endpoints:

- `GET /` - Informações da API
- `GET /health` - Status de saúde do sistema
- `POST /chat` - Enviar mensagem e receber resposta
- `GET /conversations/{conversation_id}` - Obter histórico de conversa
- `DELETE /conversations/{conversation_id}` - Deletar conversa
- `POST /conversations` - Criar nova conversa
- `GET /status` - Estatísticas do sistema

Documentação interativa disponível em `http://localhost:8000/docs`

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

## Docker (Recomendado)

Para executar tudo junto usando Docker Compose:

### Mac (com Metal/GPU) - Recomendado

```bash
# Opção 1: Script automático (inicia Ollama nativo + Docker)
./scripts/start_all.sh

# Opção 2: Manual
# 1. Iniciar Ollama nativo (com Metal)
./scripts/start_ollama_native.sh

# 2. Iniciar Docker (Frontend + Backend)
docker-compose up --build
```

**Por que Ollama nativo no Mac?** Para usar Metal Performance Shaders e acelerar os modelos com a GPU do Mac.

Acesse:
- Frontend: http://localhost:3000
- API: http://localhost:8000
- Docs: http://localhost:8000/docs
- Ollama: http://localhost:11434

Veja `QUICKSTART_DOCKER.md` para início rápido e `DOCKER.md` para mais detalhes e troubleshooting.
