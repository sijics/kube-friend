from langchain_core.tools import tool
from app.tools.k8s_client import core_v1


@tool
def get_pvc(namespace: str, pvc_name: str = "") -> str:
    """
    Get the status of PersistentVolumeClaims (PVCs) in a namespace.

    Use this tool when a pod is stuck in Pending state and you suspect a
    storage problem, or when the user asks about disk/storage issues.
    A PVC is a request for storage — if it's not Bound, the pod that needs
    it cannot start.

    Args:
        namespace: The Kubernetes namespace (e.g. "default", "prod").
        pvc_name:  Optional. Name or prefix of a specific PVC to inspect.
                   Leave empty to list all PVCs in the namespace.
    """
    api = core_v1()

    if pvc_name:
        try:
            pvc = api.read_namespaced_persistent_volume_claim(name=pvc_name, namespace=namespace)
            pvcs = [pvc]
        except Exception:
            all_pvcs = api.list_namespaced_persistent_volume_claim(namespace=namespace)
            pvcs = [p for p in all_pvcs.items if p.metadata.name.startswith(pvc_name)]
    else:
        all_pvcs = api.list_namespaced_persistent_volume_claim(namespace=namespace)
        pvcs = all_pvcs.items

    if not pvcs:
        target = f"PVC '{pvc_name}'" if pvc_name else f"any PVCs"
        return f"Could not find {target} in namespace '{namespace}'."

    lines = [f"PersistentVolumeClaims in namespace '{namespace}':\n"]

    for pvc in pvcs:
        meta = pvc.metadata
        spec = pvc.spec
        status = pvc.status

        # PVC phase is the key indicator:
        # Bound    = storage is allocated and ready
        # Pending  = waiting for a PersistentVolume to be provisioned (pod cannot start)
        # Lost     = the backing PV was deleted (data may be gone)
        phase_marker = "✓" if status.phase == "Bound" else "✗"

        lines.append(f"{phase_marker} {meta.name}")
        lines.append(f"   Phase        : {status.phase}")
        lines.append(f"   Access Modes : {spec.access_modes}")
        lines.append(f"   Storage Class: {spec.storage_class_name or 'default'}")
        lines.append(f"   Capacity     : {spec.resources.requests.get('storage', '?') if spec.resources and spec.resources.requests else '?'}")
        lines.append(f"   Volume       : {spec.volume_name or 'not bound yet'}")

        # Conditions appear when the PVC has a problem (e.g. resize failed)
        if status.conditions:
            lines.append("   Conditions:")
            for cond in status.conditions:
                lines.append(f"     - {cond.type}: {cond.reason} — {cond.message}")

        lines.append("")

    return "\n".join(lines)
