from langchain_core.tools import tool
from app.tools.k8s_client import core_v1


@tool
def get_pod_status(namespace: str, pod_name: str) -> str:
    """
    Get the current status of a Kubernetes pod.

    Use this tool when the user asks why a pod is failing, crashing, pending,
    or not starting. It returns the pod phase, container statuses, restart
    counts, and last termination reason (e.g. OOMKilled, Error, Completed).

    Args:
        namespace: The Kubernetes namespace the pod lives in (e.g. "default", "prod").
        pod_name:  The exact name of the pod (e.g. "openrag-backend-7d9f4b-xk2p9").
                   Also accepts a deployment prefix — will find the first matching pod.
    """
    # WHY this docstring matters:
    # LangChain reads this docstring and sends it to GPT-4o as the tool description.
    # GPT-4o uses it to decide WHEN to call this tool and WHAT arguments to pass.
    # The Args section becomes the argument schema the LLM fills in.

    api = core_v1()

    try:
        # First try exact name match
        pod = api.read_namespaced_pod(name=pod_name, namespace=namespace)
        pods = [pod]
    except Exception:
        # If exact match fails, list all pods and find prefix matches
        # This handles "openrag-backend" matching "openrag-backend-7d9f4b-xk2p9"
        all_pods = api.list_namespaced_pod(namespace=namespace)
        pods = [p for p in all_pods.items if p.metadata.name.startswith(pod_name)]

    if not pods:
        return f"No pod found matching '{pod_name}' in namespace '{namespace}'."

    lines = []
    for pod in pods:
        meta = pod.metadata
        status = pod.status
        spec = pod.spec

        lines.append(f"Pod: {meta.name}")
        lines.append(f"  Namespace : {meta.namespace}")
        lines.append(f"  Phase     : {status.phase}")
        lines.append(f"  Node      : {spec.node_name or 'unscheduled'}")

        # Pod-level conditions (Scheduled, Initialized, Ready, ContainersReady)
        if status.conditions:
            lines.append("  Conditions:")
            for cond in status.conditions:
                # A condition is a named True/False flag with an optional reason/message
                flag = "✓" if cond.status == "True" else "✗"
                lines.append(f"    {flag} {cond.type}: {cond.reason or ''} {cond.message or ''}")

        # Per-container status — this is where crash/OOM info lives
        if status.container_statuses:
            lines.append("  Containers:")
            for cs in status.container_statuses:
                lines.append(f"    - {cs.name}")
                lines.append(f"      Image    : {cs.image}")
                lines.append(f"      Ready    : {cs.ready}")
                lines.append(f"      Restarts : {cs.restart_count}")

                # Current state: Running, Waiting, or Terminated
                if cs.state.running:
                    lines.append(f"      State    : Running since {cs.state.running.started_at}")
                elif cs.state.waiting:
                    lines.append(f"      State    : Waiting — {cs.state.waiting.reason}: {cs.state.waiting.message or ''}")
                elif cs.state.terminated:
                    t = cs.state.terminated
                    lines.append(f"      State    : Terminated — reason={t.reason}, exit_code={t.exit_code}")

                # Last state tells us WHY a container previously died
                # This is critical for diagnosing CrashLoopBackOff
                if cs.last_state.terminated:
                    lt = cs.last_state.terminated
                    lines.append(f"      LastState: {lt.reason} (exit={lt.exit_code}) at {lt.finished_at}")

        lines.append("")  # blank line between pods

    return "\n".join(lines)
