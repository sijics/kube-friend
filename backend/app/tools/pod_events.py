from langchain_core.tools import tool
from app.tools.k8s_client import core_v1


@tool
def get_pod_events(namespace: str, pod_name: str = "") -> str:
    """
    Retrieve Kubernetes events for a namespace, optionally filtered to a specific pod.

    Events are Kubernetes' own audit log — they record what the control plane
    did or tried to do: scheduling decisions, image pulls, OOM kills, volume mount
    failures, liveness probe failures, etc. Always check events when a pod is
    Pending or when get_pod_status shows an unclear reason.

    Args:
        namespace: The Kubernetes namespace to query events in (e.g. "default").
        pod_name:  Optional. Filter events to a specific pod name or prefix.
                   Leave empty to get all recent events in the namespace.
    """
    api = core_v1()

    # Kubernetes events are stored as objects in the same namespace as the resource.
    # They have a .involved_object that links them to a pod, deployment, etc.
    all_events = api.list_namespaced_event(namespace=namespace)

    events = all_events.items

    # Filter to the specific pod if a name was given
    if pod_name:
        events = [
            e for e in events
            if e.involved_object.name and e.involved_object.name.startswith(pod_name)
        ]

    if not events:
        target = f"pod '{pod_name}'" if pod_name else f"namespace '{namespace}'"
        return f"No events found for {target}."

    # Sort by last timestamp, most recent first
    # last_timestamp is when the event was last seen (events can repeat)
    events.sort(
        key=lambda e: e.last_timestamp or e.event_time or "",
        reverse=True,
    )

    # Only show the 20 most recent events — more than enough for diagnosis
    events = events[:20]

    lines = [f"Events in namespace '{namespace}'" + (f" for pod '{pod_name}'" if pod_name else "") + ":\n"]

    for e in events:
        # Event type is "Normal" or "Warning"
        # Warning events are the ones that indicate problems
        type_marker = "⚠" if e.type == "Warning" else "ℹ"
        timestamp = str(e.last_timestamp or e.event_time or "unknown time")
        count = f"(x{e.count})" if e.count and e.count > 1 else ""

        lines.append(
            f"{type_marker} [{timestamp}] {count}\n"
            f"   Object : {e.involved_object.kind}/{e.involved_object.name}\n"
            f"   Reason : {e.reason}\n"
            f"   Message: {e.message}\n"
        )

    return "\n".join(lines)
