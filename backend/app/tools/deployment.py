from langchain_core.tools import tool
from app.tools.k8s_client import apps_v1


@tool
def get_deployment(namespace: str, deployment_name: str) -> str:
    """
    Get the status and configuration of a Kubernetes Deployment.

    Use this tool when the user asks about a deployment — how many replicas
    are running, what image version is deployed, whether a rollout is stuck,
    or what the deployment strategy is. Deployments manage the desired state
    of a set of pods.

    Args:
        namespace:       The Kubernetes namespace (e.g. "default", "prod").
        deployment_name: The deployment name (e.g. "openrag-backend").
    """
    api = apps_v1()

    try:
        # Try exact name first
        deployment = api.read_namespaced_deployment(name=deployment_name, namespace=namespace)
        deployments = [deployment]
    except Exception:
        # Fall back to prefix search
        all_deps = api.list_namespaced_deployment(namespace=namespace)
        deployments = [d for d in all_deps.items if d.metadata.name.startswith(deployment_name)]

    if not deployments:
        return f"No deployment found matching '{deployment_name}' in namespace '{namespace}'."

    lines = []
    for d in deployments:
        meta = d.metadata
        spec = d.spec
        status = d.status

        lines.append(f"Deployment: {meta.name}")
        lines.append(f"  Namespace : {meta.namespace}")
        lines.append(f"  Labels    : {meta.labels}")

        # Replica counts — the key health indicator for a deployment
        # desired = what you asked for, ready = actually serving traffic
        lines.append(f"  Replicas  : desired={spec.replicas}  ready={status.ready_replicas or 0}  "
                     f"available={status.available_replicas or 0}  updated={status.updated_replicas or 0}")

        # Rollout strategy: RollingUpdate (zero-downtime) or Recreate (downtime)
        if spec.strategy:
            lines.append(f"  Strategy  : {spec.strategy.type}")
            if spec.strategy.rolling_update:
                ru = spec.strategy.rolling_update
                lines.append(f"    maxSurge={ru.max_surge}  maxUnavailable={ru.max_unavailable}")

        # Container images — tells you what version is actually deployed
        lines.append("  Containers:")
        for container in spec.template.spec.containers:
            lines.append(f"    - {container.name}: {container.image}")
            if container.resources:
                req = container.resources.requests or {}
                lim = container.resources.limits or {}
                lines.append(f"      requests: cpu={req.get('cpu','?')} memory={req.get('memory','?')}")
                lines.append(f"      limits:   cpu={lim.get('cpu','?')} memory={lim.get('memory','?')}")

        # Deployment conditions — shows if a rollout is progressing or stuck
        if status.conditions:
            lines.append("  Conditions:")
            for cond in status.conditions:
                flag = "✓" if cond.status == "True" else "✗"
                lines.append(f"    {flag} {cond.type}: {cond.reason} — {cond.message or ''}")

        lines.append("")

    return "\n".join(lines)
