"""
dashboard.py — scans all pods in a namespace and generates AI diagnosis
for any pod that is not healthy.

WHY a separate module and not just a tool?
------------------------------------------
The dashboard endpoint needs structured JSON (a list of DashboardPod objects)
not a plain string. Tools return strings for the LLM to read. The dashboard
is consumed by the React UI directly — it needs typed data it can render.

So: tools are for the agent, dashboard.py is for the UI.
"""

import asyncio
from datetime import datetime, timezone
from typing import Optional

from langchain_core.messages import HumanMessage, SystemMessage

from app.tools.k8s_client import core_v1
from app.llm.factory import get_llm
from app.schemas import DashboardPod, DashboardSummary, DashboardResponse


# Statuses we consider unhealthy and worth diagnosing
_UNHEALTHY_PHASES = {"Pending", "Failed", "Unknown"}
_UNHEALTHY_REASONS = {"CrashLoopBackOff", "OOMKilled", "Error", "Evicted",
                      "ImagePullBackOff", "ErrImagePull", "CreateContainerConfigError"}


def _pod_display_status(pod) -> str:
    """
    Derive a human-readable status string from a pod object.
    Mirrors what `kubectl get pods` shows in the STATUS column.
    """
    phase = (pod.status.phase or "Unknown")

    # Check container-level waiting reason first — more informative than phase
    for cs in (pod.status.container_statuses or []):
        if cs.state and cs.state.waiting and cs.state.waiting.reason:
            return cs.state.waiting.reason

    if pod.status.reason:
        return pod.status.reason

    return phase


def _is_unhealthy(pod) -> bool:
    status = _pod_display_status(pod)
    phase = pod.status.phase or "Unknown"
    if phase in _UNHEALTHY_PHASES:
        return True
    if status in _UNHEALTHY_REASONS:
        return True
    # Running but containers not ready
    for cs in (pod.status.container_statuses or []):
        if not cs.ready:
            if cs.state and cs.state.waiting:
                return True
    return False


def _pod_summary_text(pod) -> str:
    """
    Build a compact text summary of a pod for the LLM to diagnose.
    Kept short — we only need enough for a one-line diagnosis.
    """
    meta = pod.metadata
    status = pod.status
    lines = [
        f"Pod: {meta.name}  namespace: {meta.namespace}  phase: {status.phase}",
    ]
    for cs in (status.container_statuses or []):
        state_str = ""
        if cs.state.waiting:
            state_str = f"Waiting/{cs.state.waiting.reason}: {cs.state.waiting.message or ''}"
        elif cs.state.terminated:
            state_str = f"Terminated reason={cs.state.terminated.reason} exit={cs.state.terminated.exit_code}"
        elif cs.state.running:
            state_str = "Running"
        lines.append(f"  container={cs.name} ready={cs.ready} restarts={cs.restart_count} state={state_str}")
        if cs.last_state and cs.last_state.terminated:
            lt = cs.last_state.terminated
            lines.append(f"  lastState={lt.reason} exit={lt.exit_code}")
    if status.conditions:
        for c in status.conditions:
            if c.status != "True":
                lines.append(f"  condition {c.type}=False reason={c.reason} msg={c.message or ''}")
    return "\n".join(lines)


_DIAGNOSIS_SYSTEM = """You are a Kubernetes expert. Given a pod status summary,
respond with exactly two lines:
DIAGNOSIS: <one sentence root cause>
SUGGESTION: <one concrete fix, include kubectl command if applicable>
Nothing else."""


async def _diagnose_pod(pod) -> tuple[str, str]:
    """
    Ask the LLM for a one-line diagnosis and suggestion for an unhealthy pod.
    Returns (diagnosis, suggestion).
    """
    summary = _pod_summary_text(pod)
    llm = get_llm()
    messages = [
        SystemMessage(content=_DIAGNOSIS_SYSTEM),
        HumanMessage(content=summary),
    ]
    try:
        response = await llm.ainvoke(messages)
        text = response.content or ""
        diagnosis = ""
        suggestion = ""
        for line in text.splitlines():
            if line.startswith("DIAGNOSIS:"):
                diagnosis = line[len("DIAGNOSIS:"):].strip()
            elif line.startswith("SUGGESTION:"):
                suggestion = line[len("SUGGESTION:"):].strip()
        return diagnosis or "Unable to determine root cause.", suggestion or "Inspect pod logs and events."
    except Exception as e:
        return f"Diagnosis unavailable: {e}", "Check pod logs manually."


async def build_dashboard(namespace: str) -> DashboardResponse:
    """
    Scan all pods in the given namespace, classify them, and generate
    AI diagnosis for unhealthy ones. Returns a DashboardResponse.
    """
    api = core_v1()
    now = datetime.now(timezone.utc)

    empty_summary = DashboardSummary(total=0, running=0, warning=0, critical=0)

    try:
        pod_list = api.list_namespaced_pod(namespace=namespace).items
    except Exception as e:
        return DashboardResponse(error=str(e), pods=[], summary=empty_summary, namespaces=[])

    # Fetch all namespaces for the selector dropdown
    try:
        ns_list = [ns.metadata.name for ns in api.list_namespace().items]
    except Exception:
        ns_list = [namespace]

    # Diagnose all unhealthy pods concurrently
    unhealthy_pods = [p for p in pod_list if _is_unhealthy(p)]
    diagnoses: dict[str, tuple[str, str]] = {}

    if unhealthy_pods:
        tasks = [_diagnose_pod(p) for p in unhealthy_pods]
        results = await asyncio.gather(*tasks)
        for pod, result in zip(unhealthy_pods, results):
            diagnoses[pod.metadata.name] = result

    pods_out: list[DashboardPod] = []
    running = warning = critical = 0

    for pod in pod_list:
        meta = pod.metadata
        status = pod.status
        display_status = _pod_display_status(pod)
        phase = status.phase or "Unknown"

        age_hours: Optional[float] = None
        if meta.creation_timestamp:
            age_hours = round((now - meta.creation_timestamp).total_seconds() / 3600, 1)

        total_restarts = sum(
            cs.restart_count for cs in (status.container_statuses or [])
        )

        # Severity classification
        if not _is_unhealthy(pod) and phase == "Running":
            severity = "healthy"
            running += 1
        elif display_status in {"CrashLoopBackOff", "OOMKilled", "Error",
                                 "ImagePullBackOff", "ErrImagePull", "Evicted"} \
                or phase == "Failed":
            severity = "critical"
            critical += 1
        else:
            severity = "warning"
            warning += 1

        diagnosis, suggestion = diagnoses.get(meta.name, (None, None))

        pods_out.append(DashboardPod(
            name=meta.name,
            namespace=meta.namespace,
            status=display_status,
            phase=phase,
            severity=severity,
            restarts=total_restarts,
            age_hours=age_hours,
            node=(pod.spec.node_name or "unscheduled"),
            diagnosis=diagnosis,
            suggestion=suggestion,
        ))

    # Sort: critical first, then warning, then healthy
    _order = {"critical": 0, "warning": 1, "healthy": 2}
    pods_out.sort(key=lambda p: _order.get(p.severity, 3))

    return DashboardResponse(
        pods=pods_out,
        summary=DashboardSummary(
            total=len(pods_out),
            running=running,
            warning=warning,
            critical=critical,
        ),
        namespaces=ns_list,
    )
