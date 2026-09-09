"""
orphaned_pvs.py — find orphaned OpenRAG PersistentVolumes (PV-level scan).

Ported from list-orphaned-pvs.sh. Operates at the PV level, not PVC level,
and covers two distinct PV origins:

TYPE A — NFS PVs created by infra-openrag-operator
  Name pattern : c-<workload-id>-pv
  CSI driver   : vpc.file.csi.ibm.io
  Labels       : workload=<workload-id>  tenant=<namespace>

TYPE B — Block PVs dynamically provisioned by the OSS operator Helm chart
  Name pattern : pvc-<uuid>  (Kubernetes auto-generated)
  Claim names  : openrag-lf-data | openrag-be-data | openrag-data
  Claim NS     : IS the workload namespace (namespace == workload-id)

A PV is orphaned when:
  - Its phase is Released or Failed  (immediate signal — no owner PVC)
  - OR its claim namespace has no live OpenRAG CR AND no live Workload CR
"""

import re
from langchain_core.tools import tool
from kubernetes import client as k8s_client

# CSI driver used for NFS PVs (Type A)
_NFS_DRIVER = "vpc.file.csi.ibm.io"

# Claim name suffixes that identify OSS operator PVs (Type B)
_OSS_CLAIM_SUFFIXES = ("openrag-lf-data", "openrag-be-data", "openrag-data")

# Name pattern for infra-openrag-operator NFS PVs (Type A)
_NFS_PV_RE = re.compile(r"^c-(.+)-pv$")


def _core_v1() -> k8s_client.CoreV1Api:
    return k8s_client.CoreV1Api()


def _custom_api() -> k8s_client.CustomObjectsApi:
    return k8s_client.CustomObjectsApi()


def _namespace_is_active(custom: k8s_client.CustomObjectsApi, namespace: str) -> bool:
    """
    Return True if namespace still has a live OpenRAG CR or Workload CR.
    Mirrors namespace_is_active() in the bash script.
    """
    # Check Workload CR (infra-openrag-operator)
    try:
        result = custom.list_namespaced_custom_object(
            group="wxd.ibm.com", version="v1",
            namespace=namespace, plural="workloads",
        )
        if result.get("items"):
            return True
    except Exception:
        pass

    # Check OpenRAG CR (OSS operator) — auto-discover plural name
    try:
        ext = k8s_client.ApiextensionsV1Api()
        for crd in ext.list_custom_resource_definition().items:
            names = crd.spec.names
            if names.singular == "openrag" or names.plural in ("openrags",):
                grp = crd.spec.group
                ver = next(
                    (v.name for v in crd.spec.versions if v.served),
                    crd.spec.versions[0].name,
                )
                result = custom.list_namespaced_custom_object(
                    group=grp, version=ver,
                    namespace=namespace, plural=names.plural,
                )
                if result.get("items"):
                    return True
    except Exception:
        pass

    return False


@tool
def find_orphaned_openrag_pvs(dry_run: bool = True) -> str:
    """
    Find (and optionally delete) orphaned OpenRAG PersistentVolumes across
    the entire cluster.

    Covers two PV types:
      TYPE A — NFS PVs created by infra-openrag-operator
               (name pattern: c-<workload-id>-pv, driver: vpc.file.csi.ibm.io)
      TYPE B — Block PVs provisioned by the OSS operator Helm chart
               (claim names: openrag-lf-data, openrag-be-data, openrag-data)

    A PV is considered orphaned when:
      - Its phase is Released or Failed, OR
      - Its claim namespace has no live OpenRAG CR and no live Workload CR

    Args:
        dry_run: When True (default), only lists orphaned PVs — no deletions.
                 When False, deletes every identified orphan.
                 Always review with dry_run=True before setting False.
    """
    core    = _core_v1()
    custom  = _custom_api()

    try:
        all_pvs = core.list_persistent_volume().items
    except Exception as e:
        return f"Error listing PersistentVolumes: {e}"

    orphans = []
    ok_pvs  = []
    total_a = 0
    total_b = 0

    lines = [
        "=== OpenRAG Orphaned PV Scanner ===",
        f"dry_run={dry_run}",
        "",
    ]

    # ── TYPE A — NFS PVs (c-<workload-id>-pv) ────────────────────────────────
    lines.append("--- TYPE A: NFS PVs (infra-openrag-operator) ---")
    type_a_pvs = [
        pv for pv in all_pvs
        if _NFS_PV_RE.match(pv.metadata.name)
        and pv.spec.csi
        and pv.spec.csi.driver == _NFS_DRIVER
    ]

    if not type_a_pvs:
        lines.append("  None found.")
    else:
        for pv in type_a_pvs:
            total_a += 1
            pv_name  = pv.metadata.name
            labels   = pv.metadata.labels or {}
            phase    = pv.status.phase or "Unknown"
            reclaim  = pv.spec.persistent_volume_reclaim_policy or "Unknown"
            capacity = "?"
            if pv.spec.capacity:
                capacity = pv.spec.capacity.get("storage", "?")

            # Extract workload-id from name: c-<workload-id>-pv
            m = _NFS_PV_RE.match(pv_name)
            workload_id = m.group(1) if m else ""
            tenant_ns   = labels.get("tenant", workload_id)

            reason = ""
            if phase in ("Released", "Failed"):
                reason = f"phase={phase}"
            elif tenant_ns and not _namespace_is_active(custom, tenant_ns):
                reason = f"no OpenRAG/Workload CR in ns {tenant_ns}"

            entry = {
                "type": "A", "name": pv_name, "workload_id": workload_id,
                "namespace": tenant_ns, "phase": phase, "reclaim": reclaim,
                "capacity": capacity, "reason": reason,
            }
            if reason:
                orphans.append(entry)
                lines.append(
                    f"  [ORPHAN] {pv_name}\n"
                    f"    phase={phase}  reclaim={reclaim}  capacity={capacity}\n"
                    f"    workload={workload_id}  ns={tenant_ns}\n"
                    f"    reason={reason}\n"
                    f"    delete: kubectl delete pv {pv_name}"
                )
            else:
                ok_pvs.append(entry)
                lines.append(f"  [OK]     {pv_name}  phase={phase}  ns={tenant_ns}")

    lines.append("")

    # ── TYPE B — Block PVs (OSS Helm chart) ──────────────────────────────────
    lines.append("--- TYPE B: Block PVs (OSS operator Helm chart) ---")
    type_b_pvs = [
        pv for pv in all_pvs
        if pv.spec.claim_ref
        and pv.spec.claim_ref.name
        and any(pv.spec.claim_ref.name.endswith(s) for s in _OSS_CLAIM_SUFFIXES)
    ]

    if not type_b_pvs:
        lines.append("  None found.")
    else:
        for pv in type_b_pvs:
            total_b += 1
            pv_name    = pv.metadata.name
            claim_ns   = pv.spec.claim_ref.namespace or ""
            claim_name = pv.spec.claim_ref.name or ""
            phase      = pv.status.phase or "Unknown"
            reclaim    = pv.spec.persistent_volume_reclaim_policy or "Unknown"
            sc         = pv.spec.storage_class_name or ""
            capacity   = "?"
            if pv.spec.capacity:
                capacity = pv.spec.capacity.get("storage", "?")

            reason = ""
            if phase in ("Released", "Failed"):
                reason = f"phase={phase}"
            elif claim_ns and not _namespace_is_active(custom, claim_ns):
                reason = f"no OpenRAG/Workload CR in ns {claim_ns}"

            entry = {
                "type": "B", "name": pv_name, "workload_id": claim_ns,
                "namespace": claim_ns, "claim": claim_name,
                "phase": phase, "reclaim": reclaim,
                "storage_class": sc, "capacity": capacity, "reason": reason,
            }
            if reason:
                orphans.append(entry)
                lines.append(
                    f"  [ORPHAN] {pv_name}\n"
                    f"    phase={phase}  reclaim={reclaim}  sc={sc}  capacity={capacity}\n"
                    f"    claim={claim_ns}/{claim_name}\n"
                    f"    reason={reason}\n"
                    f"    delete: kubectl delete pv {pv_name}"
                )
            else:
                ok_pvs.append(entry)
                lines.append(
                    f"  [OK]     {pv_name}"
                    f"  phase={phase}  claim={claim_ns}/{claim_name}"
                )

    lines.append("")
    total = total_a + total_b
    lines.append("═" * 64)
    lines.append(
        f"Summary: {len(orphans)} orphaned PV(s) out of {total} total OpenRAG PV(s) "
        f"(Type A: {total_a}, Type B: {total_b})."
    )

    if not orphans:
        lines.append("No orphaned PVs found.")
        return "\n".join(lines)

    lines.append("")
    lines.append("Orphaned PVs:")
    for o in orphans:
        lines.append(f"  - {o['name']}  ({o['reason']})")

    # ── Deletion ─────────────────────────────────────────────────────────────
    if not dry_run:
        lines.append("")
        lines.append("dry_run=False — deleting orphaned PVs...")
        deleted = []
        errors  = []
        for o in orphans:
            try:
                core.delete_persistent_volume(name=o["name"])
                deleted.append(o["name"])
                lines.append(f"  ✓ Deleted {o['name']}")
            except Exception as e:
                errors.append(o["name"])
                lines.append(f"  ✗ Failed to delete {o['name']}: {e}")
        lines.append(
            f"\nDeleted {len(deleted)} PV(s)."
            + (f" {len(errors)} error(s)." if errors else "")
        )
    else:
        lines.append("")
        lines.append("dry_run=True — no PVs were deleted.")
        lines.append("To delete, call this tool again with dry_run=False.")

    return "\n".join(lines)
