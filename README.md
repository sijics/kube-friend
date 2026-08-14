# ⎈ kubefriend — AI DevOps Assistant

Ask questions about your Kubernetes cluster in plain English.  
kubefriend investigates live cluster data, explains what's wrong, and tells you exactly how to fix it.

```
"Why is my openrag-backend pod failing?"
"Show me all openrag workloads in Processing state"
"Which pods in namespace prod are safe to delete?"
```

---

## What it does

| | |
|---|---|
| 💬 **Chat** | Natural language → live cluster data → root cause + remediation |
| 📊 **Dashboard** | Live pod health table with AI diagnosis, auto-refreshes every 30s |
| ⎈ **Any cluster** | Switch between clusters with one command — works with any `kubectl` context |
| 🤖 **Dual LLM** | OpenAI GPT-4o or IBM watsonx Granite — switch with one command |
| 🔍 **CRD aware** | Understands custom resources: workloads, milvus, presto, opensearch, openrag… |

---

## Prerequisites

| Tool | Version | Install |
|---|---|---|
| Python | 3.12+ | [python.org](https://python.org) |
| Node.js | 18+ | `brew install node` |
| uv | any | `curl -LsSf https://astral.sh/uv/install.sh \| sh` |
| kubectl | any | [kubernetes.io/docs/tasks/tools](https://kubernetes.io/docs/tasks/tools) |

A valid `~/.kube/config` pointing to a running cluster is required.

---

## Installation

```bash
# 1. Clone the repo
git clone https://github.com/sijics/kube-friend.git
cd kube-friend

# 2. Run the one-time install script
chmod +x install.sh && ./install.sh

# 3. Add your API key to .env
nano .env
```

The install script:
- Checks Python 3.12+, Node.js, and uv
- Installs any missing tools via Homebrew (macOS)
- Creates `backend/.venv` and installs all Python dependencies
- Runs `npm install` for the frontend
- Creates `.env` from `.env.example` if it doesn't exist

---

## Configuration

Edit `.env` in the repo root:

```bash
# ── LLM (choose one) ──────────────────────────────────────────────────────────
LLM_PROVIDER=openai          # or: watsonx

# ── OpenAI ────────────────────────────────────────────────────────────────────
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4o          # or: gpt-4o-mini (cheaper, still great)

# ── IBM watsonx (free tier at dataplatform.cloud.ibm.com) ─────────────────────
WATSONX_API_KEY=
WATSONX_PROJECT_ID=
WATSONX_URL=https://us-south.ml.cloud.ibm.com
WATSONX_MODEL_ID=ibm/granite-3-8b-instruct

# ── Kubernetes ────────────────────────────────────────────────────────────────
KUBECONFIG_PATH=~/.kube/config
```

---

## Running

```bash
./kubefriend start       # start backend + frontend, opens browser automatically
./kubefriend stop        # stop everything
./kubefriend restart     # stop then start
./kubefriend status      # show running state, cluster, and LLM
```

Then open **http://localhost:5173**

---

## Switching clusters

kubefriend uses your active `kubectl` context — no extra config needed.

```bash
# See all available contexts
./kubefriend contexts

# Switch to a different cluster (restarts backend automatically)
./kubefriend switch rancher-desktop
./kubefriend switch my-prod-cluster
./kubefriend switch lh-wxd-dev-us-south-db-roks24-oc
```

---

## Switching LLM

```bash
./kubefriend llm openai     # use OpenAI GPT-4o
./kubefriend llm watsonx    # use IBM watsonx Granite
```

Restarts the backend instantly — no rebuild needed.

---

## All commands

```
./kubefriend start                    Start backend + frontend, open browser
./kubefriend stop                     Stop everything
./kubefriend restart                  Stop then start
./kubefriend status                   Show running status + cluster + LLM
./kubefriend switch <context>         Switch kubectl context (restarts backend)
./kubefriend contexts                 List all available kubectl contexts
./kubefriend logs [backend|frontend]  Tail live logs (default: both)
./kubefriend llm [openai|watsonx]     Switch LLM provider (restarts backend)
```

Or use `make`:

```bash
make install
make run
make stop
make status
make switch c=rancher-desktop
make llm p=watsonx
make logs
```

---

## What you can ask

See [docs/capabilities.md](docs/capabilities.md) for the full list with examples.

**Quick examples:**

```
Why is my openrag-backend pod failing?
Show me the logs for pod payments-7d9f4b-xk2p9 in namespace prod
Why is pod demo-pending not scheduling?
Show me all openrag workloads
Which workloads are in Processing state?
What pods in namespace default are safe to delete?
Why is my nginx deployment not rolling out?
```

---

## Architecture

```
Browser (React + Vite)
    │  POST /api/chat  (SSE streaming)
    ▼
FastAPI backend
    │
    ▼
LangGraph ReAct Agent
    │  reasons → calls tools → reasons → final answer
    ├── get_pod_status       Pod phase, container states, restart count
    ├── get_pod_logs         Last N log lines
    ├── get_pod_events       Kubernetes events (Warnings, scheduling)
    ├── get_deployment       Replica counts, rollout status
    ├── get_pvc              PVC bound/pending status
    ├── find_unused_pods     Evicted, completed, idle pods
    └── get_crd_resources    ANY custom resource (workloads, milvus, presto…)
    │
    ▼
Kubernetes Python client → your cluster (via ~/.kube/config)
```

**LLM:** OpenAI GPT-4o (default) or IBM watsonx Granite-3  
**Agent loop:** LangGraph ReAct — the LLM decides which tools to call, reads results, and loops until it has enough data to answer  
**Streaming:** Every agent step (tool call, tool result, token) is streamed to the browser via SSE as it happens

---

## Docker alternative

If you prefer Docker over native:

```bash
cp .env.example .env
# edit .env with your keys
docker compose up --build
```

Note: If your cluster API server is on `localhost` (e.g. `oc login` tunnel or Rancher Desktop),
set `KUBE_SERVER_HOST_OVERRIDE=host.docker.internal` in `.env` so the container can reach it.

---

## Project structure

```
kubefriend/
├── backend/
│   ├── app/
│   │   ├── main.py           FastAPI app + /api/chat SSE + /api/dashboard
│   │   ├── dashboard.py      Pod health scanner with AI diagnosis
│   │   ├── schemas.py        Pydantic request/response models
│   │   ├── agent/
│   │   │   ├── graph.py      LangGraph ReAct loop
│   │   │   ├── state.py      Agent message state
│   │   │   └── prompts.py    System prompt
│   │   ├── llm/
│   │   │   └── factory.py    OpenAI / watsonx factory
│   │   └── tools/
│   │       ├── registry.py   All tools registered here
│   │       ├── k8s_client.py Kubernetes client init
│   │       ├── pod_status.py
│   │       ├── pod_logs.py
│   │       ├── pod_events.py
│   │       ├── deployment.py
│   │       ├── pvc.py
│   │       ├── unused_pods.py
│   │       └── crd_resource.py  Generic CRD tool
│   └── pyproject.toml
├── frontend/
│   └── src/
│       ├── App.tsx            Chat + Dashboard tabs
│       ├── components/
│       │   ├── ChatWindow.tsx
│       │   ├── MessageBubble.tsx
│       │   ├── InputBar.tsx
│       │   ├── ToolCallPanel.tsx
│       │   ├── Dashboard.tsx
│       │   ├── PodTable.tsx
│       │   ├── SummaryBar.tsx
│       │   └── NamespaceSelector.tsx
│       └── hooks/
│           ├── useChat.ts
│           └── useDashboard.ts
├── kubefriend          CLI script
├── install.sh          One-time setup
├── run.sh              Start natively
├── stop.sh             Stop everything
├── Makefile            make shortcuts
├── docker-compose.yml  Docker alternative
└── .env.example        All config keys documented
```

---

## Contributing

1. Fork the repo
2. `./install.sh` to set up
3. `./kubefriend start` to run
4. Add a new tool in `backend/app/tools/` with `@tool` decorator
5. Register it in `backend/app/tools/registry.py`

That's it — the agent picks it up automatically.

---

## Roadmap

- [ ] GitHub tool — link PRs to pod failures
- [ ] ArgoCD tool — sync status and health
- [ ] Helm tool — installed versions, upgrade history
- [ ] Node tool — CPU/memory/disk pressure
- [ ] CRD dashboard tab — workload health alongside pods
- [ ] Multi-cluster dashboard — compare across contexts
