"""
crd_resource.py — generic tool to query any CRD / custom resource in the cluster.

This tool lets the LLM agent inspect ANY Kubernetes custom resource —
workloads, operators, CRDs you define — without needing a dedicated tool per type.
"""

import json
from langchain_core.tools import tool
from app.tools.k8s_client import core_v1
from kubernetes import client as k8s_client


def _custom_objects_api():
    """Return a CustomObjectsApi using the same patched config as other tools."""
    from app.tools.k8s_client import _load_kube_config
    _load_kube_config()
    return k8s_client.CustomObjectsApi()


def _discover_crd(plural: str) -> tuple[str, str, str] | None:
    """
    Given a plural resource name (e.g. 'workloads'), discover its
    group, version, and plural by scanning all CRDs.
    Returns (group, version, plural) or None if not found.
    """
    try:
        ext = k8s_client.ApiextensionsV1Api()
        crds = ext.list_custom_resource_definition()
        for crd in crds.items:
            names = crd.spec.names
            if names.plural == plural or names.singular == plural or names.kind.lower() == plural.rstrip('s'):
                group = crd.spec.group
                # Pick the first stored version
                version = next(
                    (v.name for v in crd.spec.versions if v.served),
                    crd.spec.versions[0].name if crd.spec.versions else "v1"
                )
                return group, version, names.plural
    except Exception:
        pass
    return None


@tool
def get_crd_resources(
    resource_type: str,
    namespace: str = "",
    filter_type: str = "",
    filter_state: str = "",
    name: str = "",
) -> str:
    """
    Query any Kubernetes Custom Resource (CRD) by resource type.

    Use this tool when the user asks about custom resources like workloads,
    operators, or any non-standard Kubernetes resource. For example:
    - "show me all openrag workloads"
    - "what is the status of workload X"
    - "list all milvus workloads in namespace Y"
    - "why is workload Z in Processing state"

    Args:
        resource_type:  The plural CRD name, e.g. "workloads", "kafkas", "opensearchclusters"
        namespace:      Kubernetes namespace. Leave empty to search all namespaces.
        filter_type:    Filter by spec.type label/field (e.g. "openrag", "milvus", "presto")
        filter_state:   Filter by status.state (e.g. "Processing", "OK", "Failed")
        name:           Exact name of a specific resource to look up.
    """
    api = _custom_objects_api()

    # Auto-discover the CRD group+version
    discovered = _discover_crd(resource_type)
    if not discovered:
        return (
            f"CRD '{resource_type}' not found in the cluster. "
            f"Run 'kubectl get crd' to see available custom resource types."
        )

    group, version, plural = discovered

    try:
        if namespace:
            result = api.list_namespaced_custom_object(
                group=group, version=version, namespace=namespace, plural=plural
            )
        else:
            result = api.list_cluster_custom_object(
                group=group, version=version, plural=plural
            )
    except Exception as e:
        return f"Error querying {plural}: {e}"

    items = result.get("items", [])
    if not items:
        return f"No {plural} found" + (f" in namespace '{namespace}'" if namespace else " across all namespaces") + "."

    # Apply filters
    if name:
        items = [i for i in items if i.get("metadata", {}).get("name", "") == name]
    if filter_type:
        items = [
            i for i in items
            if i.get("metadata", {}).get("labels", {}).get("type", "").lower() == filter_type.lower()
            or i.get("spec", {}).get("type", "").lower() == filter_type.lower()
        ]
    if filter_state:
        items = [
            i for i in items
            if i.get("status", {}).get("state", "").lower() == filter_state.lower()
        ]

    if not items:
        return f"No {plural} matched the given filters (type={filter_type!r}, state={filter_state!r}, name={name!r})."

    lines = [f"{group}/{version} — {plural} ({len(items)} found)\n"]

    for item in items:
        meta = item.get("metadata", {})
        spec = item.get("spec", {})
        status = item.get("status", {})
        labels = meta.get("labels", {})

        lines.append(f"Name      : {meta.get('name', '?')}")
        lines.append(f"Namespace : {meta.get('namespace', 'cluster-scoped')}")
        lines.append(f"Type      : {labels.get('type') or spec.get('type', '?')}")
        lines.append(f"Version   : {spec.get('version', '?')}")
        lines.append(f"State     : {status.get('state', 'unknown')}")
        lines.append(f"Age       : {meta.get('creationTimestamp', '?')}")

        # Surface components if present (e.g. watsonx workload components)
        components = status.get("components", {})
        if components:
            lines.append("Components:")
            for comp_name, comp in components.items():
                if isinstance(comp, dict):
                    comp_state = comp.get("state", comp.get("status", "?"))
                    comp_ver   = comp.get("version", "")
                    lines.append(f"  {comp_name}: {comp_state} {comp_ver}".rstrip())

        # Surface disablements
        disablements = spec.get("disablements", [])
        if disablements:
            lines.append(f"Disablements: {', '.join(str(d) for d in disablements)}")

        # Instance ID / CRN
        instance_id = spec.get("instance_id", "")
        if instance_id:
            lines.append(f"Instance  : {instance_id}")

        lines.append("")  # blank line between items

    return "\n".join(lines)
