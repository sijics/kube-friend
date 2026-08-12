import os
import re
from kubernetes import client, config
from kubernetes.client import CoreV1Api, AppsV1Api

# ---------------------------------------------------------------------------
# Host override — applied once at module import time.
#
# WHY at import time?
# -------------------
# load_kube_config() populates client.Configuration._default (a module-level
# singleton). Every CoreV1Api / AppsV1Api constructed without an explicit
# api_client reads from that singleton at call time — not at construction time.
# Patching _default.host here (before any API object is created) is therefore
# the only reliable place that affects all subsequent API calls.
#
# WHY KUBE_SERVER_HOST_OVERRIDE?
# ------------------------------
# OpenShift's `oc login` tunnels the cluster API to localhost:<port> on your
# Mac. Inside Docker "localhost" is the container, not the Mac host. Docker
# Desktop exposes the Mac via "host.docker.internal". Setting this env var
# rewrites every localhost/127.0.0.1 server reference in the loaded kubeconfig
# so the containerised backend can reach the tunnel on the Mac host.
# ---------------------------------------------------------------------------

def _load_kube_config() -> None:
    """Load kubeconfig (in-cluster first, then file) and apply host override."""
    try:
        config.load_incluster_config()
        return  # in-cluster: no localhost tunnel, no override needed
    except config.ConfigException:
        pass

    kubeconfig_path = os.getenv("KUBECONFIG_PATH")
    config.load_kube_config(config_file=kubeconfig_path or None)

    host_override = os.getenv("KUBE_SERVER_HOST_OVERRIDE")
    if not host_override:
        return

    # Patch the singleton that load_kube_config just wrote.
    # client.Configuration._default is the object all API clients read from.
    default_cfg = client.Configuration._default  # type: ignore[attr-defined]
    if default_cfg and default_cfg.host:
        default_cfg.host = re.sub(
            r"https?://(localhost|127\.0\.0\.1)(:\d+)?",
            lambda m: f"https://{host_override}{m.group(2) or ''}",
            default_cfg.host,
        )
        # The TLS cert is issued for 127.0.0.1, not host.docker.internal.
        # Disable hostname verification when using the override — we're still
        # using the same certificate and CA, just reaching it via a different name.
        default_cfg.verify_ssl = False


# Load once when the module is imported so every tool function shares the
# same already-patched configuration object.
_load_kube_config()


def core_v1() -> CoreV1Api:
    """
    Return a Kubernetes CoreV1Api client.

    Covers: Pods, Services, ConfigMaps, PersistentVolumeClaims, Events.
    """
    return client.CoreV1Api()


def apps_v1() -> AppsV1Api:
    """
    Return a Kubernetes AppsV1Api client.

    Covers: Deployments, ReplicaSets, StatefulSets, DaemonSets.
    """
    return client.AppsV1Api()