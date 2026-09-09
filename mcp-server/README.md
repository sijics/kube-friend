# kubefriend MCP Server

Exposes all 7 kubefriend Kubernetes tools directly inside **Bob** via the
Model Context Protocol (STDIO transport).

Once registered, Bob can answer questions like:
- *"Why is my payment-service pod crashing in prod?"*
- *"Show me all openrag workloads in Processing state"*
- *"Which pods in namespace staging are safe to delete?"*

No kubefriend UI needed. Uses Bob's own LLM — no separate API key required.

---

## Prerequisites

- Python 3.12+ with `kubernetes` package installed
- A valid `~/.kube/config` pointing at your cluster
- Bob IDE installed

---

## Setup (one time)

### 1. Install the kubernetes dependency

```bash
cd /path/to/kubefriend/mcp-server
pip install kubernetes
# or if using the kubefriend venv:
/path/to/kubefriend/backend/.venv/bin/pip install kubernetes
```

### 2. Register in Bob's MCP settings

Open Bob → Settings → MCP → Add server manually, and paste:

```json
{
  "mcpServers": {
    "kubefriend": {
      "command": "python3",
      "args": ["/absolute/path/to/kubefriend/mcp-server/server.py"],
      "env": {
        "KUBECONFIG_PATH": "/Users/yourname/.kube/config"
      }
    }
  }
}
```

> **Tip:** Use the kubefriend venv Python for zero extra installs:
> ```json
> "command": "/absolute/path/to/kubefriend/backend/.venv/bin/python3"
> ```

### 3. Switch clusters anytime

Just change `KUBECONFIG_PATH` in the env block, or let it use your active
`kubectl` context by leaving it empty (the server reads `~/.kube/config`
and uses whatever context is active).

---

## Available tools

| Tool | What it does |
|---|---|
| `get_pod_status` | Phase, container states, restart count, termination reason |
| `get_pod_logs` | Last N lines of container logs |
| `get_pod_events` | Kubernetes events (scheduling, image pull, backoff) |
| `get_deployment` | Replica counts, rollout status, image versions |
| `get_pvc` | PVC bound/pending/lost status |
| `find_unused_pods` | Evicted, completed, failed, idle pods — cleanup candidates |
| `get_crd_resources` | Any CRD: workloads, OpenSearch, Milvus, Kafka, etc. |

---

## Troubleshooting

- **Server not connecting:** Check the absolute path in `args` is correct.
- **kubeconfig error:** Set `KUBECONFIG_PATH` explicitly, e.g. `/Users/you/.kube/config`.
- **kubernetes module not found:** Run `pip install kubernetes` or point `command` at the kubefriend venv Python.
- **View server logs:** Bob shows MCP server stderr in its output panel.
