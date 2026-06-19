# OSymandias — Documentação

> Referência completa da API e guia de uso.

---

## Índice

1. [Instalação](#instalação)
2. [Referência da CLI](#referência-da-cli)
   - [osy --version](#osy---version)
3. [Autenticação](#autenticação)
4. [@osy.tool — ferramentas nativas](#osytool)
5. [@osy.agent — agentes externos](#osyagent)
6. [osymandias.toml](#osymandiastoml)
7. [OsyContext](#osycontext)
8. [Adaptadores](#adaptadores)
   - [LangChain](#langchain)
   - [CrewAI](#crewai)
   - [LlamaIndex](#llamaindex)
   - [Smolagents](#smolagents)
   - [OpenAI Agents SDK](#openai-agents-sdk)
9. [Enviando jobs via API](#enviando-jobs-via-api)
   - [Job em linguagem natural](#job-em-linguagem-natural)
   - [Plano de tarefas explícito (`__task_plan__`)](#plano-de-tarefas-explícito-__task_plan__)
   - [Resubmissão de um job](#resubmissão-de-um-job)
10. [Páginas do dashboard](#páginas-do-dashboard)
11. [Provedores de LLM suportados](#provedores-de-llm-suportados)
12. [Escalabilidade](#escalabilidade)
13. [Dependências opcionais](#dependências-opcionais)

---

## Instalação

```bash
pip install osymandias
```

**Pré-requisitos:** Python 3.11+, Docker (utilizado para gerenciar os containers de infraestrutura).

Extras opcionais por framework:

```bash
pip install osymandias[langchain]
pip install osymandias[crewai]
pip install osymandias[llamaindex]
pip install osymandias[smolagents]
pip install osymandias[openai-agents]

# Todos de uma vez
pip install osymandias[all]
```

---

## Referência da CLI

### `osy --version`

Exibe a versão instalada e encerra.

```bash
osy --version   # osy 1.0.1
osy -V
```

---

### `osy init`

Inicializa um novo projeto OSymandias no diretório atual.

```
osy init
```

Prompts interativos solicitam o provedor de LLM e a chave de API. Cria:

| Arquivo | Finalidade |
|---|---|
| `OSY.compose.yml` | Docker Compose com todos os containers de infraestrutura |
| `OSY.nginx.conf` | Config do Nginx que serve o dashboard na porta 47759 |
| `.env` | Chaves dos provedores de LLM e configuração do runtime |
| `osy_tools.py` | Exemplo de arquivo com `@osy.tool` para começar |
| `osymandias.toml` | Config do projeto (agent_modules comentado) |

Seguro para re-executar — arquivos existentes são ignorados.

---

### `osy serve`

Inicia o runtime completo.

```
osy serve [--no-docker] [--concurrency N]
```

Sobe os containers Docker, executa as migrações do banco, descobre os callables `@osy.tool` e `@osy.agent`, e inicia:

| Serviço | Porta |
|---|---|
| Dashboard (nginx) | `47759` |
| Backend FastAPI | `47760` |
| Servidor interno de ferramentas | `47761` |

**Modo `--no-docker`** — ignora o Docker e conecta a serviços gerenciados externamente:

```bash
# No .env — descomente e atualize as URLs para suas instâncias:
# OSY_NO_DOCKER=1
# OSY_POSTGRES_URL=postgresql+asyncpg://user:pass@meu-db.exemplo.com:5432/osymandias
# OSY_REDIS_URL=redis://meu-redis.exemplo.com:6379/0
# OSY_RABBITMQ_URL=amqp://user:pass@meu-rabbit.exemplo.com:5672/
# OSY_QDRANT_URL=http://meu-qdrant.exemplo.com:6333

osy serve --no-docker
# ou: OSY_NO_DOCKER=1 osy serve
```

`osy serve --no-docker` verifica a conectividade com todos os serviços configurados antes de iniciar e exibe um erro claro caso algum esteja inacessível. `osy stop` e `osy down` ignoram o Docker graciosamente quando não disponível.

**`--concurrency N`** — número de slots simultâneos do worker Celery neste nó (padrão: 4). Também lê de `OSY_WORKER_CONCURRENCY` no `.env`.

---

### `osy logs`

Acompanha eventos de um job específico ou do stream global.

```
osy logs [JOB_ID] [--follow] [--limit N] [--type TIPO_EVENTO]
```

| Opção | Padrão | Descrição |
|---|---|---|
| `JOB_ID` | — | ID do job ou prefixo sem ambiguidade. Omita para todos os jobs. |
| `--follow` / `-f` | desligado | Assina o pub/sub do Redis e transmite eventos ao vivo |
| `--limit N` / `-n N` | `50` | Número de eventos passados a exibir antes do stream |
| `--type` / `-t` | — | Filtra por tipo de evento (ex.: `TASK_PROGRESS`, `TOOL_CALL_STARTED`) |

```bash
osy logs                             # últimos 50 eventos de todos os jobs
osy logs abc123                      # últimos 50 eventos do job abc123
osy logs abc123 -f                   # stream ao vivo de todos os eventos do job
osy logs abc123 -f -t TASK_PROGRESS  # stream ao vivo apenas de eventos de progresso
```

---

### `osy workers`

Inicia workers Celery **adicionais** para escalabilidade horizontal. Sem servidor de API, sem Docker — apenas processos worker conectando ao RabbitMQ e Redis compartilhados.

```
osy workers [--queues FILAS] [--concurrency N] [--loglevel NÍVEL]
```

| Opção | Padrão | Variável de ambiente |
|---|---|---|
| `--queues` | `agents,tools,evaluator` | `OSY_WORKER_QUEUES` |
| `--concurrency` | `4` | `OSY_WORKER_CONCURRENCY` |
| `--loglevel` | `warning` | — |

Execute em qualquer máquina que consiga acessar o mesmo broker/backend. Veja [Escalabilidade](#escalabilidade).

---

### `osy stop`

Pausa todos os containers sem deletar dados.

```
osy stop
```

---

### `osy down`

Para e remove os containers, mas mantém os volumes (dados do PostgreSQL, vetores do Qdrant).

```
osy down
```

---

### `osy delete`

Para e remove containers **e** volumes. Solicita confirmação antes de deletar.

```
osy delete
```

> **Atenção:** Isso deleta permanentemente todos os jobs, memória e dados de agentes.

---

## Autenticação

O OSymandias inclui um controle opcional por chave de API estática. A autenticação está **desabilitada por padrão** — nenhuma configuração necessária para desenvolvimento local.

### Habilitando a autenticação

Defina `OSY_API_KEY` no `.env` (ou como variável de ambiente):

```bash
# .env
OSY_API_KEY=minha-chave-secreta
```

Reinicie com `osy serve`. Todos os endpoints `/api/v1/*` passarão a exigir a chave. `/health`, `/docs` e `/openapi.json` estão sempre isentos.

### Enviando a chave

Qualquer um dos headers funciona:

```bash
# Header Authorization (esquema Bearer)
curl -H "Authorization: Bearer minha-chave-secreta" http://localhost:47760/api/v1/jobs

# Header X-Api-Key
curl -H "X-Api-Key: minha-chave-secreta" http://localhost:47760/api/v1/jobs
```

Requisições sem chave válida recebem `401 Unauthorized`.

### Desabilitando a autenticação

Remova `OSY_API_KEY` do `.env` (ou defina como string vazia) e reinicie.

---

## @osy.tool

Registra qualquer função Python como uma ferramenta de agente. As ferramentas ficam disponíveis para agentes nativos via dashboard (página `/tools`).

```python
from osymandias import osy

@osy.tool
def minha_ferramenta(arg1: str, arg2: int = 0) -> dict:
    """Descrição de uma linha exibida no dashboard."""
    return {"resultado": ...}
```

**Regras:**
- O nome da função se torna o nome da ferramenta.
- A primeira linha do docstring se torna a descrição.
- Tipos de parâmetros e valores padrão são inferidos dos type hints.
- O tipo de retorno deve ser `dict` (ou serializável em JSON).

**Exemplo — múltiplas ferramentas:**

```python
from osymandias import osy

@osy.tool
def buscar_banco_de_dados(query: str, limite: int = 10) -> dict:
    """Busca no banco de dados interno de produtos. Retorna itens correspondentes."""
    rows = db.execute("SELECT * FROM products WHERE ...", (query, limite))
    return {"itens": [dict(r) for r in rows]}

@osy.tool
def enviar_mensagem_slack(canal: str, texto: str) -> dict:
    """Envia uma mensagem para um canal do Slack."""
    slack_client.chat_postMessage(channel=canal, text=texto)
    return {"ok": True}
```

As ferramentas são descobertas automaticamente — nenhuma chamada de registro necessária. Qualquer arquivo `.py` no projeto que importe `osymandias` é escaneado ao executar `osy serve`.

---

## @osy.agent

Registra qualquer callable Python como um agente externo do OSymandias. O agente é despachado via Celery e aparece no dashboard `/agents` com um badge colorido.

```python
from osymandias import osy, OsyContext

@osy.agent("MeuAgente")
def meu_agente(task: str, ctx: OsyContext) -> dict:
    ...
    return {"resultado": ...}
```

### Assinatura

```python
osy.agent(
    name: str,
    *,
    description: str = "",
    framework: str | None = None,
    llm_provider: str | None = None,
    llm_model: str | None = None,
    output_schema = None,
    input_schema = None,
    tools: list[str] | None = None,
) -> Callable
```

### Parâmetros

| Parâmetro | Tipo | Descrição |
|---|---|---|
| `name` | `str` | **Obrigatório.** Nome de exibição e chave de despacho. Deve ser único. |
| `description` | `str` | Descrição legível exibida no painel de detalhes do agente. |
| `framework` | `str \| None` | Framework utilizado. Controla a cor do badge no registro. Valores aceitos: `"crewai"`, `"langchain"`, `"llamaindex"`, `"smolagents"`, `"autogen"`. Qualquer outra string é exibida como está. |
| `llm_provider` | `str \| None` | Provedor utilizado internamente (ex.: `"ollama"`, `"openai"`). Apenas informativo. |
| `llm_model` | `str \| None` | Modelo utilizado internamente (ex.: `"qwen2.5:7b"`). Apenas informativo. |
| `output_schema` | Modelo Pydantic ou `dict` | JSON Schema descrevendo o formato de retorno. Exibido no painel de detalhes. |
| `input_schema` | Modelo Pydantic ou `dict` | JSON Schema descrevendo a entrada esperada além de `task: str`. |
| `tools` | `list[str] \| None` | Nomes das ferramentas que este agente utiliza. Apenas informativo. |

> **Todos os kwargs são opcionais.** O agente executa independentemente do que for declarado. Eles existem apenas para enriquecer a exibição no dashboard.

### Registro adaptativo de agentes

Agentes externos são automaticamente incluídos no contexto do PlannerAgent em cada job. Quando um job em linguagem natural é submetido (sem `__task_plan__`), o planner recebe a lista completa de tipos de agentes disponíveis — nativos *e* externos — e pode rotear tarefas para qualquer um deles pelo nome. Nenhuma configuração necessária: registre um agente com `@osy.agent` e o planner o descobrirá no próximo `osy serve`.

```
osy serve          ← descobre callables @osy.agent, popula o banco
↓
POST /jobs {"title": "...", "description": "Pesquise EVs e escreva um resumo"}
↓
PlannerAgent        ← vê: ResearchAgent, WriterAgent, AnalystAgent,
                           MeuAgentePersonalizado [langchain] (externo), ...
↓
Cria tarefas roteadas para os agentes corretos automaticamente
```

### Assinatura do callable

A função decorada deve aceitar `task: str` como primeiro argumento e retornar um `dict`. O parâmetro `ctx: OsyContext` é opcional — inclua-o para acessar memória, eventos e sub-tarefas.

```python
# Mínimo
@osy.agent("EchoAgent")
def echo(task: str) -> dict:
    return {"resultado": task}

# Com contexto
@osy.agent("EchoAgent")
def echo(task: str, ctx: OsyContext) -> dict:
    ctx.emit_event("TASK_PROGRESS", {"step": "ecoando"})
    return {"resultado": task}
```

### Exemplo completo

```python
from pydantic import BaseModel
from osymandias import osy, OsyContext

class ResultadoPesquisa(BaseModel):
    resumo: str
    fontes: list[str]
    confianca: float

@osy.agent(
    "ResearchAgent",
    framework="langchain",
    description="Pesquisa na web e resume os resultados",
    llm_provider="ollama",
    llm_model="qwen2.5:7b",
    output_schema=ResultadoPesquisa,
)
def research_agent(task: str, ctx: OsyContext) -> dict:
    ctx.emit_event("TASK_PROGRESS", {"step": "iniciando pesquisa"})
    chain = build_chain()
    resultado = chain.invoke(task)
    ctx.write_memory("output_pesquisa", {"resumo": resultado})
    return {"resumo": resultado, "fontes": [], "confianca": 0.9}
```

---

## osymandias.toml

Declara quais módulos Python contêm seus callables `@osy.agent`. Colocado na raiz do projeto (criado automaticamente pelo `osy init`).

```toml
# osymandias.toml

agent_modules = [
    "meuprojeto.agents",
    "meuprojeto.crews",
    "meuprojeto.pipelines.research",
]
```

Ao executar `osy serve`, cada módulo é importado em ordem e todos os decoradores `@osy.agent` nesses módulos são executados, populando o registro de agentes.

**Fallback:** Se `agent_modules` estiver ausente ou o arquivo não tiver entradas, `osy serve` faz fallback para escanear todos os arquivos `.py` no diretório do projeto que importam `osymandias`. Conveniente durante o desenvolvimento, mas mais lento para projetos grandes.

**Alternativa:** Você também pode declarar os módulos no `pyproject.toml`:

```toml
[tool.osymandias]
agent_modules = ["meuprojeto.agents"]
```

`osymandias.toml` tem prioridade sobre `pyproject.toml` se ambos existirem.

---

## OsyContext

`OsyContext` é injetado como parâmetro `ctx` de cada callable `@osy.agent` no momento da execução. Fornece acesso à memória compartilhada do job, ao stream de eventos ao vivo e ao spawn de sub-tarefas — tudo com escopo no job atual.

```python
from osymandias import OsyContext
```

---

### `ctx.write_memory(key, value)`

Escreve um valor na memória compartilhada do job atual.

```python
ctx.write_memory(key: str, value: dict) -> None
```

- Sobrescreve qualquer valor anterior na mesma chave.
- Todos os agentes no mesmo job compartilham o mesmo namespace — um agente LangChain pode ler o que um agente CrewAI escreveu.
- Persistido imediatamente na transação atual do banco.

```python
ctx.write_memory("plano", {
    "etapas": ["pesquisa", "análise", "escrita"],
    "prioridade": "alta",
})
```

---

### `ctx.read_memory(key)`

Lê um valor previamente escrito da memória do job.

```python
ctx.read_memory(key: str) -> dict | None
```

Retorna `None` se a chave ainda não existir.

```python
plano = ctx.read_memory("plano")
if plano:
    etapas = plano["etapas"]
```

---

### `ctx.search_memory(query, top_k=5)`

Busca semântica vetorial sobre todas as entradas de memória do job atual.

```python
ctx.search_memory(query: str, top_k: int = 5) -> list[dict]
```

Utiliza embeddings do Qdrant. Útil para recuperar outputs passados relevantes sem conhecer a chave exata.

```python
entradas = ctx.search_memory("preços de concorrentes", top_k=3)
for e in entradas:
    print(e["key"], e["value"])
```

---

### `ctx.emit_event(event, data)`

Emite um evento que é transmitido ao vivo para o feed SSE do dashboard.

```python
ctx.emit_event(event: str, data: dict) -> None
```

Os eventos aparecem instantaneamente na timeline do job. Convenções comuns (não obrigatórias):

| Tipo de evento | Payload típico |
|---|---|
| `"TASK_PROGRESS"` | `{"pct": 50, "step": "analisando"}` |
| `"AGENT_LOG"` | `{"message": "encontradas 12 fontes"}` |
| Qualquer string customizada | Qualquer dict |

```python
ctx.emit_event("TASK_PROGRESS", {"pct": 25, "step": "buscando fontes"})
ctx.emit_event("AGENT_LOG", {"message": f"query retornou {n} resultados"})
```

---

### `ctx.spawn_tasks(task_defs)`

Cria uma ou mais sub-tarefas que rodam sob a tarefa atual.

```python
ctx.spawn_tasks(task_defs: list[dict]) -> list[uuid.UUID]
```

Cada sub-tarefa é enfileirada imediatamente no scheduler Celery e executa em paralelo. As tarefas aparecem como uma árvore sob a tarefa pai na timeline do job.

**Chaves de task_def:**

| Chave | Obrigatório | Descrição |
|---|---|---|
| `title` | Sim | Nome de exibição da sub-tarefa |
| `agent_type` | Não | Nome do agente registrado para despacho (padrão: `"ResearchAgent"`) |
| `description` | Não | Contexto de entrada passado ao agente |

Retorna uma lista de UUIDs de tarefas na mesma ordem de `task_defs`.

```python
ids = ctx.spawn_tasks([
    {
        "title": "Pesquisa de Mercado",
        "agent_type": "ResearchAgent",
        "description": f"Pesquise o mercado de EVs: {task}",
    },
    {
        "title": "Análise de Concorrentes",
        "agent_type": "AnalystAgent",
        "description": f"Analise os principais concorrentes de EVs para: {task}",
    },
])
```

---

### `ctx.wait_for_tasks(task_ids, timeout=90)`

Bloqueia até que todas as sub-tarefas especificadas atinjam um estado terminal (concluída, falha ou cancelada).

```python
ctx.wait_for_tasks(task_ids: list[uuid.UUID], timeout: int = 90) -> dict[str, dict]
```

Assina o canal pub/sub do Redis do job e acorda imediatamente quando cada tarefa é concluída — sem intervalo de polling fixo. Faz fallback para uma leitura final no banco para cobrir o caso em que uma tarefa terminou antes da assinatura ser estabelecida. Retorna resultados para todas as tarefas independentemente de sucesso ou falha — verifique a chave `"error"` nos dicts individuais se necessário.

**Retorna:** `{título_da_tarefa: dict_resultado}`

Tarefas que não concluírem dentro do `timeout` em segundos são registradas como aviso; sua entrada no dict de resultado será `{}`.

```python
ids = ctx.spawn_tasks([...])
resultados = ctx.wait_for_tasks(ids, timeout=120)

pesquisa    = resultados.get("Pesquisa de Mercado", {})
concorrente = resultados.get("Análise de Concorrentes", {})

ctx.write_memory("combinado", {**pesquisa, **concorrente})
return {"merged": resultados}
```

---

## Adaptadores

Adaptadores encapsulam objetos de frameworks de terceiros para que seu output esteja em conformidade com o tipo de retorno `dict` esperado pelo `@osy.agent`. Cada adaptador está em `osymandias.adapters.*`.

---

### LangChain

```bash
pip install osymandias[langchain]
```

```python
from osymandias.adapters.langchain import LangChainAdapter
```

Encapsula qualquer **LCEL Runnable** do LangChain (chains, pipelines `prompt | llm | parser`) ou **AgentExecutor** legado. Automaticamente anexa um `OsyCallbackHandler` que encaminha eventos `on_llm_start`, `on_tool_start`, etc. como eventos `TASK_PROGRESS` para o dashboard.

```python
from langchain_core.prompts import ChatPromptTemplate
from langchain_ollama import ChatOllama
from osymandias import osy, OsyContext
from osymandias.adapters.langchain import LangChainAdapter

llm = ChatOllama(model="qwen2.5:7b")
prompt = ChatPromptTemplate.from_messages([
    ("system", "Você é um assistente de pesquisa."),
    ("human", "{input}"),
])
chain = prompt | llm

@osy.agent("ResearchAgent", framework="langchain", llm_model="qwen2.5:7b")
def research_agent(task: str, ctx: OsyContext) -> dict:
    return LangChainAdapter(chain).run(task, ctx=ctx)
```

**`LangChainAdapter.run(task, ctx=None) → dict`**

Invoca a chain com `{"input": task}`. Se `ctx` for fornecido, anexa o callback handler. Normaliza o resultado para `dict` automaticamente (lida com `str`, modelos Pydantic e dicts brutos).

---

### CrewAI

```bash
pip install osymandias[crewai]
```

```python
from osymandias.adapters.crewai import CrewAIAdapter
```

Encapsula um objeto `Crew`. O crew executa como uma caixa-preta — handoffs internos entre agentes dentro do crew não são rastreados individualmente no OSymandias. Use `ctx.emit_event` manualmente dentro de callbacks do CrewAI se precisar de progresso intermediário.

```python
from crewai import Agent, Crew, Task
from osymandias import osy, OsyContext
from osymandias.adapters.crewai import CrewAIAdapter

pesquisador = Agent(role="Pesquisador", goal="Encontrar dados precisos", backstory="...", llm="ollama/qwen2.5:7b")
analista    = Agent(role="Analista",    goal="Interpretar os achados",   backstory="...", llm="ollama/qwen2.5:7b")

crew = Crew(
    agents=[pesquisador, analista],
    tasks=[
        Task(description="Pesquise {task}", agent=pesquisador),
        Task(description="Analise os achados", agent=analista),
    ],
    verbose=False,
)

@osy.agent("AnalystCrew", framework="crewai")
def analyst_crew(task: str, ctx: OsyContext) -> dict:
    ctx.emit_event("TASK_PROGRESS", {"step": "crew iniciando"})
    resultado = CrewAIAdapter(crew).run(task, ctx=ctx)
    ctx.write_memory("output_crew", resultado)
    return resultado
```

**`CrewAIAdapter.run(task, ctx=None) → dict`**

Chama `crew.kickoff(inputs={"task": task})`. Normaliza `CrewOutput.raw` para `dict`.

---

### LlamaIndex

```bash
pip install osymandias[llamaindex]
```

```python
from osymandias.adapters.llamaindex import LlamaIndexAdapter
```

Encapsula um `QueryEngine` (usa `.query()`) ou um `ReActAgent` (usa `.chat()`). Nós fonte da recuperação são incluídos no resultado em `"sources"`. Imagens encontradas nos metadados dos nós fonte são coletadas em `"_media"` para renderização multimodal no dashboard.

```python
from llama_index.core import VectorStoreIndex, SimpleDirectoryReader
from osymandias import osy, OsyContext
from osymandias.adapters.llamaindex import LlamaIndexAdapter

docs  = SimpleDirectoryReader("./data").load_data()
index = VectorStoreIndex.from_documents(docs)
engine = index.as_query_engine()

@osy.agent("RAGAgent", framework="llamaindex", description="Responde perguntas a partir de documentos locais")
def rag_agent(task: str, ctx: OsyContext) -> dict:
    return LlamaIndexAdapter(engine).run(task, ctx=ctx)
```

**`LlamaIndexAdapter.run(task, ctx=None) → dict`**

Retorna `{"output": str, "sources": list[str], "_media": list[dict]}`.

---

### Smolagents

```bash
pip install osymandias[smolagents]
```

```python
from osymandias.adapters.smolagents import SmolAgentsAdapter
```

Encapsula qualquer agente HuggingFace Smolagents. Se o agente retornar um `matplotlib.figure.Figure` ou `PIL.Image`, é codificado em base64 e colocado em `"_media"` para renderização no dashboard.

```python
from smolagents import CodeAgent, HfApiModel
from osymandias import osy, OsyContext
from osymandias.adapters.smolagents import SmolAgentsAdapter

agent = CodeAgent(
    tools=[],
    model=HfApiModel("meta-llama/Llama-3.2-3B-Instruct"),
)

@osy.agent("HFCoder", framework="smolagents")
def hf_agent(task: str, ctx: OsyContext) -> dict:
    return SmolAgentsAdapter(agent).run(task, ctx=ctx)
```

**`SmolAgentsAdapter.run(task, ctx=None) → dict`**

Chama `agent.run(task)`. Retorna `{"output": str}` para texto, ou `{"output": "figure", "_media": [...]}` para outputs de imagem.

---

### OpenAI Agents SDK

```bash
pip install osymandias[openai-agents]
```

```python
from osymandias.adapters.openai_agents import OpenAIAgentsAdapter
```

Encapsula um `Agent` do OpenAI Agents SDK. Handoffs de agentes são emitidos como eventos `TASK_PROGRESS` para que a cadeia de handoffs seja visível no stream SSE do dashboard.

```python
from agents import Agent
from osymandias import osy, OsyContext
from osymandias.adapters.openai_agents import OpenAIAgentsAdapter

agent = Agent(
    name="Assistente",
    instructions="Você é um assistente prestativo.",
    model="gpt-4o",
)

@osy.agent("GPT4Agent", framework="openai-agents", llm_provider="openai", llm_model="gpt-4o")
def gpt4_agent(task: str, ctx: OsyContext) -> dict:
    return OpenAIAgentsAdapter(agent).run(task, ctx=ctx)
```

**`OpenAIAgentsAdapter.run(task, ctx=None) → dict`**

Chama `Runner.run_sync(agent, task)`. Emite um evento `TASK_PROGRESS` por mensagem de handoff se `ctx` for fornecido.

---

## Enviando jobs via API

### Job em linguagem natural

Deixe o PlannerAgent decompor o objetivo em tarefas automaticamente:

```bash
curl -X POST http://localhost:47760/api/v1/jobs \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Relatório Mercado EV",
    "description": "Pesquise o mercado europeu de veículos elétricos em 2024 e escreva um relatório estruturado.",
    "priority": "NORMAL",
    "input_payload": {}
  }'
```

**Valores de prioridade:** `"LOW"` · `"NORMAL"` · `"HIGH"` · `"CRITICAL"`

### Plano de tarefas explícito (`__task_plan__`)

Ignore o PlannerAgent completamente fornecendo uma lista de tarefas diretamente em `input_payload`. Útil quando você sabe exatamente quais agentes executar e em qual ordem:

```bash
curl -X POST http://localhost:47760/api/v1/jobs \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Relatório Mercado EV",
    "description": "Pesquisa de mercado EV",
    "priority": "NORMAL",
    "input_payload": {
      "__task_plan__": [
        {"title": "Pesquisa",   "agent_type": "ResearchAgent", "description": "Mercado EV na Europa 2024"},
        {"title": "Relatório",  "agent_type": "WriterAgent",   "description": "Escreva um relatório estruturado a partir dos achados"}
      ]
    }
  }'
```

Cada entrada em `__task_plan__` aceita as mesmas chaves que os task defs do `ctx.spawn_tasks`: `title` (obrigatório), `agent_type`, `description`.

### Resubmissão de um job

Copia a entrada de um job concluído ou com falha e cria uma nova execução:

```bash
curl -X POST http://localhost:47760/api/v1/jobs/<job-id>/resubmit
```

Retorna o novo objeto de job. O job original permanece inalterado. O botão de resubmissão também está disponível na view de detalhes do job no dashboard para qualquer job em estado terminal (COMPLETED, FAILED, CANCELLED).

### Python

```python
import httpx

resp = httpx.post("http://localhost:47760/api/v1/jobs", json={
    "title": "Relatório Mercado EV",
    "description": "Pesquise o mercado europeu de veículos elétricos em 2024.",
    "priority": "NORMAL",
    "input_payload": {},
})
job = resp.json()
print(job["id"])
```

Documentação interativa completa da API: **http://localhost:47760/api/v1/docs**

---

## Páginas do dashboard

| Página | URL | Descrição |
|------|-----|-------------|
| Jobs | `/jobs` | Lista de jobs — busca, filtro por status, paginação |
| Detalhe do job | `/jobs/{id}` | Visualizador de output (JSON/markdown/imagem/áudio), feed de eventos, árvore de tarefas, botão de resubmissão |
| Agentes | `/agents` | Registro de agentes — nativos e externos, painel de detalhes adaptativo, filtro por tipo/framework |
| Ferramentas | `/tools` | Ferramentas nativas e funções `@osy.tool` |
| Memória | `/memory` | Navegar e buscar entradas de memória de jobs/agentes, deletar chaves individuais |
| Eventos | `/events` | Stream de eventos global ao vivo — pausar/retomar, filtrar por job |
| Métricas | `/metrics` | Gráficos de 7 dias: jobs, tokens, estimativa de custo, taxa de sucesso |

### Preview de output ao vivo

Enquanto um job está em execução, a aba OUTPUT exibe um preview ao vivo das tarefas em andamento. Cada vez que um agente chama `ctx.emit_event("TASK_PROGRESS", {...})`, o dashboard atualiza o card da tarefa em tempo real via SSE — sem polling. Quando o job conclui e `output_payload` está disponível, o output final substitui o preview automaticamente.

---

## Provedores de LLM suportados

Configurado durante o `osy init` ou editando o `.env` diretamente.

| Provedor | Chave no `.env` | Exemplo de modelo |
|---|---|---|
| Ollama (local) | *(nenhuma necessária)* | `llama3.2`, `qwen2.5:7b` |
| OpenAI | `OPENAI_API_KEY` | `gpt-4o`, `gpt-4o-mini` |
| Anthropic | `ANTHROPIC_API_KEY` | `claude-sonnet-4-6` |
| DeepSeek | `DEEPSEEK_API_KEY` | `deepseek-chat` |
| Groq | `GROQ_API_KEY` | `llama-3.3-70b-versatile` |
| Gemini | `GEMINI_API_KEY` | `gemini-2.0-flash` |

Modelos podem ser alterados por agente no dashboard sem reiniciar o runtime.

---

## Escalabilidade

O OSymandias escala horizontalmente executando processos Celery worker adicionais em máquinas separadas. O servidor de API, o scheduler e os workers são independentes — apenas o RabbitMQ (fila de tarefas) e o Redis (resultados + pub/sub) precisam ser acessíveis por todos os nós.

### Arquitetura de filas

| Fila | Responsabilidade | Recomendação de concorrência |
|---|---|---|
| `scheduler` | Resolução de DAG, despacho de jobs | 1 (worker único, evita race conditions) |
| `agents` | Loops de agentes (chamadas de LLM) | Escale — maior uso de CPU/espera aqui |
| `tools` | Chamadas `@osy.tool` e webhooks | Escale junto com workers de agentes |
| `evaluator` | Pontuação de output | Volume baixo; 1-2 slots suficientes |

A fila `scheduler` deve permanecer em uma máquina (a que executa `osy serve`). `agents`, `tools` e `evaluator` podem ser distribuídas livremente.

### Concorrência local

Aumente slots em uma única máquina via `--concurrency` ou `.env`:

```bash
# .env
OSY_WORKER_CONCURRENCY=8

# ou na inicialização
osy serve --concurrency 8
```

### Escalabilidade horizontal (múltiplas máquinas)

```bash
# ── Máquina A — executa API + scheduler ───────────────────────────
osy serve --no-docker   # ou com Docker

# ── Máquina B — workers de agentes extras ─────────────────────────
# Aponte para o broker/redis compartilhado no .env ou variáveis de ambiente
OSY_RABBITMQ_URL=amqp://user:pass@maquina-a:47764/ \
OSY_REDIS_URL=redis://maquina-a:47763/0 \
osy workers --queues agents,tools --concurrency 8

# ── Máquina C — evaluator dedicado ────────────────────────────────
OSY_RABBITMQ_URL=amqp://user:pass@maquina-a:47764/ \
OSY_REDIS_URL=redis://maquina-a:47763/0 \
osy workers --queues evaluator --concurrency 2
```

Os nós worker precisam ter `osymandias` instalado e acesso ao mesmo `osymandias.toml` (ou aos mesmos módulos `@osy.agent` importáveis). Eles **não** precisam de acesso ao PostgreSQL — o servidor de API é o único processo que fala diretamente com o Postgres.

### Kubernetes / deployments em container

Cada worker Celery é um processo stateless. Um deployment típico:

| Deployment | Comando | Réplicas |
|---|---|---|
| API | `uvicorn osymandias.runtime.main:app` | 1-2 |
| Workers de agentes | `celery -A osymandias.runtime.workers.celery_app worker --queues agents,tools` | N |
| Scheduler | `celery -A osymandias.runtime.workers.celery_app worker --queues scheduler --concurrency 1` | 1 |
| Beat | `celery -A osymandias.runtime.workers.celery_app beat` | 1 |

Todos os containers worker compartilham o mesmo broker RabbitMQ e backend Redis via variáveis de ambiente.

---

## Dependências opcionais

| Extra | Instala |
|---|---|
| `osymandias[langchain]` | `langchain-core`, `langchain` |
| `osymandias[crewai]` | `crewai` |
| `osymandias[llamaindex]` | `llama-index-core` |
| `osymandias[smolagents]` | `smolagents` |
| `osymandias[openai-agents]` | `openai-agents` |
| `osymandias[all]` | Todos acima |

O pacote base `osymandias` não tem dependências de framework — os extras só são necessários se você usar o adaptador correspondente.
