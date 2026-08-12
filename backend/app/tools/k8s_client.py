import os
from kubernetes import client, config
from kubernetes.client import CoreV1Api, AppsV1Api


def _load_config() -> None:
    """
    Load Kubernetes authentication configuration.

    WHY two methods?
    ----------------
    There are two ways to authenticate to a Kubernetes cluster:

    1. In-cluster config:
       When kubefriend itself runs INSIDE a Kubernetes pod (future), the cluster
       injects credentials automatically via a mounted ServiceAccount token at
       /var/run/secrets/kubernetes.io/serviceaccount/
       No kubeconfig file needed — the pod IS the credential.

    2. Kubeconfig file:
       When running locally or in Docker, we use the kubeconfig file at
       ~/.kube/config (mounted into the container as a volume).
       This is the same file kubectl uses.

    We try in-cluster first — if that fails (we're not in a pod), fall back
    to kubeconfig. This means the same code works in both environments.
    """
    try:
        config.load_incluster_config()
    except config.ConfigException:
        kubeconfig_path = os.getenv("KUBECONFIG_PATH")
        config.load_kube_config(config_file=kubeconfig_path or None)
        # passing None means "use the default ~/.kube/config location"


def core_v1() -> CoreV1Api:
    """
    Return a Kubernetes CoreV1Api client.

    CoreV1Api covers the core resource types:
    - Pods          (get_pod_status, get_pod_logs, get_pod_events)
    - Services
    - ConfigMaps
    - PersistentVolumeClaims  (get_pvc)
    - Events

    Call this inside each tool function (not at module level) so the config
    is loaded fresh each time — avoids stale credentials after token refresh.
    """
    _load_config()
    return client.CoreV1Api()


def apps_v1() -> AppsV1Api:
    """
    Return a Kubernetes AppsV1Api client.

    AppsV1Api covers higher-level workload resources:
    - Deployments   (get_deployment)
    - ReplicaSets
    - StatefulSets
    - DaemonSets
    """
    _load_config()
    return client.AppsV1Api()
