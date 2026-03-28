import os
import subprocess
import json
from datetime import datetime
from typing import Dict, Any

# ============================================================================
# CONSTANTS
# ============================================================================

NAMESPACE = "boutique"
CHAOS_NAMESPACE = "chaos-mesh"

# Services we cannot break
CRITICAL_SERVICES = ["frontend", "checkoutservice"]

# All services in Online Boutique
ALL_SERVICES = [
    "frontend",
    "cartservice",
    "checkoutservice",
    "paymentservice",
    "emailservice",
    "productcatalogservice",
    "recommendationservice",
    "currencyservice",
    "shippingservice",
    "adservice"
]

# Path to YAML manifests
MANIFESTS_DIR = os.path.join(os.path.dirname(__file__), "manifests")

# Maps scenario names to (yaml_file, chaos_kind, resource_name)
SCENARIO_MANIFEST = {
    "pod_kill": ("pod_kill.yaml", "PodChaos", "kuberesilience-pod-kill"),
    "cpu_stress": ("cpu_stress.yaml", "StressChaos", "kuberesilience-cpu-stress"),
    "memory_stress": ("memory_stress.yaml", "StressChaos", "kuberesilience-memory-stress"),
    "network_latency": ("network_latency.yaml", "NetworkChaos", "kuberesilience-network-latency"),
    "packet_loss": ("packet_loss.yaml", "NetworkChaos", "kuberesilience-packet-loss"),
}

# ============================================================================
# FUNCTION 1: Check if Chaos Mesh is available
# ============================================================================

def check_chaos_mesh_available() -> bool:
    """
    Check if Chaos Mesh is running and accessible.
    
    Returns:
        True if Chaos Mesh pods are running, False otherwise
    """
    try:
        result = subprocess.run(
            ["kubectl", "get", "pods", "-n", "chaos-mesh"],
            capture_output=True,
            text=True,
            timeout=5
        )
        
        if result.returncode == 0 and "chaos" in result.stdout:
            print("✅ Chaos Mesh available")
            return True
        else:
            print("⚠️  Chaos Mesh not found — fallback mode active")
            return False
    except Exception as e:
        print(f"⚠️  Chaos Mesh check failed ({e}) — fallback mode active")
        return False

# ============================================================================
# FUNCTION 2: Inject chaos (core logic)
# ============================================================================

def inject_chaos(service: str, scenario: str) -> Dict[str, Any]:
    """
    Inject a chaos scenario into a service using Chaos Mesh.
    
    Args:
        service: Target service name (e.g., 'cartservice')
        scenario: Chaos scenario (e.g., 'pod_kill', 'cpu_stress')
    
    Returns:
        Dictionary with success status and details
    """
    # Validation: Is this a known service?
    if service not in ALL_SERVICES:
        return {
            "success": False,
            "reason": "unknown_service",
            "service": service
        }
    
    # Validation: Is this a known scenario?
    if scenario not in SCENARIO_MANIFEST:
        return {
            "success": False,
            "reason": "unknown_scenario",
            "scenario": scenario
        }
    
    # Safety: Don't break critical services
    if service in CRITICAL_SERVICES:
        return {
            "success": False,
            "reason": "critical_service_protected",
            "service": service
        }
    
    try:
        # Get the YAML file path
        yaml_filename, _, _ = SCENARIO_MANIFEST[scenario]
        manifest_path = os.path.join(MANIFESTS_DIR, yaml_filename)
        
        # Read the YAML file
        with open(manifest_path, 'r') as f:
            yaml_content = f.read()
        
        # Replace SERVICE_PLACEHOLDER with actual service name
        modified_yaml = yaml_content.replace("SERVICE_PLACEHOLDER", service)
        
        # Apply the manifest via kubectl
        result = subprocess.run(
            ["kubectl", "apply", "-f", "-"],
            input=modified_yaml,
            capture_output=True,
            text=True,
            timeout=10
        )
        
        # Check if it succeeded
        if result.returncode != 0:
            return {
                "success": False,
                "reason": result.stderr
            }
        
        # Success! Print confirmation
        print(f"[CHAOS] ✅ Injected {scenario} into {service}")
        
        # Return success response
        return {
            "success": True,
            "service": service,
            "scenario": scenario,
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "method": "chaos_mesh",
            "duration_seconds": 60
        }
    
    except Exception as e:
        return {
            "success": False,
            "reason": str(e)
        }

# ============================================================================
# FUNCTION 3: Cleanup a single scenario
# ============================================================================

def cleanup_chaos(scenario: str) -> Dict[str, Any]:
    """
    Clean up a specific chaos scenario.
    
    Args:
        scenario: Chaos scenario to remove
    
    Returns:
        Dictionary with cleanup status
    """
    if scenario not in SCENARIO_MANIFEST:
        return {
            "success": False,
            "reason": "unknown_scenario",
            "scenario": scenario
        }
    
    try:
        _, chaos_kind, resource_name = SCENARIO_MANIFEST[scenario]
        
        # Convert kind to lowercase kubectl resource name
        kind_map = {
            "PodChaos": "podchaos",
            "StressChaos": "stresschaos",
            "NetworkChaos": "networkchaos"
        }
        
        kubectl_kind = kind_map[chaos_kind]
        
        # Delete the resource
        result = subprocess.run(
            ["kubectl", "delete", kubectl_kind, resource_name, 
             "-n", "chaos-mesh", "--ignore-not-found"],
            capture_output=True,
            text=True,
            timeout=10
        )
        
        print(f"[CHAOS] 🧹 Cleaned up {scenario}")
        
        return {
            "success": result.returncode == 0,
            "scenario": scenario
        }
    
    except Exception as e:
        return {
            "success": False,
            "reason": str(e),
            "scenario": scenario
        }

# ============================================================================
# FUNCTION 4: Cleanup all scenarios
# ============================================================================

def cleanup_all() -> Dict[str, Any]:
    """
    Clean up all active chaos scenarios.
    
    Returns:
        Dictionary with cleanup stats
    """
    results = []
    success_count = 0
    
    for scenario in SCENARIO_MANIFEST.keys():
        result = cleanup_chaos(scenario)
        results.append(result)
        if result.get("success"):
            success_count += 1
    
    return {
        "cleaned": success_count,
        "total": len(SCENARIO_MANIFEST),
        "scenarios": results
    }

# ============================================================================
# FUNCTION 5: Fallback pod kill (kubectl only)
# ============================================================================

def fallback_pod_kill(service: str) -> Dict[str, Any]:
    """
    Fallback pod kill using kubectl directly (when Chaos Mesh unavailable).
    
    Args:
        service: Target service
    
    Returns:
        Dictionary with kill status
    """
    try:
        # Step 1: Get the first pod of the service
        get_pod_result = subprocess.run(
            ["kubectl", "get", "pods", "-n", "boutique", 
             "-l", f"app={service}", 
             "-o", "jsonpath={.items[0].metadata.name}"],
            capture_output=True,
            text=True,
            timeout=5
        )
        
        if get_pod_result.returncode != 0:
            return {
                "success": False,
                "reason": "could_not_find_pod",
                "service": service,
                "method": "kubectl_fallback"
            }
        
        pod_name = get_pod_result.stdout.strip()
        if not pod_name:
            return {
                "success": False,
                "reason": "no_pods_found",
                "service": service,
                "method": "kubectl_fallback"
            }
        
        # Step 2: Delete the pod
        delete_result = subprocess.run(
            ["kubectl", "delete", "pod", pod_name, "-n", "boutique"],
            capture_output=True,
            text=True,
            timeout=5
        )
        
        success = delete_result.returncode == 0
        
        print(f"[CHAOS] ⚡ Fallback pod kill: {pod_name}")
        
        return {
            "success": success,
            "pod_deleted": pod_name,
            "service": service,
            "method": "kubectl_fallback"
        }
    
    except Exception as e:
        return {
            "success": False,
            "reason": str(e),
            "service": service,
            "method": "kubectl_fallback"
        }

# ============================================================================
# FUNCTION 5: Main entry point (called by FastAPI)
# ============================================================================

def inject_chaos_safe(service: str, scenario: str) -> Dict[str, Any]:
    """
    Main function called by FastAPI routes.
    
    Intelligently chooses:
    - Chaos Mesh if available
    - kubectl fallback if only pod_kill is requested
    - Error if Chaos Mesh needed but unavailable
    
    Args:
        service: Target service name
        scenario: Chaos scenario
    
    Returns:
        Injection result dictionary
    """
    # Check if Chaos Mesh is available
    mesh_available = check_chaos_mesh_available()
    
    if mesh_available:
        # Use Chaos Mesh
        return inject_chaos(service, scenario)
    else:
        # Mesh is down. Can we fallback?
        if scenario == "pod_kill":
            # Only scenario we can handle without Chaos Mesh
            return fallback_pod_kill(service)
        else:
            # Need Chaos Mesh for this scenario
            return {
                "success": False,
                "reason": "chaos_mesh_required_for_this_scenario",
                "scenario": scenario
            }
