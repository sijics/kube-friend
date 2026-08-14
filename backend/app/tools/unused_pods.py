from datetime import datetime, timezone
from langchain_core.tools import tool
from app.tools.k8s_client import core_v1


@tool
def find_unused_pods(
    namespace: str,
    older_than_hours: int = 24,
    max_restarts: int = 0,
    include_completed: bool = True,
    include_evicted: bool = True,
) -> str:
    """
    Find pods that are likely unused, old, or safe to delete.

    Use this tool when the user asks about cleaning up their cluster,
    finding old pods, identifying unused workloads, or freeing up resources.

    Criteria for "unused":
    - Phase is Succeeded or Failed (job pods that finished)
    - Phase is Failed with reason Evicted
    - Pod has been running longer than older_than_hours with 0 restarts
      (may be a forgotten long-running pod)
    - Phase is Unknown (node lost contact)

    Args:
        namespace:         Kubernetes namespace to scan (e.g. "default", "prod").
        older_than_hours:  Flag pods older than this many hours. Default 24.
        max_restarts:      Include running pods with <= this many restarts as
                           "possibly idle". Default 0 (only zero-restart pods).
        include_completed: Include Succeeded/completed pods. Default True.
        include_evicted:   Include Evicted pods. Default True.
    """
    api = core_v1()
    now = datetime.now(timezone.utc)

    try:
        pods = api.list_namespaced_pod(namespace=namespace).items
    except Exception as e:
        return f"Error listing pods in namespace '{namespace}': {e}"

    unused = []

    for pod in pods:
        meta = pod.metadata
        status = pod.status
        phase = status.phase or "Unknown"

        age_hours = 0.0
        if meta.creation_timestamp:
            age_hours = (now - meta.creation_timestamp).total_seconds() / 3600

        reason = ""
        if status.reason:
            reason = status.reason

        # Evicted pods — take up a slot in etcd, serve no purpose
        if include_evicted and reason == "Evicted":
            unused.append({
                "name": meta.name,
                "phase": phase,
                "reason": "Evicted",
                "age_hours": round(age_hours, 1),
                "why": "Pod was evicted by the node (resource pressure). Safe to delete.",
                "cmd": f"kubectl delete pod {meta.name} -n {namespace}",
            })
            continue

        # Completed / Succeeded pods (finished jobs)
        if include_completed and phase == "Succeeded":
            unused.append({
                "name": meta.name,
                "phase": phase,
                "reason": "Completed",
                "age_hours": round(age_hours, 1),
                "why": "Job/pod completed successfully. Safe to delete if logs not needed.",
                "cmd": f"kubectl delete pod {meta.name} -n {namespace}",
            })
            continue

        # Failed pods that are not evicted
        if phase == "Failed":
            unused.append({
                "name": meta.name,
                "phase": phase,
                "reason": reason or "Failed",
                "age_hours": round(age_hours, 1),
                "why": "Pod is in Failed state and not restarting. Safe to delete.",
                "cmd": f"kubectl delete pod {meta.name} -n {namespace}",
            })
            continue

        # Unknown phase — node lost contact
        if phase == "Unknown":
            unused.append({
                "name": meta.name,
                "phase": phase,
                "reason": "Unknown",
                "age_hours": round(age_hours, 1),
                "why": "Node lost contact with this pod. Likely stale.",
                "cmd": f"kubectl delete pod {meta.name} -n {namespace}",
            })
            continue

        # Running pods older than threshold with low/zero restarts
        if phase == "Running" and age_hours >= older_than_hours:
            total_restarts = sum(
                cs.restart_count
                for cs in (status.container_statuses or [])
            )
            if total_restarts <= max_restarts:
                unused.append({
                    "name": meta.name,
                    "phase": phase,
                    "reason": f"Running {round(age_hours, 1)}h, {total_restarts} restarts",
                    "age_hours": round(age_hours, 1),
                    "why": (
                        f"Pod has been running for {round(age_hours, 1)} hours "
                        f"with only {total_restarts} restart(s). "
                        "May be a forgotten or idle workload — verify before deleting."
                    ),
                    "cmd": f"kubectl describe pod {meta.name} -n {namespace}",
                })

    if not unused:
        return (
            f"No unused or stale pods found in namespace '{namespace}' "
            f"matching the criteria (older_than_hours={older_than_hours}, "
            f"include_completed={include_completed}, include_evicted={include_evicted})."
        )

    lines = [f"Found {len(unused)} unused/stale pod(s) in namespace '{namespace}':\n"]
    for p in unused:
        lines.append(f"Pod: {p['name']}")
        lines.append(f"  Status : {p['phase']} ({p['reason']})")
        lines.append(f"  Age    : {p['age_hours']} hours")
        lines.append(f"  Why    : {p['why']}")
        lines.append(f"  Action : {p['cmd']}")
        lines.append("")

    return "\n".join(lines)
