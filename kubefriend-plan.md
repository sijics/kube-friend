# kubefriend — DevOps AI Assistant: Implementation Plan

## Top-Level Overview

Build **kubefriend**, a full-stack AI DevOps assistant that lets a user type a natural-language
question (e.g. "Why is my openrag-backend pod failing?") and receive a structured, reasoned
answer backed by live Kubernetes data.

**Scope:**
- React + Vite + TypeScript single-page chat UI (localhost, no auth)
- FastAPI Python backend — chat endpoint, SSE streaming, tool execution
- LangGraph ReAct agent loop — the LLM plans and calls tools iteratively
- Five initial Kubernetes tools: `get_pod_status`, `get_pod_logs`, `get_pod_events`,
  `get_deployment`, `get_pvc`
- Dual LLM backend: OpenAI GPT-4o (primary) / IBM watsonx Granite (secondary) — switched via
  `LLM_PROVIDER` env var
- Everything launched with `docker compose up`
- Namespace handling: if the user omits a namespace, the agent asks for it before proceeding
- Conversation store: in-memory dict (sufficient for v1; no cross-restart persistence needed)

**Non-goals (v1):**
- Authentication / multi-user
- GitHub, ArgoCD, Helm, OpenSearch integrations (future)
- Production Kubernetes deployment of kubefriend itself

**Implementation style:**
Each sub-task must be preceded by a clear educational explanation covering:
- **What** is being built in this sub-task
- **How** it works (the mechanism, the data flow, the pattern used)
- **Why** this approach was chosen over alternatives

This is a learning-first project. Explanations are a first-class deliverable, not optional.

---

## Project Directory Structure

```
kubefriend/
├── backend/
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py               # FastAPI app + /api/chat SSE endpoint
│   │   ├── agent/
│   │   │   ├── __init__.py
│   │   │   ├── graph.py          # LangGraph ReAct graph definition
│   │   │   ├── state.py          # AgentState TypedDict
│   │   │   └── prompts.py        # System prompt template
│   │   ├── llm/
│   │   │   ├── __init__.py
│   │   │   └── factory.py        # Returns LLM instance from env config
│   │   ├── tools/
│   │   │   ├── __init__.py
│   │   │   ├── registry.py       # Aggregates all tools into a list
│   │   │   ├── k8s_client.py     # Shared kubernetes Python client init
│   │   │   ├── pod_status.py     # get_pod_status tool
│   │   │   ├── pod_logs.py       # get_pod_logs tool
│   │   │   ├── pod_events.py     # get_pod_events tool
│   │   │   ├── deployment.py     # get_deployment tool
│   │   │   └── pvc.py            # get_pvc tool
│   │   └── schemas.py            # Pydantic request/response models
│   ├── pyproject.toml
│   ├── uv.lock
│   ├── Dockerfile
│   └── .env.example
├── frontend/
│   ├── src/
│   │   ├── main.tsx
│   │   ├── App.tsx
│   │   ├── components/
│   │   │   ├── ChatWindow.tsx    # Scrollable message list
│   │   │   ├── MessageBubble.tsx # User / assistant message rendering
│   │   │   ├── ToolCallPanel.tsx # Collapsible tool-call trace sidebar
│   │   │   └── InputBar.tsx      # Text input + send button
│   │   ├── hooks/
│   │   │   └── useChat.ts        # SSE streaming hook
│   │   ├── types.ts              # Shared TS types (Message, ToolCall, etc.)
│   │   └── api.ts                # fetch wrapper for /api/chat
│   ├── index.html
│   ├── vite.config.ts
│   ├── tsconfig.json
│   ├── package.json
│   └── Dockerfile
├── docker-compose.yml
├── .env.example                  # Root-level env template
└── README.md
```

---

## Sub-Tasks

---

### Sub-Task 1 — Project Scaffolding

**Intent:**
Establish the full directory skeleton, configuration files, Docker setup, and dependency
manifests so every subsequent sub-task has a stable, runnable foundation.

**Expected Outcomes:**
- `docker compose up` starts both services (even if backend returns 404 and frontend shows blank)
- `uv sync` inside `backend/` resolves all dependencies without errors
- `npm install` inside `frontend/` resolves all dependencies without errors
- `.env.example` documents every required environment variable
- `README.md` has quickstart instructions

**Todo List:**
1. Create root `docker-compose.yml` wiring `backend` (port 8000) and `frontend` (port 5173)
   services, with a shared `.env` file and `kubeconfig` volume mount for the backend
2. Create `backend/pyproject.toml` with `uv` tooling; declare dependencies:
   `fastapi`, `uvicorn[standard]`, `langchain`, `langgraph`, `langchain-openai`,
   `ibm-watsonx-ai`, `langchain-ibm`, `kubernetes`, `python-dotenv`, `pydantic`, `sse-starlette`
3. Create `backend/Dockerfile`: Python 3.12 slim, `uv sync --frozen`, `uvicorn` entrypoint
4. Create `backend/.env.example` with keys: `LLM_PROVIDER`, `OPENAI_API_KEY`, `OPENAI_MODEL`,
   `WATSONX_API_KEY`, `WATSONX_PROJECT_ID`, `WATSONX_URL`, `WATSONX_MODEL_ID`,
   `KUBECONFIG_PATH`, `DEFAULT_NAMESPACE`
5. Create `frontend/package.json` with Vite + React + TypeScript + `@types/react`
6. Create `frontend/vite.config.ts` with a dev proxy: `/api` → `http://localhost:8000`
7. Create `frontend/Dockerfile`: `node:20-alpine`, `npm ci`, `npm run build`,
   served by `nginx:alpine`
8. Create stub `backend/app/main.py` (FastAPI app, `/healthz` route only)
9. Create stub `frontend/src/main.tsx` and `App.tsx` (renders "kubefriend loading…")
10. Update `README.md` with prerequisites and `docker compose up` quickstart

**Relevant Context:**
- No existing code — all files are new
- `kubeconfig` must be mounted into the backend container so the kubernetes Python client can
  authenticate; default path `/root/.kube/config` inside container

**Status:** `[x] done`

---

### Sub-Task 2 — LLM Factory

**Intent:**
Implement the `llm/factory.py` module that reads `LLM_PROVIDER` and returns the correct
LangChain chat model instance, isolating all LLM configuration in one place.

**Expected Outcomes:**
- `get_llm()` returns a `langchain_openai.ChatOpenAI` when `LLM_PROVIDER=openai`
- `get_llm()` returns a `langchain_ibm.WatsonxLLM` (wrapped as a chat model) when
  `LLM_PROVIDER=watsonx`
- Raises a clear `ValueError` for unknown providers
- No LLM credentials appear anywhere outside this module and the `.env` file

**Todo List:**
1. Create `backend/app/llm/__init__.py`
2. Implement `backend/app/llm/factory.py`:
   - Read `LLM_PROVIDER` (default `"openai"`)
   - For `openai`: instantiate `ChatOpenAI(model=OPENAI_MODEL, streaming=True)`
   - For `watsonx`: instantiate `WatsonxLLM` / `ChatWatsonx` with URL, project ID, model ID,
     and API key from env; wrap in streaming-compatible adapter
   - Expose a single `get_llm()` function

**Relevant Context:**
- `langchain-openai` package for OpenAI
- `langchain-ibm` package for watsonx (check `ChatWatsonx` availability; fall back to
  `WatsonxLLM` + `LLMChain` adapter if chat interface is not yet available)
- Streaming must work through LangChain's standard `astream_events` interface

**Status:** `[x] done`

---

### Sub-Task 3 — Kubernetes Tool Implementations

**Intent:**
Build the five discrete Kubernetes tools that the LLM agent can call. Each tool is a
LangChain `@tool`-decorated function that takes structured input, calls the Kubernetes Python
client, and returns a formatted string summary.

**Expected Outcomes:**
- Each tool is independently importable and callable
- Tools handle missing resources gracefully (return a "not found" string, not an exception)
- `registry.py` exports a single `TOOLS: list` used by the agent
- Tools work against the cluster referenced by `KUBECONFIG_PATH` env var (or in-cluster
  config when running inside Kubernetes)

**Todo List:**
1. Implement `backend/app/tools/k8s_client.py`:
   - Tries `load_incluster_config()` first; falls back to `load_kube_config(KUBECONFIG_PATH)`
   - Exposes `core_v1()` and `apps_v1()` helper functions returning API client instances
2. Implement `get_pod_status` in `pod_status.py`:
   - Input: `namespace`, `pod_name` (or prefix search)
   - Returns: phase, conditions, container statuses, restart counts, image names
3. Implement `get_pod_logs` in `pod_logs.py`:
   - Input: `namespace`, `pod_name`, optional `container`, optional `tail_lines` (default 100)
   - Returns: last N lines of logs; handles multi-container pods
4. Implement `get_pod_events` in `pod_events.py`:
   - Input: `namespace`, optional `pod_name` filter
   - Returns: recent Warning/Normal events sorted by last timestamp
5. Implement `get_deployment` in `deployment.py`:
   - Input: `namespace`, `deployment_name`
   - Returns: desired/ready/available replicas, image versions, rollout conditions, strategy
6. Implement `get_pvc` in `pvc.py`:
   - Input: `namespace`, optional `pvc_name`
   - Returns: PVC names, access modes, capacity, bound status, storage class
7. Implement `backend/app/tools/registry.py`:
   - Imports all five tools and exports `TOOLS = [...]`

**Relevant Context:**
- Use `kubernetes` Python package (`kubernetes.client`, `kubernetes.config`)
- Each tool decorated with `@tool` from `langchain_core.tools`
- Tool docstrings become the tool description the LLM sees — write them clearly
- Output must be a plain string (the LLM reads it as a tool result)

**Status:** `[x] done`

---

### Sub-Task 4 — LangGraph ReAct Agent

**Intent:**
Wire the LLM and tools into a LangGraph ReAct loop: the agent reasons, decides which tool
to call, receives the result, reasons again, and eventually produces a final answer with
root-cause analysis and remediation suggestions.

**Expected Outcomes:**
- `graph.py` exports a compiled `StateGraph` that accepts a user message and streams
  intermediate steps (tool calls + tool results) and the final answer
- Agent correctly identifies Kubernetes resources from natural-language questions
- Agent stops looping when it has enough information to answer (no infinite loops)

**Todo List:**
1. Define `backend/app/agent/state.py`:
   - `AgentState` TypedDict with `messages: Annotated[list, add_messages]`
2. Write `backend/app/agent/prompts.py`:
   - System prompt instructing the agent: it is a Kubernetes expert, should identify the
     resource from the question, call tools methodically, explain root cause clearly, and
     always suggest at least one remediation step
   - If the user's question does not include a namespace, the agent must ask the user to
     provide the namespace before calling any tool — do not assume a default namespace
3. Implement `backend/app/agent/graph.py`:
   - Create a `StateGraph(AgentState)` with two nodes: `agent` (LLM call) and `tools`
     (ToolNode executing the called tools)
   - `agent` node: binds `get_llm()` with `TOOLS` via `.bind_tools()`; runs LLM with current
     messages
   - `tools` node: LangGraph `ToolNode(TOOLS)`
   - Conditional edge from `agent`: if last message has tool calls → go to `tools`;
     otherwise → `END`
   - Unconditional edge from `tools` → `agent`
   - Entry point: `agent`
   - Compile and export as `agent_graph`

**Relevant Context:**
- Use `langgraph.graph.StateGraph`, `langgraph.prebuilt.ToolNode`,
  `langgraph.graph.END`, `langgraph.graph.START`
- Use `langchain_core.messages.add_messages` for the reducer
- This is the standard LangGraph ReAct pattern — no custom loop logic needed

**Status:** `[x] done`

---

### Sub-Task 5 — FastAPI Backend & SSE Streaming

**Intent:**
Expose the agent over HTTP. The `/api/chat` endpoint accepts a user message and streams
back Server-Sent Events: one event per agent step (tool call, tool result, token, final
answer). This lets the frontend render progressively.

**Expected Outcomes:**
- `POST /api/chat` with `{"message": "...", "conversation_id": "..."}` streams SSE events
- Event types: `token` (LLM token), `tool_call` (tool name + input), `tool_result`
  (tool output), `done` (signals stream end), `error`
- `GET /healthz` returns `{"status": "ok"}`
- CORS configured for `http://localhost:5173`

**Todo List:**
1. Define `backend/app/schemas.py`:
   - `ChatRequest`: `message: str`, `conversation_id: str`
   - `SSEEvent`: `type: str`, `data: Any`
2. Implement `backend/app/main.py`:
   - Create `FastAPI` app with CORS middleware (allow `http://localhost:5173`)
   - `GET /healthz`
   - `POST /api/chat` as an async SSE endpoint using `sse_starlette.sse.EventSourceResponse`
   - Inside the streaming generator: invoke `agent_graph.astream_events(...)` with
     `version="v2"`; map LangGraph event types to SSE event types and yield them as
     JSON-encoded strings
   - Maintain a simple in-memory conversation store: `dict[conversation_id → message_history]`
     so multi-turn context is preserved within a session

**Relevant Context:**
- `sse_starlette` package for SSE in FastAPI
- LangGraph `astream_events` emits events with `event`, `name`, `data` keys
- Map: `on_chat_model_stream` → `token`; `on_tool_start` → `tool_call`;
  `on_tool_end` → `tool_result`; graph completion → `done`

**Status:** `[x] done`

---

### Sub-Task 6 — React Frontend

**Intent:**
Build the minimal chat UI: a message list, a collapsible tool-call trace panel, and a text
input that streams the assistant's response in real time using the SSE endpoint.

**Expected Outcomes:**
- User types a question and presses Enter / Send
- Assistant response streams token by token in the chat window
- A collapsible sidebar/panel shows each tool call and its result
- Tool-call panel updates live as tools are invoked during the agent loop
- UI is clean and functional (no design polish required for v1)

**Todo List:**
1. Define `frontend/src/types.ts`:
   - `Message`: `id`, `role: "user" | "assistant"`, `content`, `toolCalls?: ToolCall[]`
   - `ToolCall`: `name`, `input`, `result`, `status: "pending" | "done"`
2. Implement `frontend/src/api.ts`:
   - `streamChat(message, conversationId, callbacks)` — opens a `fetch` to `POST /api/chat`,
     reads the SSE stream via `ReadableStream`, calls `onToken`, `onToolCall`, `onToolResult`,
     `onDone`, `onError` callbacks
3. Implement `frontend/src/hooks/useChat.ts`:
   - Manages `messages` state and `isStreaming` flag
   - Calls `streamChat`; appends tokens to the current assistant message; populates toolCalls
4. Implement `frontend/src/components/ChatWindow.tsx`:
   - Renders `MessageBubble` for each message; auto-scrolls to bottom
5. Implement `frontend/src/components/MessageBubble.tsx`:
   - User bubbles (right-aligned); assistant bubbles (left-aligned, markdown-rendered)
6. Implement `frontend/src/components/ToolCallPanel.tsx`:
   - Collapsible panel listing tool calls; each item shows name, JSON input, result text
7. Implement `frontend/src/components/InputBar.tsx`:
   - Controlled text input; disabled while `isStreaming`; submits on Enter or button click
8. Assemble in `frontend/src/App.tsx`:
   - Layout: chat window (main area) + tool-call panel (right sidebar, collapsible)
   - Wire `useChat` hook to `ChatWindow` and `InputBar`

**Relevant Context:**
- Vite dev proxy (`/api` → backend) means no hardcoded backend URL in frontend code
- Use `react-markdown` for rendering assistant message content
- `conversation_id` can be a UUID generated once per page load (stored in component state)

**Status:** `[x] done`

---

### Sub-Task 7 — Integration & Docker Compose

**Intent:**
Verify the full stack works end-to-end: UI → backend → agent → tools → Kubernetes cluster,
with everything launchable via a single `docker compose up`.

**Expected Outcomes:**
- `docker compose up` starts both containers with no errors
- Navigating to `http://localhost:5173` shows the chat UI
- Asking "What is the status of pod X in namespace Y?" returns a real answer from the cluster
- Tool calls are visible in the tool-call panel
- `.env.example` at root level is the single source of truth for configuration

**Todo List:**
1. Finalize `docker-compose.yml`:
   - `backend` service: build `./backend`, env_file `.env`, mount
     `~/.kube:/root/.kube:ro`, port `8000:8000`
   - `frontend` service: build `./frontend`, port `5173:80` (nginx in prod mode),
     depends_on `backend`
2. Create root `.env.example` mirroring `backend/.env.example`
3. Confirm `vite.config.ts` proxy is only used in dev mode; in production the nginx config
   must proxy `/api` to the backend service name (`http://backend:8000`)
4. Add `nginx.conf` to `frontend/` for the production container:
   - Serve static files from `/usr/share/nginx/html`
   - Proxy `/api/` to `http://backend:8000/api/`
5. Smoke-test checklist (manual):
   - `docker compose up --build` completes
   - `curl http://localhost:8000/healthz` returns `{"status":"ok"}`
   - UI loads at `http://localhost:5173`
   - A pod-status question returns a streamed answer with tool calls visible

**Relevant Context:**
- kubeconfig mount `~/.kube:/root/.kube:ro` gives the backend container cluster access
- `DEFAULT_NAMESPACE` env var allows the agent to default to a namespace when none is
  mentioned in the question

**Status:** `[x] done`

---

## Tech Stack Rationale

| Choice | Rationale |
|---|---|
| FastAPI | Async-native, SSE support via `sse_starlette`, excellent Pydantic integration |
| LangGraph ReAct | Explicit graph = debuggable agent loop; built-in tool call/result cycle; streaming-first |
| `kubernetes` Python client | Official client, supports both in-cluster and kubeconfig auth |
| OpenAI GPT-4o | Best tool-calling reliability; native function-calling in LangChain |
| IBM watsonx Granite | Open, on-prem option; `langchain-ibm` provides LangChain integration |
| Vite + React + TypeScript | Fast dev cycle; TypeScript catches SSE event shape errors at compile time |
| `uv` + `pyproject.toml` | Fast dependency resolution; lock file for reproducible builds |
| Docker Compose | Single-command local stack; mirrors a production multi-service deployment |

---

## Configuration / Secrets Approach

- All secrets live in a single `.env` file (git-ignored) at the repo root
- `.env.example` committed to git documents every key with placeholder values
- Backend reads env vars via `python-dotenv` at startup; no secrets in code
- `LLM_PROVIDER=openai|watsonx` controls which LLM factory branch is taken
- Kubernetes auth: kubeconfig mounted as read-only volume; in-cluster config auto-detected
  when deployed inside a pod (future)

---

## Future Expansion Hooks

The tool registry (`tools/registry.py`) is the single place to add new tools. Future tool
modules (GitHub, ArgoCD, Helm, OpenSearch, IBM Cloud) follow the same `@tool` pattern and are
appended to `TOOLS`. No agent or API code changes needed.
