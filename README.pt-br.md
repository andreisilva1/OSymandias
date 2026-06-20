<div align="right">
  <a href="README.md">English</a> · <b>Português BR</b>
</div>

<div align="center">

<img src="banner.svg" width="100%"/>

*"Contemplai minhas obras, ó Poderosos, e despachae."*

**Runtime multi-agente para desenvolvedores Python. Um comando para iniciar tudo.**

[![PyPI](https://img.shields.io/pypi/v/osymandias?style=flat-square&color=C8A040)](https://pypi.org/project/osymandias)
[![Python](https://img.shields.io/badge/python-3.11+-blue?style=flat-square)](https://python.org)
[![License](https://img.shields.io/badge/license-MIT-green?style=flat-square)](LICENSE)
[![Tests](https://github.com/andreisilva1/OSymandias/actions/workflows/tests.yml/badge.svg)](https://github.com/andreisilva1/OSymandias/actions/workflows/tests.yml)
[![Status](https://img.shields.io/badge/status-in%20development-orange?style=flat-square)](https://github.com/andreisilva1/OSymandias)

📖 **Documentação:** [English](DOCS_en.md) · [Português BR](DOCS_pt-br.md)

</div>

---

```bash
pip install osymandias && osy init && osy serve
```

PostgreSQL · Redis · RabbitMQ · Qdrant · 4 Celery workers · dashboard em `localhost:47759` — tudo com um comando.

---

## O problema

Construir um sistema multi-agente significa conectar uma fila de tarefas, um vector store, um message broker, memória compartilhada entre agentes, uma forma de observar o que está acontecendo e código de cola para segurar tudo. Antes de escrever um único agente.

**OSymandias é essa infraestrutura.** Decore suas funções. Envie um objetivo em linguagem natural. Veja rodar.

---

## Como funciona

```mermaid
flowchart LR
    J(["📋 Job\nobjetivo em texto"])
    P["⚙️ PlannerAgent\ndecompõe em tarefas"]
    T1["🤖 ResearchAgent"]
    T2["🤖 WriterAgent"]
    T3["🤖 SeuAgente\n@osy.agent"]
    E["✅ EvaluatorAgent\nvalida e repete se necessário"]
    O(["📄 Output"])

    J --> P
    P --> T1 & T2 & T3
    T1 & T2 & T3 --> E
    E --> O
```

Cada agente tem acesso a 20 ferramentas nativas (busca na web, I/O de arquivos, HTTP, Python eval…), suas funções `@osy.tool` e memória compartilhada — tudo observável em tempo real pelo dashboard.

---

## Três conceitos

### 1 — Transforme qualquer função em uma ferramenta de agente

```python
from osymandias import osy

@osy.tool
def buscar_precos(empresa: str) -> dict:
    """Busca preços em tempo real no banco interno."""
    return db.query(empresa)
```

Schema inferido dos type hints. Sem YAML. Sem registro manual. Só `osy serve`.

---

### 2 — Conecte qualquer framework como agente

```python
from osymandias import osy, OsyContext

@osy.agent("ResearchAgent", framework="langchain", llm_model="qwen2.5:7b")
def research(task: str, ctx: OsyContext) -> dict:
    ctx.emit_event("TASK_PROGRESS", {"step": "buscando"})
    return {"resumo": minha_chain.invoke(task)}
```

LangChain · CrewAI · LlamaIndex · Smolagents · OpenAI Agents SDK · Python puro — todos funcionam da mesma forma. O PlannerAgent descobre e roteia para seus agentes automaticamente no `osy serve`.

---

### 3 — Orquestre de dentro de um agente

```python
@osy.agent("OrchestratorAgent")
def orquestrar(task: str, ctx: OsyContext) -> dict:
    ids = ctx.spawn_tasks([
        {"title": "Pesquisa",  "agent_type": "ResearchAgent", "description": task},
        {"title": "Análise",   "agent_type": "AnalystAgent",  "description": task},
    ])
    resultados = ctx.wait_for_tasks(ids)        # paralelo, Redis pub/sub — sem polling
    ctx.write_memory("combinado", resultados)   # compartilhado entre todos os agentes do job
    return resultados
```

---

## Controles de produção

A parte difícil de agentes não é fazê-los responder — é torná-los seguros para rodar sem supervisão.

- **Limite de tokens (budget)** — defina `max_tokens` no job; ele para com `BUDGET_EXCEEDED` antes de um loop descontrolado queimar sua cota.
- **Aprovação humana (human-in-the-loop)** — marque uma task como `requires_approval`; ela aguarda em `HUMAN_REVIEW` até você aprovar via API.
- **Webhooks de lifecycle** — registre uma URL e receba um POST em `JOB_COMPLETED` / `JOB_FAILED` / `BUDGET_EXCEEDED`.
- **Custo e tokens reais** — breakdown por agente e por ferramenta, precificado via LiteLLM.
- **Traces de execução** — a cadeia de raciocínio completa (eventos, tool calls, conversa) de qualquer task.
- **Cache de resposta** — cache determinístico opcional de LLM que corta custo em retries e replays.

```bash
# Job com teto de tokens que pausa para aprovação
curl -X POST localhost:47760/api/v1/jobs -d '{"title":"...","max_tokens":50000}'
curl -X POST localhost:47760/api/v1/jobs/$ID/tasks/$TASK/approve
```

---

## Dashboard

>*A interface pode apresentar diferenças em relação à imagem.*

![OSymandias dashboard](assets/dashboard_preview.png)

Stream de eventos em tempo real via SSE. Árvore de sub-tarefas. Preview do output enquanto o job roda. Resubmissão com um clique.

---

## Provedores de LLM suportados

OpenAI · Anthropic · DeepSeek · Groq · Gemini · **Ollama (local, sem chave de API)**

Troque o modelo por agente pelo dashboard — sem necessidade de reiniciar.

---

<details>
<summary>Sem Docker? Serviços externos?</summary>

```bash
# .env — descomente e aponte para suas próprias instâncias
OSY_NO_DOCKER=1
OSY_POSTGRES_URL=postgresql+asyncpg://user:pass@host:5432/osymandias
OSY_REDIS_URL=redis://host:6379/0
OSY_RABBITMQ_URL=amqp://user:pass@host:5672/
OSY_QDRANT_URL=http://host:6333

osy serve --no-docker
```

</details>

<details>
<summary>Escalabilidade horizontal</summary>

```bash
# Nó A — API + scheduler
osy serve

# Nó B — workers extras (aponte para broker/redis compartilhados)
OSY_RABBITMQ_URL=amqp://... OSY_REDIS_URL=redis://... \
  osy workers --queues agents,tools --concurrency 8
```

</details>

---

<div align="center">
<sub>Construído com FastAPI · Next.js · Celery · PostgreSQL · Redis · RabbitMQ · Qdrant · LiteLLM</sub>
</div>
