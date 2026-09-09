#!/usr/bin/env python3
"""
kubefriend MCP server — exposes all 7 Kubernetes tools to Bob via STDIO.

Bob spawns this as a child process. Communication is JSON-RPC 2.0 over
stdin/stdout. All logging goes to stderr so it never corrupts the protocol.

Usage (Bob MCP config):
  {
    "mcpServers": {
      "kubefriend": {
        "command": "python3",
        "args": ["/path/to/kubefriend/mcp-server/server.py"],
        "env": { "KUBECONFIG_PATH": "/Users/you/.kube/config" }
      }
    }
  }
"""

import sys
import os
import json
import re
from datetime import datetime, timezone

# ── Kubernetes client setup ───────────────────────────────────────────────────

def _load_k8s():
    """Load kubeconfig once. Returns (core_v1_api, apps_v1_api, custom_objects_api)."""
    from kubernetes import client, config

    try:
        config.load_incluster_config()
    except Exception:
        kubeconfig = os.environ.get("KUBECONFIG_PATH", "")
        if kubeconfig:
            kubeconfig = os.path.expanduser(kubeconfig)
        config.load_kube_config(config_file=kubeconfig or None)

    return client.CoreV1Api(), client.AppsV1Api(), client.CustomObjectsApi()


# ── Tool implementations ──────────────────────────────────────────────────────
# Each function mirrors its backend/app/tools/ counterpart exactly.
# They receive plain Python args and return a plain string.

def _get_pod_status(core_v1, namespace: str, pod_name: str) -> str:
    try:
        pod = core_v1.read_namespaced_pod(name=pod_name, namespace=namespace)
        pods = [pod]
    except Exception:
        all_pods = core_v1.list_namespaced_pod(namespace=namespace)
        pods = [p for p in all_pods.items if p.metadata.name.startswith(pod_name)]

    if not pods:
        return f"No pod found matching '{pod_name}' in namespace '{namespace}'."

    lines = []
    for pod in pods:
        meta, status, spec = pod.metadata, pod.status, pod.spec
        lines += [
            f"Pod: {meta.name}",
            f"  Namespace : {meta.namespace}",
            f"  Phase     : {status.phase}",
            f"  Node      : {spec.node_name or 'unscheduled'}",
        ]
        if status.conditions:
            lines.append("  Conditions:")
            for c in status.conditions:
                flag = "✓" if c.status == "True" else "✗"
                lines.append(f"    {flag} {c.type}: {c.reason or ''} {c.message or ''}")
        if status.container_statuses:
            lines.append("  Containers:")
            for cs in status.container_statuses:
                lines += [
                    f"    - {cs.name}",
                    f"      Image    : {cs.image}",
                    f"      Ready    : {cs.ready}",
                    f"      Restarts : {cs.restart_count}",
                ]
                if cs.state.running:
                    lines.append(f"      State    : Running since {cs.state.running.started_at}")
                elif cs.state.waiting:
                    lines.append(f"      State    : Waiting — {cs.state.waiting.reason}: {cs.state.waiting.message or ''}")
                elif cs.state.terminated:
                    t = cs.state.terminated
                    lines.append(f"      State    : Terminated — reason={t.reason}, exit_code={t.exit_code}")
                if cs.last_state.terminated:
                    lt = cs.last_state.terminated
                    lines.append(f"      LastState: {lt.reason} (exit={lt.exit_code}) at {lt.finished_at}")
        lines.append("")
    return "\n".join(lines)


def _get_pod_logs(core_v1, namespace: str, pod_name: str, container: str = "", tail_lines: int = 100) -> str:
    try:
        core_v1.read_namespaced_pod(name=pod_name, namespace=namespace)
        exact_name = pod_name
    except Exception:
        all_pods = core_v1.list_namespaced_pod(namespace=namespace)
        matches = [p.metadata.name for p in all_pods.items if p.metadata.name.startswith(pod_name)]
        if not matches:
            return f"No pod found matching '{pod_name}' in namespace '{namespace}'."
        exact_name = matches[0]

    try:
        logs = core_v1.read_namespaced_pod_log(
            name=exact_name, namespace=namespace,
            container=container or None, tail_lines=tail_lines, timestamps=True,
        )
        if not logs.strip():
            return (f"No logs found for pod '{exact_name}'. "
                    "Container may have crashed before writing logs.")
        return f"Logs for pod '{exact_name}' (last {tail_lines} lines):\n\n{logs}"
    except Exception as e:
        return f"Could not retrieve logs for '{exact_name}': {e}"


def _get_pod_events(core_v1, namespace: str, pod_name: str = "") -> str:
    all_events = core_v1.list_namespaced_event(namespace=namespace)
    events = all_events.items
    if pod_name:
        events = [e for e in events
                  if e.involved_object.name and e.involved_object.name.startswith(pod_name)]
    if not events:
        target = f"pod '{pod_name}'" if pod_name else f"namespace '{namespace}'"
        return f"No events found for {target}."

    events.sort(key=lambda e: e.last_timestamp or e.event_time or "", reverse=True)
    events = events[:20]

    lines = [f"Events in namespace '{namespace}'" + (f" for pod '{pod_name}'" if pod_name else "") + ":\n"]
    for e in events:
        marker = "⚠" if e.type == "Warning" else "ℹ"
        ts = str(e.last_timestamp or e.event_time or "unknown")
        count = f"(x{e.count})" if e.count and e.count > 1 else ""
        lines.append(
            f"{marker} [{ts}] {count}\n"
            f"   Object : {e.involved_object.kind}/{e.involved_object.name}\n"
            f"   Reason : {e.reason}\n"
            f"   Message: {e.message}\n"
        )
    return "\n".join(lines)


def _get_deployment(apps_v1, namespace: str, deployment_name: str) -> str:
    try:
        d = apps_v1.read_namespaced_deployment(name=deployment_name, namespace=namespace)
        deployments = [d]
    except Exception:
        all_deps = apps_v1.list_namespaced_deployment(namespace=namespace)
        deployments = [d for d in all_deps.items if d.metadata.name.startswith(deployment_name)]

    if not deployments:
        return f"No deployment found matching '{deployment_name}' in namespace '{namespace}'."

    lines = []
    for d in deployments:
        meta, spec, status = d.metadata, d.spec, d.status
        lines += [
            f"Deployment: {meta.name}",
            f"  Namespace : {meta.namespace}",
            f"  Replicas  : desired={spec.replicas}  ready={status.ready_replicas or 0}"
            f"  available={status.available_replicas or 0}  updated={status.updated_replicas or 0}",
        ]
        if spec.strategy:
            lines.append(f"  Strategy  : {spec.strategy.type}")
        lines.append("  Containers:")
        for c in spec.template.spec.containers:
            lines.append(f"    - {c.name}: {c.image}")
            if c.resources:
                req = c.resources.requests or {}
                lim = c.resources.limits or {}
                lines.append(f"      requests: cpu={req.get('cpu','?')} memory={req.get('memory','?')}")
                lines.append(f"      limits:   cpu={lim.get('cpu','?')} memory={lim.get('memory','?')}")
        if status.conditions:
            lines.append("  Conditions:")
            for cond in status.conditions:
                flag = "✓" if cond.status == "True" else "✗"
                lines.append(f"    {flag} {cond.type}: {cond.reason} — {cond.message or ''}")
        lines.append("")
    return "\n".join(lines)


def _get_pvc(core_v1, namespace: str, pvc_name: str = "") -> str:
    if pvc_name:
        try:
            pvc = core_v1.read_namespaced_persistent_volume_claim(name=pvc_name, namespace=namespace)
            pvcs = [pvc]
        except Exception:
            all_pvcs = core_v1.list_namespaced_persistent_volume_claim(namespace=namespace)
            pvcs = [p for p in all_pvcs.items if p.metadata.name.startswith(pvc_name)]
    else:
        pvcs = core_v1.list_namespaced_persistent_volume_claim(namespace=namespace).items

    if not pvcs:
        return f"No PVCs found in namespace '{namespace}'."

    lines = [f"PersistentVolumeClaims in namespace '{namespace}':\n"]
    for pvc in pvcs:
        meta, spec, status = pvc.metadata, pvc.spec, pvc.status
        marker = "✓" if status.phase == "Bound" else "✗"
        capacity = "?"
        if spec.resources and spec.resources.requests:
            capacity = spec.resources.requests.get("storage", "?")
        lines += [
            f"{marker} {meta.name}",
            f"   Phase        : {status.phase}",
            f"   Access Modes : {spec.access_modes}",
            f"   Storage Class: {spec.storage_class_name or 'default'}",
            f"   Capacity     : {capacity}",
            f"   Volume       : {spec.volume_name or 'not bound yet'}",
            "",
        ]
    return "\n".join(lines)


def _find_unused_pods(core_v1, namespace: str, older_than_hours: int = 24,
                      max_restarts: int = 0, include_completed: bool = True,
                      include_evicted: bool = True) -> str:
    try:
        pods = core_v1.list_namespaced_pod(namespace=namespace).items
    except Exception as e:
        return f"Error listing pods: {e}"

    now = datetime.now(timezone.utc)
    unused = []

    for pod in pods:
        meta, status = pod.metadata, pod.status
        phase = status.phase or "Unknown"
        age_hours = 0.0
        if meta.creation_timestamp:
            age_hours = (now - meta.creation_timestamp).total_seconds() / 3600
        reason = status.reason or ""

        if include_evicted and reason == "Evicted":
            unused.append({"name": meta.name, "phase": phase, "reason": "Evicted",
                           "age_hours": round(age_hours, 1),
                           "why": "Evicted by node (resource pressure). Safe to delete.",
                           "cmd": f"kubectl delete pod {meta.name} -n {namespace}"})
            continue
        if include_completed and phase == "Succeeded":
            unused.append({"name": meta.name, "phase": phase, "reason": "Completed",
                           "age_hours": round(age_hours, 1),
                           "why": "Job completed. Safe to delete if logs not needed.",
                           "cmd": f"kubectl delete pod {meta.name} -n {namespace}"})
            continue
        if phase == "Failed":
            unused.append({"name": meta.name, "phase": phase, "reason": reason or "Failed",
                           "age_hours": round(age_hours, 1),
                           "why": "Failed, not restarting. Safe to delete.",
                           "cmd": f"kubectl delete pod {meta.name} -n {namespace}"})
            continue
        if phase == "Unknown":
            unused.append({"name": meta.name, "phase": phase, "reason": "Unknown",
                           "age_hours": round(age_hours, 1),
                           "why": "Node lost contact. Likely stale.",
                           "cmd": f"kubectl delete pod {meta.name} -n {namespace}"})
            continue
        if phase == "Running" and age_hours >= older_than_hours:
            total_restarts = sum(cs.restart_count for cs in (status.container_statuses or []))
            if total_restarts <= max_restarts:
                unused.append({"name": meta.name, "phase": phase,
                               "reason": f"Running {round(age_hours,1)}h, {total_restarts} restarts",
                               "age_hours": round(age_hours, 1),
                               "why": f"Running {round(age_hours,1)}h with {total_restarts} restart(s). Verify before deleting.",
                               "cmd": f"kubectl describe pod {meta.name} -n {namespace}"})

    if not unused:
        return f"No unused/stale pods found in namespace '{namespace}'."

    lines = [f"Found {len(unused)} unused/stale pod(s) in namespace '{namespace}':\n"]
    for p in unused:
        lines += [f"Pod: {p['name']}", f"  Status : {p['phase']} ({p['reason']})",
                  f"  Age    : {p['age_hours']} hours", f"  Why    : {p['why']}",
                  f"  Action : {p['cmd']}", ""]
    return "\n".join(lines)


def _get_crd_resources(custom_api, namespace: str = "", resource_type: str = "workloads",
                       filter_type: str = "", filter_state: str = "", name: str = "") -> str:
    from kubernetes import client as k8s_client

    # Auto-discover group/version for this CRD
    try:
        ext = k8s_client.ApiextensionsV1Api()
        crds = ext.list_custom_resource_definition()
        found = None
        for crd in crds.items:
            names = crd.spec.names
            if (names.plural == resource_type or names.singular == resource_type
                    or names.kind.lower() == resource_type.rstrip("s")):
                group = crd.spec.group
                version = next((v.name for v in crd.spec.versions if v.served),
                               crd.spec.versions[0].name)
                found = (group, version, names.plural)
                break
    except Exception as e:
        return f"Error discovering CRD '{resource_type}': {e}"

    if not found:
        return f"CRD '{resource_type}' not found. Run 'kubectl get crd' to see available types."

    group, version, plural = found
    try:
        if namespace:
            result = custom_api.list_namespaced_custom_object(
                group=group, version=version, namespace=namespace, plural=plural)
        else:
            result = custom_api.list_cluster_custom_object(
                group=group, version=version, plural=plural)
    except Exception as e:
        return f"Error querying {plural}: {e}"

    items = result.get("items", [])
    if not items:
        return f"No {plural} found" + (f" in namespace '{namespace}'" if namespace else "") + "."

    if name:
        items = [i for i in items if i.get("metadata", {}).get("name") == name]
    if filter_type:
        items = [i for i in items
                 if i.get("metadata", {}).get("labels", {}).get("type", "").lower() == filter_type.lower()
                 or i.get("spec", {}).get("type", "").lower() == filter_type.lower()]
    if filter_state:
        items = [i for i in items
                 if i.get("status", {}).get("state", "").lower() == filter_state.lower()]

    if not items:
        return f"No {plural} matched filters (type={filter_type!r}, state={filter_state!r}, name={name!r})."

    lines = [f"{group}/{version} — {plural} ({len(items)} found)\n"]
    for item in items:
        meta = item.get("metadata", {})
        spec = item.get("spec", {})
        status = item.get("status", {})
        labels = meta.get("labels", {})
        lines += [
            f"Name      : {meta.get('name', '?')}",
            f"Namespace : {meta.get('namespace', 'cluster-scoped')}",
            f"Type      : {labels.get('type') or spec.get('type', '?')}",
            f"State     : {status.get('state', 'unknown')}",
            f"Age       : {meta.get('creationTimestamp', '?')}",
        ]
        components = status.get("components", {})
        if components:
            lines.append("Components:")
            for comp_name, comp in components.items():
                if isinstance(comp, dict):
                    lines.append(f"  {comp_name}: {comp.get('state', comp.get('status', '?'))}")
        lines.append("")
    return "\n".join(lines)


# ── MCP server — JSON-RPC 2.0 over STDIO ─────────────────────────────────────

TOOLS = [
    {
        "name": "get_pod_status",
        "description": (
            "Get the current status of a Kubernetes pod: phase, container states, "
            "restart count, last termination reason (OOMKilled, Error, CrashLoopBackOff). "
            "Use this first when any pod question is asked."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "namespace": {"type": "string", "description": "Kubernetes namespace (e.g. 'default', 'prod')"},
                "pod_name":  {"type": "string", "description": "Pod name or prefix (e.g. 'payment-service')"},
            },
            "required": ["namespace", "pod_name"],
        },
    },
    {
        "name": "get_pod_logs",
        "description": (
            "Retrieve recent logs from a Kubernetes pod. "
            "Use after get_pod_status when a pod is in CrashLoopBackOff or Error state."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "namespace":  {"type": "string", "description": "Kubernetes namespace"},
                "pod_name":   {"type": "string", "description": "Pod name or prefix"},
                "container":  {"type": "string", "description": "Container name (optional for single-container pods)"},
                "tail_lines": {"type": "integer", "description": "Number of log lines to fetch (default 100)"},
            },
            "required": ["namespace", "pod_name"],
        },
    },
    {
        "name": "get_pod_events",
        "description": (
            "Retrieve Kubernetes events for a namespace or specific pod. "
            "Use when a pod is Pending or the status reason is unclear."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "namespace": {"type": "string", "description": "Kubernetes namespace"},
                "pod_name":  {"type": "string", "description": "Filter to a specific pod (optional)"},
            },
            "required": ["namespace"],
        },
    },
    {
        "name": "get_deployment",
        "description": (
            "Get Deployment status: replica counts, rollout conditions, image versions, "
            "and resource limits. Use when asked about a deployment or rollout."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "namespace":       {"type": "string", "description": "Kubernetes namespace"},
                "deployment_name": {"type": "string", "description": "Deployment name or prefix"},
            },
            "required": ["namespace", "deployment_name"],
        },
    },
    {
        "name": "get_pvc",
        "description": (
            "Get PersistentVolumeClaim status. "
            "Use when a pod is stuck Pending — it may be waiting for storage to bind."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "namespace": {"type": "string", "description": "Kubernetes namespace"},
                "pvc_name":  {"type": "string", "description": "PVC name or prefix (optional, lists all if empty)"},
            },
            "required": ["namespace"],
        },
    },
    {
        "name": "find_unused_pods",
        "description": (
            "Find pods that are safe to delete: evicted, completed, failed, or old idle pods. "
            "Use for cluster cleanup questions."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "namespace":         {"type": "string",  "description": "Kubernetes namespace"},
                "older_than_hours":  {"type": "integer", "description": "Flag pods older than N hours (default 24)"},
                "max_restarts":      {"type": "integer", "description": "Max restarts for running pods to flag (default 0)"},
                "include_completed": {"type": "boolean", "description": "Include Succeeded pods (default true)"},
                "include_evicted":   {"type": "boolean", "description": "Include Evicted pods (default true)"},
            },
            "required": ["namespace"],
        },
    },
    {
        "name": "get_crd_resources",
        "description": (
            "Query any Kubernetes Custom Resource (CRD) by type. "
            "Use for IBM watsonx workloads, OpenSearch, Milvus, Presto, Kafka, or any CRD. "
            "Auto-discovers the CRD group and version."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "resource_type": {"type": "string", "description": "CRD plural name (e.g. 'workloads', 'kafkas')"},
                "namespace":     {"type": "string", "description": "Namespace (leave empty for all namespaces)"},
                "filter_type":   {"type": "string", "description": "Filter by spec.type label (e.g. 'openrag', 'milvus')"},
                "filter_state":  {"type": "string", "description": "Filter by status.state (e.g. 'Processing', 'OK')"},
                "name":          {"type": "string", "description": "Exact resource name to look up"},
            },
            "required": ["resource_type"],
        },
    },
]


def handle_request(req: dict, core_v1, apps_v1, custom_api) -> dict:
    """Route a JSON-RPC request to the right handler and return a response dict."""
    req_id = req.get("id")
    method = req.get("method", "")
    params = req.get("params", {})

    def ok(result):
        return {"jsonrpc": "2.0", "id": req_id, "result": result}

    def err(code, message):
        return {"jsonrpc": "2.0", "id": req_id, "error": {"code": code, "message": message}}

    if method == "initialize":
        return ok({
            "protocolVersion": "2024-11-05",
            "capabilities": {"tools": {}},
            "serverInfo": {"name": "kubefriend", "version": "1.0.0"},
        })

    if method == "tools/list":
        return ok({"tools": TOOLS})

    if method == "tools/call":
        tool_name = params.get("name", "")
        args = params.get("arguments", {})
        print(f"[kubefriend-mcp] calling {tool_name} args={args}", file=sys.stderr)

        try:
            if tool_name == "get_pod_status":
                text = _get_pod_status(core_v1, args["namespace"], args["pod_name"])
            elif tool_name == "get_pod_logs":
                text = _get_pod_logs(core_v1, args["namespace"], args["pod_name"],
                                     args.get("container", ""), int(args.get("tail_lines", 100)))
            elif tool_name == "get_pod_events":
                text = _get_pod_events(core_v1, args["namespace"], args.get("pod_name", ""))
            elif tool_name == "get_deployment":
                text = _get_deployment(apps_v1, args["namespace"], args["deployment_name"])
            elif tool_name == "get_pvc":
                text = _get_pvc(core_v1, args["namespace"], args.get("pvc_name", ""))
            elif tool_name == "find_unused_pods":
                text = _find_unused_pods(
                    core_v1, args["namespace"],
                    int(args.get("older_than_hours", 24)),
                    int(args.get("max_restarts", 0)),
                    bool(args.get("include_completed", True)),
                    bool(args.get("include_evicted", True)),
                )
            elif tool_name == "get_crd_resources":
                text = _get_crd_resources(
                    custom_api,
                    args.get("namespace", ""),
                    args.get("resource_type", "workloads"),
                    args.get("filter_type", ""),
                    args.get("filter_state", ""),
                    args.get("name", ""),
                )
            else:
                return err(-32601, f"Unknown tool: {tool_name}")

            return ok({"content": [{"type": "text", "text": text}]})

        except Exception as e:
            return ok({"content": [{"type": "text", "text": f"Error: {e}"}], "isError": True})

    if method == "notifications/initialized":
        return None  # notification — no response needed

    if method == "ping":
        return ok({})

    return err(-32601, f"Method not found: {method}")


def main():
    print("[kubefriend-mcp] starting, loading kubeconfig...", file=sys.stderr)
    try:
        core_v1, apps_v1, custom_api = _load_k8s()
        print("[kubefriend-mcp] connected to cluster", file=sys.stderr)
    except Exception as e:
        print(f"[kubefriend-mcp] ERROR loading kubeconfig: {e}", file=sys.stderr)
        sys.exit(1)

    print("[kubefriend-mcp] ready, listening on stdio", file=sys.stderr)

    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
        except json.JSONDecodeError as e:
            resp = {"jsonrpc": "2.0", "id": None,
                    "error": {"code": -32700, "message": f"Parse error: {e}"}}
            print(json.dumps(resp), flush=True)
            continue

        resp = handle_request(req, core_v1, apps_v1, custom_api)
        if resp is not None:  # None = notification, no response
            print(json.dumps(resp), flush=True)


if __name__ == "__main__":
    main()
