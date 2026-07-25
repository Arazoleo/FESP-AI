# FESP-AI — Assistente Acadêmico Neurossimbólico da UNIFESP (ICT/SJC)

![Python](https://img.shields.io/badge/python-3.11+-blue)
![FastAPI](https://img.shields.io/badge/FastAPI-backend-009688)
![LangGraph](https://img.shields.io/badge/LangGraph-multi--agente-orange)
![Ollama](https://img.shields.io/badge/Ollama-gemma4%20%2B%20embeddinggemma-black)
![PyReason](https://img.shields.io/badge/PyReason-inferência%20FOL-purple)
![Status](https://img.shields.io/badge/status-pesquisa-lightgrey)

O **FESP-AI** é um assistente acadêmico **neurossimbólico** para o Instituto de Ciência e Tecnologia da UNIFESP (campus São José dos Campos). Ele combina um **Knowledge Graph** curricular (disciplinas, pré-requisitos, docentes, cursos), **regras de inferência FOL** executadas via **PyReason** e um **LLM** (Ollama), orquestrados por um pipeline **multi-agente em LangGraph** — com RAG híbrido (vetorial + BM25) sobre ementas e regimentos e um corpus vivo do **site institucional do campus**. A tese central: o LLM interpreta e redige, mas **quem julga os fatos é o grafo** — reduzindo alucinação em respostas acadêmicas críticas (pré-requisitos, matrizes curriculares, docentes).

![FESP-AI em execução](docs/screenshot-app.png)

## Arquitetura e Metodologia

Interpretação **LLM-first com grounding simbólico**: regex atua como fast-path/prior barato, o **LLM propõe** (intent, termo, reescrita de follow-ups) e o **KG julga** (grounding de entidades, validação de claims). Intents críticos (`SYMBOLIC_DIRECT_INTENTS` em `src/workflow/router.py`) tomam o **atalho simbólico**: a resposta vem direto do grafo, com **0% de alucinação por construção**.

```mermaid
flowchart TD
    U[Usuário] --> CR[context_resolver<br>anáforas + herança de entidade]
    CR --> R{Router<br>regex prior → LLM intérprete → KG juiz}
    R -->|SYMBOLIC_DIRECT_INTENTS| KG[Knowledge Graph<br>NetworkX + PyReason FOL]
    R -->|demais intents| AG[Agentes LangGraph<br>disciplinas · docentes · cursos ·<br>regimentos · web_sjc · notícias · conversa]
    KG -->|enriquecimento: fatos verificados| AG
    AG --> RAG[RAG híbrido<br>ChromaDB + BM25 + corpus do site]
    AG --> LLM[LLM Ollama]
    LLM --> V[Validador neurossimbólico<br>claims LLM→KG + reescrita corretiva]
    KG --> V
    V --> T[Telemetria GET /telemetry]
    V --> U2[Resposta com traço de regras + bounds]
```

**Loop bidirecional Neural ↔ Simbólico:**

- **Enriquecimento pré-geração** — fatos verificados do KG são injetados no prompt do agente antes da geração;
- **Validação de claims LLM→KG** — o LLM extrai triplas (código/docente/pré-requisito) da própria resposta e o KG julga cada uma;
- **B1 — Reescrita corretiva** — violações disparam corretores dedicados (pré-requisitos, docentes) ou reescrita genérica via LLM ancorada nos fatos do KG;
- **B2 — Propagação de incerteza com bounds** — `path_confidence` propaga o menor `confidence` das arestas do caminho e a resposta anota elos parciais ("confiança 70%");
- **B3 — Path-finding no DAG de pré-requisitos** — `plan_minimal_path` (BFS topológico) planeja o caminho mínimo até uma disciplina-alvo;
- **B4 — Regras FOL explícitas com traço** — respostas simbólicas citam as regras aplicadas (`prereq_transitivity`, `minimal_path`, `unlock_condition`);
- **B5 — KGC estrutural + semântico** — completação do grafo combinando similaridade estrutural (0.6) e embeddings semânticos (0.4).

**Outras peças:** fusão multi-fonte **KG ↔ site** com regra de precedência (em divergência, vale o KG e a resposta avisa que a página pode estar desatualizada); **crawler multi-domínio** do site do campus com seccionamento por headings (páginas longas viram uma entrada de corpus por seção h2/h3, com âncora); **telemetria** do loop neurossimbólico (grounding, correções B1, reescritas LLM, claims) em `GET /telemetry`; `kg.lint()` no build do grafo (duplicatas, ciclos no DAG, pré-requisitos pendurados).

## Resultados

| Métrica | Resultado |
|---|---|
| Routing accuracy (82 queries, gabarito com alternativas) | **96%** (79/82) |
| Verificação simbólica das respostas no caminho simbólico | **89%** (47/53) |
| Eval conversacional do site (10 conversas multi-turno) | **29/29** (100%) |
| LLM-as-judge — correctness/groundedness no caminho simbólico | **5.0 / 5.0** |

Números do run mais recente de `eval/eval_neurosymbolic.py` (07/2026) e de `eval/eval_site_conversations.py`; histórico e detalhes em `BACKLOG.md`.

## Stack

Python 3.11 · FastAPI · LangGraph/LangChain · Ollama (**gemma4** geração + **embeddinggemma** embeddings) · ChromaDB (+ BM25) · NetworkX · PyReason · Next.js (frontend).

## Como rodar

```bash
cp .env.example .env        # escolha MODEL_NAME / EMBEDDING_MODEL
docker compose up -d        # backend :8000 + frontend :3000
```

Requer Ollama acessível (local ou cloud — veja `OLLAMA_CLOUD.md`) com os modelos baixados (`ollama pull gemma4:31b-cloud` e `ollama pull embeddinggemma`).

**Endpoints principais** (`http://localhost:8000`, docs interativas em `/docs`):

| Endpoint | Descrição |
|---|---|
| `POST /chat` | Conversa com o pipeline completo (histórico por `conversation_id`) |
| `POST /crawl-sjc` | (Re)gera o corpus do site institucional do campus |
| `GET /telemetry` | Contadores do loop neurossimbólico |
| `GET /health` | Health check |
| `GET /graph-viewer` · `GET /planner` | Visualizador do KG e planner de grade |

**Testes de regressão** (offline, sem LLM/backend):

```bash
python3 test_routing.py               # roteamento (31 casos)
python3 test_site_crawler.py          # crawler/seccionamento (20 casos)
python3 test_neurosym_b1_b2.py        # B1 reescrita corretiva / B2 bounds
python3 test_conversation_history.py  # histórico multi-turno nos prompts
python3 test_graph_term_extraction.py # grounding de termos no KG
python3 test_neurosymbolic.py         # validador neurossimbólico
python3 test_planner.py               # planner de grade (BFS topológico)
python3 test_pyreason_bounds.py       # propagação de bounds via PyReason
python3 test_pyreason_parity.py       # paridade PyReason × referência Python
```

**Evals** (requerem o backend de pé em `localhost:8000`):

```bash
python3 eval/eval_neurosymbolic.py --judge   # routing + verificação simbólica + LLM-judge
python3 eval/eval_site_conversations.py      # 10 conversas multi-turno (exit code ≠ 0 em falha)
python3 eval/eval_baselines.py               # baselines: LLM-only, RAG padrão, GraphRAG
```

## Estrutura do repositório

```
├── src/
│   ├── api.py                     # FastAPI (endpoints acima)
│   ├── multi_agent_rag.py         # orquestração multi-agente
│   ├── workflow/                  # router (SYMBOLIC_DIRECT_INTENTS), pipeline LangGraph, estado
│   ├── agents/                    # disciplinas, docentes, cursos, regimentos, web_sjc, notícias...
│   ├── knowledge_graph.py         # KG (NetworkX) + lint
│   ├── pyreason_engine.py         # regras FOL via PyReason (bounds)
│   ├── neurosymbolic_validator.py # claims LLM→KG + reescrita corretiva (B1)
│   ├── graph_rag.py               # GraphRAG + grounding de termos no KG
│   ├── site_crawler.py            # crawler do site do campus (seções por heading)
│   ├── context_resolver.py        # anáforas e herança de contexto entre turnos
│   └── telemetry.py               # contadores do loop neurossimbólico
├── frontend/                      # chat Next.js
├── eval/                          # scripts de avaliação e tabelas do paper
├── paper/                         # LaTeX (paper, ENIAC, slides)
├── markdown_*/                    # dados curriculares (fonte do KG e do RAG)
├── test_*.py                      # testes de regressão offline
└── BACKLOG.md                     # histórico de features e backlog
```
