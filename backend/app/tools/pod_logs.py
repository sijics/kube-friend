from langchain_core.tools import tool
from app.tools.k8s_client import core_v1


@tool
def get_pod_logs(namespace: str, pod_name: str, container: str = "", tail_lines: int = 100) -> str:
    """
    Retrieve recent logs from a Kubernetes pod or specific container.

    Use this tool to see what a pod is actually printing — error messages,
    stack traces, application crashes, or startup failures. Always call this
    after get_pod_status when a pod is in CrashLoopBackOff or Error state.

    Args:
        namespace:   The Kubernetes namespace (e.g. "default", "prod").
        pod_name:    The pod name or prefix (e.g. "openrag-backend").
        container:   Container name within the pod. Leave empty for single-container pods.
                     Required if the pod has multiple containers.
        tail_lines:  Number of recent log lines to retrieve. Default is 100.
                     Use a smaller number (20-30) for a quick scan.
    """
    api = core_v1()

    # Resolve pod name prefix to exact pod name
    try:
        api.read_namespaced_pod(name=pod_name, namespace=namespace)
        exact_name = pod_name
    except Exception:
        all_pods = api.list_namespaced_pod(namespace=namespace)
        matches = [p.metadata.name for p in all_pods.items if p.metadata.name.startswith(pod_name)]
        if not matches:
            return f"No pod found matching '{pod_name}' in namespace '{namespace}'."
        exact_name = matches[0]  # use the first matching pod

    try:
        logs = api.read_namespaced_pod_log(
            name=exact_name,
            namespace=namespace,
            container=container or None,   # None = use the only/default container
            tail_lines=tail_lines,
            timestamps=True,               # prepend timestamp to each line — useful for debugging
            previous=False,                # False = current container instance
                                           # True  = the previous (crashed) container instance
        )

        if not logs.strip():
            # No output doesn't mean no problem — the container may have crashed before logging
            return (
                f"No logs found for pod '{exact_name}' in namespace '{namespace}'.\n"
                "The container may have crashed before writing any logs. "
                "Try get_pod_status to check last termination reason, "
                "or re-run with previous=True for the previous crashed instance."
            )

        return f"Logs for pod '{exact_name}' (last {tail_lines} lines):\n\n{logs}"

    except Exception as e:
        # Common reasons: pod is Pending (not yet running), container name wrong,
        # or the pod was evicted and no longer has logs
        return f"Could not retrieve logs for '{exact_name}': {e}"
