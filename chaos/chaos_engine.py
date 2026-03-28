"""
chaos_engine.py — KubeResilience Core Module
============================================
Injects controlled chaos into Kubernetes services to test resilience.
Supports 5 scenarios:  pod_kill | cpu_stress | memory_stress |
                        network_latency | packet_loss

Entry point: inject_chaos_safe(service, scenario) -> dict
"""

import os
import subprocess
import json
from datetime import datetime, timezone
from typing import Dict, Any, List, Tuple

# ─────────────────────────────────────────────
# CONSTANTS & CONFIGURATION
# ─────────────────────────────────────────────
NAMESPACE: str = "boutique"
CHAOS_NAMESPACE: str = "chaos-mesh"

CRITICAL_SERVICES: List[str] = ["frontend", "checkoutservice"]

ALL_SERVICES: List[str] = [
    "frontend",
    "cartservice",
    "checkoutservice",
    "paymentservice",
    "emailservice",
    "productcatalogservice",
    "recommendationservice",
    "currencyservice",
    "shippingservice",
    "adservice",
]

MANIFESTS_DIR: str = os.path.join(os.path.dirname(__file__), "manifests")

# Maps scenario name → (yaml_file, Chaos Mesh kind, resource_name)
SCENARIO_MANIFEST: Dict[str, Tuple[str, str, str]] = {
    "pod_kill":        ("pod_kill.yaml",        "PodChaos",     "kuberesilience-pod-kill"),
    "cpu_stress":      ("cpu_stress.yaml",       "StressChaos",  "kuberesilience-cpu-stress"),
    "memory_stress":   ("memory_stress.yaml",    "StressChaos",  "kuberesilience-memory-stress"),
    "network_latency": ("network_latency.yaml",  "NetworkChaos", "kuberesilience-network-latency"),
    "packet_loss":     ("packet_loss.yaml",      "NetworkChaos", "kuberesilience-packet-loss"),
}

# CRD kind → kubectl resource type
_KIND_TO_CRD: Dict[str, str] = {
    "PodChaos":     "podchaos",
    "StressChaos":  "stresschaos",
    "NetworkChaos": "networkchaos",
}

# ─────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────
def _now_iso() -> str:
    """Return current UTC time as an ISO-8601 string."""
    return datetime.now(timezone.utc).isoformat()


def _run(cmd: List[str], stdin_data: str = "") -> subprocess.CompletedProcess:
    """Run a shell command and return the CompletedProcess result."""
    return subprocess.run(
        cmd,
        input=stdin_data if stdin_data else None,
        capture_output=True,
        text=True,
        timeout=30,
    )


# ─────────────────────────────────────────────
# FUNCTION 1 — Availability Check
# ─────────────────────────────────────────────
def check_chaos_mesh_available() -> bool:
    """
    Check whether Chaos Mesh is installed and running on the cluster.

    Runs: kubectl get pods -n chaos-mesh
    Returns True  if pods are found with 'chaos' in their names.
    Returns False otherwise (Chaos Mesh absent or cluster unreachable).
    """
    try:
        result = _run(["kubectl", "get", "pods", "-n", CHAOS_NAMESPACE])
        available = result.returncode == 0 and "chaos" in result.stdout.lower()
        if available:
            print("[CHAOS] OK  Chaos Mesh available")
        else:
            print("[CHAOS] WARN Chaos Mesh not found - running in fallback mode")
        return available
    except Exception as exc:
        print(f"[CHAOS] WARN Could not reach cluster: {exc}")
        return False


# ─────────────────────────────────────────────
# FUNCTION 2 — Core Injection
# ─────────────────────────────────────────────
def inject_chaos(service: str, scenario: str) -> Dict[str, Any]:
    """
    Inject a chaos experiment into *service* using the named *scenario*.

    Steps:
      1. Validate service and scenario.
      2. Reject critical services.
      3. Read YAML manifest and substitute SERVICE_PLACEHOLDER.
      4. Apply via ``kubectl apply -f -`` (piped stdin).

    Args:
        service:  Name of the target microservice (must be in ALL_SERVICES).
        scenario: Chaos scenario key (must be in SCENARIO_MANIFEST).

    Returns:
        dict with keys: success, service, scenario, timestamp, method,
        duration_seconds — or error keys on failure.
    """
    # ── Validate ─────────────────────────────
    if service not in ALL_SERVICES:
        return {
            "success": False,
            "reason": "unknown_service",
            "service": service,
            "valid_services": ALL_SERVICES,
        }

    if scenario not in SCENARIO_MANIFEST:
        return {
            "success": False,
            "reason": "unknown_scenario",
            "scenario": scenario,
            "valid_scenarios": list(SCENARIO_MANIFEST.keys()),
        }

    # ── Guard critical services ───────────────
    if service in CRITICAL_SERVICES:
        print(f"[CHAOS] BLOCK Blocked: '{service}' is a critical service.")
        return {
            "success": False,
            "reason": "critical_service_protected",
            "service": service,
        }

    # ── Load manifest ─────────────────────────
    yaml_file, kind, resource_name = SCENARIO_MANIFEST[scenario]
    manifest_path = os.path.join(MANIFESTS_DIR, yaml_file)

    try:
        with open(manifest_path, "r", encoding="utf-8") as fh:
            manifest_content = fh.read()
    except FileNotFoundError:
        return {
            "success": False,
            "reason": "manifest_not_found",
            "path": manifest_path,
        }

    # ── Substitute placeholder ────────────────
    manifest_content = manifest_content.replace("SERVICE_PLACEHOLDER", service)

    # ── Apply via kubectl ─────────────────────
    print(f"[CHAOS] GO Injecting '{scenario}' into '{service}'...")
    try:
        result = _run(["kubectl", "apply", "-f", "-"], stdin_data=manifest_content)
    except subprocess.TimeoutExpired:
        return {"success": False, "reason": "kubectl_timeout", "service": service, "scenario": scenario}

    if result.returncode != 0:
        return {
            "success": False,
            "reason": "kubectl_apply_failed",
            "service": service,
            "scenario": scenario,
            "stderr": result.stderr.strip(),
        }

    duration = 30 if scenario == "pod_kill" else 60
    print(f"[CHAOS] OK '{scenario}' injected into '{service}' for {duration}s.")
    return {
        "success": True,
        "service": service,
        "scenario": scenario,
        "timestamp": _now_iso(),
        "method": "chaos_mesh",
        "duration_seconds": duration,
        "resource_name": resource_name,
    }


# ─────────────────────────────────────────────
# FUNCTION 3 — Cleanup Single Scenario
# ─────────────────────────────────────────────
def cleanup_chaos(scenario: str) -> Dict[str, Any]:
    """
    Delete the Chaos Mesh resource for a given scenario.

    Args:
        scenario: The scenario key whose resource should be removed.

    Returns:
        dict with keys: success, scenario (and error info on failure).
    """
    if scenario not in SCENARIO_MANIFEST:
        return {"success": False, "reason": "unknown_scenario", "scenario": scenario}

    _, kind, resource_name = SCENARIO_MANIFEST[scenario]
    crd_type = _KIND_TO_CRD.get(kind, kind.lower())

    print(f"[CHAOS] CLEAN Cleaning up '{scenario}' ({crd_type}/{resource_name})...")
    try:
        result = _run([
            "kubectl", "delete", crd_type, resource_name,
            "-n", CHAOS_NAMESPACE,
            "--ignore-not-found",
        ])
    except subprocess.TimeoutExpired:
        return {"success": False, "reason": "kubectl_timeout", "scenario": scenario}
    except FileNotFoundError:
        return {"success": False, "reason": "kubectl_not_found", "scenario": scenario}
    except Exception as exc:
        return {"success": False, "reason": str(exc), "scenario": scenario}

    if result.returncode != 0:
        return {
            "success": False,
            "reason": "kubectl_delete_failed",
            "scenario": scenario,
            "stderr": result.stderr.strip(),
        }

    print(f"[CHAOS] OK Cleaned up '{scenario}'.")
    return {"success": True, "scenario": scenario}


# ─────────────────────────────────────────────
# FUNCTION 4 — Cleanup All Scenarios
# ─────────────────────────────────────────────
def cleanup_all() -> Dict[str, Any]:
    """
    Delete Chaos Mesh resources for all 5 scenarios.

    Returns:
        dict: cleaned (count), total (count), scenarios (list of results).
    """
    print("[CHAOS] CLEAN Cleaning up ALL chaos experiments...")
    results: List[Dict[str, Any]] = []
    for scenario in SCENARIO_MANIFEST:
        results.append(cleanup_chaos(scenario))

    cleaned = sum(1 for r in results if r.get("success"))
    print(f"[CHAOS] OK Cleanup complete: {cleaned}/{len(results)} removed.")
    return {
        "cleaned": cleaned,
        "total": len(results),
        "scenarios": results,
    }


# ─────────────────────────────────────────────
# FUNCTION 5 — Fallback Pod Kill (kubectl only)
# ─────────────────────────────────────────────
def fallback_pod_kill(service: str) -> Dict[str, Any]:
    """
    Kill a pod belonging to *service* using plain kubectl (no Chaos Mesh).

    Used when Chaos Mesh is unavailable and scenario is 'pod_kill'.

    Args:
        service: Name of the microservice whose pod will be deleted.

    Returns:
        dict with keys: success, pod_deleted, service, method.
    """
    print(f"[CHAOS] FALLBACK kubectl pod kill for '{service}'...")
    try:
        # Step 1: find the first pod
        get_result = _run([
            "kubectl", "get", "pods",
            "-n", NAMESPACE,
            "-l", f"app={service}",
            "-o", "jsonpath={.items[0].metadata.name}",
        ])

        if get_result.returncode != 0 or not get_result.stdout.strip():
            return {
                "success": False,
                "reason": "pod_not_found",
                "service": service,
                "method": "kubectl_fallback",
            }

        pod_name = get_result.stdout.strip()

        # Step 2: delete the pod
        del_result = _run(["kubectl", "delete", "pod", pod_name, "-n", NAMESPACE])

        if del_result.returncode != 0:
            return {
                "success": False,
                "reason": "pod_delete_failed",
                "service": service,
                "method": "kubectl_fallback",
                "stderr": del_result.stderr.strip(),
            }

        print(f"[CHAOS] OK Fallback: deleted pod '{pod_name}'.")
        return {
            "success": True,
            "pod_deleted": pod_name,
            "service": service,
            "timestamp": _now_iso(),
            "method": "kubectl_fallback",
        }

    except subprocess.TimeoutExpired:
        return {"success": False, "reason": "kubectl_timeout", "service": service, "method": "kubectl_fallback"}
    except FileNotFoundError:
        return {"success": False, "reason": "kubectl_not_found", "service": service, "method": "kubectl_fallback"}
    except Exception as exc:
        return {"success": False, "reason": str(exc), "service": service, "method": "kubectl_fallback"}


# ─────────────────────────────────────────────
# FUNCTION 6 — Main Entry Point (Safe Wrapper)
# ─────────────────────────────────────────────
def inject_chaos_safe(service: str, scenario: str) -> Dict[str, Any]:
    """
    **Primary entry point** for all chaos injection.

    Logic:
      - If Chaos Mesh is available → call inject_chaos().
      - If Chaos Mesh is NOT available AND scenario == 'pod_kill'
        → call fallback_pod_kill().
      - If Chaos Mesh is NOT available AND scenario != 'pod_kill'
        → return {success: False, reason: "chaos_mesh_required_for_this_scenario"}.

    Args:
        service:  Target microservice name.
        scenario: Chaos scenario key.

    Returns:
        dict describing result.  Always contains 'success' bool.
    """
    print(f"[CHAOS] >> inject_chaos_safe({service!r}, {scenario!r})")

    # Guard critical services early (before Chaos Mesh check)
    if service in CRITICAL_SERVICES:
        return {
            "success": False,
            "reason": "critical_service_protected",
            "service": service,
        }

    chaos_mesh_up = check_chaos_mesh_available()

    if chaos_mesh_up:
        return inject_chaos(service, scenario)

    # Fallback path
    if scenario == "pod_kill":
        print("[CHAOS] FALLBACK Chaos Mesh unavailable - using kubectl fallback for pod_kill.")
        return fallback_pod_kill(service)

    print(f"[CHAOS] ERROR Chaos Mesh unavailable and '{scenario}' requires Chaos Mesh.")
    return {
        "success": False,
        "reason": "chaos_mesh_required_for_this_scenario",
        "scenario": scenario,
        "service": service,
    }


# ─────────────────────────────────────────────
# QUICK SELF-TEST (run as script)
# ─────────────────────────────────────────────
if __name__ == "__main__":
    import json as _json

    print("\n=== KubeResilience Chaos Engine Self-Test ===\n")

    print("[1] Checking Chaos Mesh...")
    available = check_chaos_mesh_available()

    print("\n[2] Testing critical service guard...")
    result = inject_chaos_safe("frontend", "pod_kill")
    print(_json.dumps(result, indent=2))

    print("\n[3] Dry-run: inject pod_kill into cartservice...")
    result = inject_chaos_safe("cartservice", "pod_kill")
    print(_json.dumps(result, indent=2))

    print("\n[4] Cleanup all...")
    result = cleanup_all()
    print(_json.dumps(result, indent=2))

    print("\n=== Self-test complete ===")
