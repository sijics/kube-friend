"""
orphaned_pvc.py — find OpenRAG PVCs whose parent Workload or OpenRAG CR no longer exists.

Ported from the bash script that uses kubectl + jq. The logic is:

1. List every PVC across all namespaces (or a specific one).
2. Keep only PVCs that look like they belong to OpenRAG:
     - label type=openrag
     - label service_id starts with "openrag"
     - label workload_id is set
     - name contains "openrag", "langflow", or "backend"
3. For each candidate PVC, resolve the owner workload ID:
     - From label workload_id if present
     - By extracting a UUID prefix from the PVC name (patterns: c-<uuid>-* or <uuid>-*)
4. If a workload ID was resolved:
     - Check if a Workload CR exists in that namespace with that name
     - Check if an OpenRAG CR exists in that namespace with that name
     - If neither exists → ORPHANED
5. If no workload ID could be resolved:
     - Check whether any workload or openrag resources exist in the namespace at all
     - If none → ORPHANED, else → UNKNOWN (cannot determine owner)
"""

import re
from langchain_core.tools import tool
from app.tools.k8s_client import core_v1
from kubernetes import client as k8s_client


def _custom_api() -> k8s_client.CustomObjectsApi:
    return k8s_client.CustomObjectsApi()


def _workload_exists(custom: k8s_client.CustomObjectsApi,
                     namespace: str, workload_id: str) -> bool:
    """Return True if a workloads.wxd.ibm.com CR named workload_id exists in namespace."""
    try:
        custom.get_namespaced_custom_object(
            group="wxd.ibm.com", version="v1",
            namespace=namespace, plural="workloads", name=workload_id,
        )
        return True
    except Exception:
        return False


def _openrag_cr_exists(custom: k8s_client.CustomObjectsApi,
                       namespace: str, cr_name: str) -> bool:
    """Return True if an openrags CR named cr_name exists in namespace.
    Tries common OpenRAG CRD plural names."""
    for plural in ("openrags", "openrag"):
        try:
            # Try to discover the actual group/version first
            ext = k8s_client.ApiextensionsV1Api()
            crds = ext.list_custom_resource_definition()
            for crd in crds.items:
                if crd.spec.names.plural == plural or crd.spec.names.singular == "openrag":
                    group = crd.spec.group
                    version = next(
                        (v.name for v in crd.spec.versions if v.served),
                        crd.spec.versions[0].name,
                    )
                    custom.get_namespaced_custom_object(
                        group=group, version=version,
                        namespace=namespace, plural=crd.spec.names.plural,
                        name=cr_name,
                    )
                    return True
        except Exception:
            pass
    return False


# UUID pattern — matches standard hyphenated UUIDs (8-4-4-4-12)
_UUID_RE = re.compile(
    r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}",
    re.IGNORECASE,
)

# PVC name patterns from the bash script:
#   c-<uuid>-*   →  extract uuid
#   <uuid>-*     →  extract uuid
_PVC_PREFIX_RE = re.compile(
    r"^(?:c-)?([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})-",
    re.IGNORECASE,
)


def _extract_workload_id(pvc_name: str) -> str:
    """Extract a workload UUID from a PVC name, or return empty string."""
    m = _PVC_PREFIX_RE.match(pvc_name)
    return m.group(1) if m else ""


def _is_openrag_pvc(pvc) -> bool:
    """Return True if this PVC looks like it belongs to OpenRAG."""
    labels = pvc.metadata.labels or {}
    name = pvc.metadata.name.lower()

    if labels.get("type", "").lower() == "openrag":
        return True
    if str(labels.get("service_id", "")).lower().startswith("openrag"):
        return True
    if "workload_id" in labels:
        return True
    if any(kw in name for kw in ("openrag", "langflow", "backend")):
        return True
    return False


@tool
def find_orphaned_openrag_pvcs(namespace: str = "") -> str:
    """
    Find orphaned OpenRAG PVCs — PVCs that belong to an OpenRAG workload
    whose parent Workload CR or OpenRAG CR no longer exists in the cluster.

    Orphaned PVCs waste storage and should be cleaned up after a workload
    is deleted. This tool scans all namespaces (or a specific one) for PVCs
    that match OpenRAG patterns and checks whether their owning workload
    still exists.

    Args:
        namespace: Kubernetes namespace to scan. Leave empty to scan ALL
                   namespaces (recommended — OpenRAG uses per-instance namespaces).
    """
    api     = core_v1()
    custom  = _custom_api()

    # ── 1. Collect candidate PVCs ────────────────────────────────────────────
    try:
        if namespace:
            all_pvcs = api.list_namespaced_persistent_volume_claim(namespace=namespace).items
        else:
            all_pvcs = api.list_persistent_volume_claim_for_all_namespaces().items
    except Exception as e:
        return f"Error listing PVCs: {e}"

    candidates = [p for p in all_pvcs if _is_openrag_pvc(p)]

    if not candidates:
        scope = f"namespace '{namespace}'" if namespace else "all namespaces"
        return f"No OpenRAG PVCs found in {scope}."

    # ── 2. Classify each PVC ─────────────────────────────────────────────────
    orphaned = []
    active   = []
    unknown  = []

    for pvc in candidates:
        ns       = pvc.metadata.namespace
        name     = pvc.metadata.name
        labels   = pvc.metadata.labels or {}
        phase    = pvc.status.phase or "Unknown"
        capacity = "?"
        if pvc.spec.resources and pvc.spec.resources.requests:
            capacity = pvc.spec.resources.requests.get("storage", "?")

        # Resolve workload ID — from label first, then PVC name pattern
        workload_id = labels.get("workload_id", "") or _extract_workload_id(name)

        entry = {
            "namespace":   ns,
            "pvc_name":    name,
            "workload_id": workload_id or "N/A",
            "phase":       phase,
            "capacity":    capacity,
        }

        if workload_id:
            if _workload_exists(custom, ns, workload_id):
                entry["reason"] = "Workload CR exists"
                active.append(entry)
            elif _openrag_cr_exists(custom, ns, workload_id):
                entry["reason"] = "OpenRAG CR exists"
                active.append(entry)
            else:
                entry["reason"] = f"No Workload or OpenRAG CR found for ID {workload_id}"
                entry["delete_cmd"] = f"kubectl delete pvc {name} -n {ns}"
                orphaned.append(entry)
        else:
            # No workload ID — check if ANY workload/openrag resources exist in ns
            wl_count = 0
            try:
                wl_result = custom.list_namespaced_custom_object(
                    group="wxd.ibm.com", version="v1",
                    namespace=ns, plural="workloads",
                )
                wl_count = len(wl_result.get("items", []))
            except Exception:
                pass

            if wl_count == 0:
                entry["reason"] = "No workload_id label and no Workload CRs in namespace"
                entry["delete_cmd"] = f"kubectl delete pvc {name} -n {ns}"
                orphaned.append(entry)
            else:
                entry["reason"] = "Cannot determine owner (no workload_id label)"
                unknown.append(entry)

    # ── 3. Format output ─────────────────────────────────────────────────────
    lines = []
    lines.append(
        f"OpenRAG PVC scan — "
        f"scanned {len(candidates)} PVC(s): "
        f"{len(orphaned)} orphaned · {len(active)} active · {len(unknown)} unknown\n"
    )

    if orphaned:
        lines.append("── ORPHANED PVCs (safe to delete) ──────────────────────────")
        for p in orphaned:
            lines += [
                f"✗ {p['pvc_name']}",
                f"  Namespace  : {p['namespace']}",
                f"  Workload ID: {p['workload_id']}",
                f"  Phase      : {p['phase']}",
                f"  Capacity   : {p['capacity']}",
                f"  Reason     : {p['reason']}",
                f"  Delete     : {p['delete_cmd']}",
                "",
            ]

    if unknown:
        lines.append("── UNKNOWN ownership (review manually) ──────────────────────")
        for p in unknown:
            lines += [
                f"? {p['pvc_name']}",
                f"  Namespace  : {p['namespace']}",
                f"  Phase      : {p['phase']}",
                f"  Capacity   : {p['capacity']}",
                f"  Reason     : {p['reason']}",
                "",
            ]

    if active:
        lines.append("── ACTIVE PVCs (workload exists) ────────────────────────────")
        for p in active:
            lines += [
                f"✓ {p['pvc_name']}",
                f"  Namespace  : {p['namespace']}",
                f"  Workload ID: {p['workload_id']}",
                f"  Phase      : {p['phase']}",
                f"  Capacity   : {p['capacity']}",
                "",
            ]

    if orphaned:
        lines.append(
            f"WARNING: {len(orphaned)} orphaned PVC(s) found. "
            "Review and delete with the commands above."
        )

    return "\n".join(lines)
