# kubefriend — Capabilities

Full reference of what kubefriend can do, with example questions for each capability.

---

## 1. Pod Diagnosis

kubefriend investigates failing, crashing, or stuck pods using live cluster data.

**What it collects:**
- Pod phase (Running, Pending, Failed, Unknown)
- Container states (Running, Waiting, Terminated)
- Restart count and last termination reason (OOMKilled, Error, CrashLoopBackOff)
- Pod conditions (Scheduled, Initialized, Ready, ContainersReady)
- Recent logs (last 100 lines by default)
- Kubernetes events (Warnings, scheduling failures, image pull errors)

**Example questions:**
```
Why is my openrag-backend pod failing?
Why is pod payments-7d9f4b-xk2p9 in namespace prod crashing?
Why does my pod keep restarting?
What does OOMKilled mean for pod frontend-abc123?
Why is pod demo-crashloop in CrashLoopBackOff?
Show me the last 50 lines of logs for pod nginx-xyz in namespace default
```

---

## 2. Pending Pod Analysis

Diagnoses pods stuck in Pending state — scheduling failures, resource constraints, missing PVCs.

**What it checks:**
- Node scheduling events (Insufficient CPU/memory, taints/tolerations, node selectors)
- PVC bound status (pod waiting for storage)
- Image pull errors
- Resource quota exhaustion

**Example questions:**
```
Why is pod demo-pending not starting?
Why is my pod stuck in Pending?
Why can't my pod be scheduled?
Is there a storage issue with pod postgres-0 in namespace data?
```

---

## 3. Deployment Status

Checks rollout health, replica counts, and image versions for Deployments.

**What it returns:**
- Desired / ready / available replica counts
- Current and previous image versions
- Rollout conditions (Progressing, Available, ReplicaFailure)
- Deployment strategy (RollingUpdate, Recreate)

**Example questions:**
```
What is the status of the frontend deployment in namespace prod?
Why is my nginx deployment not rolling out?
How many replicas does the payments deployment have?
Is the openrag-be deployment healthy?
What image version is running in the api deployment?
```

---

## 4. PVC / Storage

Checks PersistentVolumeClaim status — whether storage is bound, pending, or lost.

**What it returns:**
- PVC names, access modes, capacity
- Bound / Pending / Lost status
- Storage class
- Associated PV

**Example questions:**
```
Why is my database pod stuck waiting for storage?
Is the postgres PVC in namespace data bound?
Show me all PVCs in namespace prod
What storage class is used by pvc-data-postgres-0?
```

---

## 5. Custom Resources (CRDs)

Queries **any** Custom Resource Definition in the cluster — not just built-in Kubernetes resources.
The API group and version are auto-discovered from the cluster.

**Supported filter options:**
- `filter_type` — filter by resource type label (e.g. `openrag`, `milvus`, `presto`)
- `filter_state` — filter by status state (e.g. `Processing`, `OK`, `Failed`)
- `name` — look up a specific resource by name
- `namespace` — scope to a namespace, or leave empty for all namespaces

**Example questions:**
```
Show me all openrag workloads
List all workloads in Processing state
Why is workload 12022bd7-4e09-4852-b5a5-4f94264065c2 in Processing state?
Show me all milvus workloads
List presto workloads across all namespaces
Are there any opensearch workloads not in OK state?
Show me the components of workload abc123
```

**Works with any CRD**, for example:
```
Show me all kafkas in namespace kafka
List prometheuses in monitoring namespace
Show me all ingressroutes
```

---

## 6. Unused Pod Cleanup

Identifies pods that are safe to delete — evicted, completed, failed, or idle running pods.

**Criteria:**
- `Evicted` pods — resource pressure evictions, safe to delete immediately
- `Succeeded` / `Completed` pods — finished jobs, safe to delete
- `Failed` pods — not restarting, safe to delete
- `Unknown` phase — node lost contact, likely stale
- Long-running pods with zero restarts — possibly forgotten/idle (verify before deleting)

**Configurable thresholds:**
- `older_than_hours` — flag pods older than N hours (default: 24)
- `max_restarts` — include running pods with ≤ N restarts (default: 0)
- `include_completed` — include Succeeded pods (default: true)
- `include_evicted` — include Evicted pods (default: true)

**Example questions:**
```
What pods in namespace default are safe to delete?
Find all evicted pods in namespace prod
Show me completed job pods in namespace batch
Which pods in kubefriend-test are unused?
Find pods older than 7 days with no restarts in namespace staging
Clean up suggestions for namespace prod
```

---

## 7. Live Dashboard

The **📊 Dashboard** tab shows a live table of all pods in a namespace with:

| Column | What it shows |
|---|---|
| Pod | Pod name |
| Status | CrashLoopBackOff / Running / Pending / etc. with colour badge |
| Restarts | Total restart count |
| Age (h) | How long the pod has been running |
| Node | Which node it's scheduled on |
| AI Diagnosis | One-sentence root cause (pre-computed for unhealthy pods) |
| Suggestion | Concrete fix with kubectl command |
| Ask AI | Switches to Chat tab with question pre-filled |

**Summary bar** at the top shows: Total / Running / Warning / Critical counts.

**Namespace selector** — switch between any namespace in the cluster.

**Auto-refresh** — polls `/api/dashboard` every 30 seconds automatically.

---

## 8. Multi-cluster Support

kubefriend uses your active `kubectl` context — the same credentials `kubectl` uses.

```bash
# See all contexts
./kubefriend contexts

# Switch to any context — backend restarts automatically
./kubefriend switch rancher-desktop
./kubefriend switch my-prod-roks-cluster
./kubefriend switch arn:aws:eks:us-east-1:123:cluster/my-eks
```

Works with:
- IBM Cloud ROKS (OpenShift)
- AWS EKS
- Rancher Desktop (local)
- Any cluster in `~/.kube/config`

---

## 9. Dual LLM Support

Switch the AI brain with one command:

```bash
./kubefriend llm openai     # OpenAI GPT-4o (default)
./kubefriend llm watsonx    # IBM watsonx Granite-3
```

| | OpenAI GPT-4o | IBM watsonx Granite-3 |
|---|---|---|
| Model | `gpt-4o` or `gpt-4o-mini` | `ibm/granite-3-8b-instruct` |
| Cost | Pay-per-token (~$0.01/question) | IBM Cloud credits (free tier available) |
| Tool calling | ✅ Excellent | ✅ Supported |
| Free tier | ❌ | ✅ at dataplatform.cloud.ibm.com |

To use watsonx:
1. Create a project at [dataplatform.cloud.ibm.com](https://dataplatform.cloud.ibm.com)
2. Associate a **Watson Machine Learning** service instance with the project
3. Get your Project ID (from the project's Manage tab) and IBM Cloud API key (from [cloud.ibm.com/iam/apikeys](https://cloud.ibm.com/iam/apikeys))
4. Set credentials in `.env` and run `./kubefriend llm watsonx`

---

## How the agent reasons

kubefriend uses a **LangGraph ReAct loop**:

```
Your question
    ↓
Agent reads question + system prompt
    ↓
Decides which tool to call first (e.g. get_pod_status)
    ↓
Tool calls Kubernetes API → returns data
    ↓
Agent reads result, decides next tool (e.g. get_pod_logs)
    ↓
... repeats until it has enough data ...
    ↓
Writes final answer:
  • Observation  — what the tools found
  • Root Cause   — why this is happening
  • Remediation  — exact steps + kubectl commands to fix it
  • Prevention   — how to avoid it in future
```

Every tool call and its result is visible in the **Tool Call Panel** (right sidebar in the Chat tab), so you can see exactly what the agent investigated.

---

## Extending kubefriend

Adding a new capability is three steps:

1. Create `backend/app/tools/my_tool.py` with a `@tool`-decorated function
2. Add it to `TOOLS` in `backend/app/tools/registry.py`
3. Restart the backend — the agent picks it up automatically

The tool's **docstring** is what the LLM reads to decide when to call it — write it clearly.

Planned future tools: GitHub, ArgoCD, Helm, Node pressure, IBM Cloud APIs.
