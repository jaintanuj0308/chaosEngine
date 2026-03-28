import os
import random
import time
from kubernetes import client, config, watch
import logging

# Configure Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class ChaosEngine:
    """Core logic for KubeResilience experiments."""
    
    def __init__(self):
        try:
            # Try loading in-cluster config (if running in a POD)
            config.load_incluster_config()
            logger.info("Loaded in-cluster Kubernetes config.")
        except config.ConfigException:
            # Fallback for local development
            config.load_kube_config()
            logger.info("Loaded local Kubernetes config.")
        
        self.v1 = client.CoreV1Api()
        self.apps_v1 = client.AppsV1Api()
        self.namespace = os.getenv("TARGET_NAMESPACE", "default")
    
    def list_pods(self):
        """Returns a list of pods in the target namespace."""
        logger.info(f"Listing pods in namespace: {self.namespace}")
        pods = self.v1.list_namespaced_pod(self.namespace)
        return [pod.metadata.name for pod in pods.items]
    
    def kill_random_pod(self, label_selector=None):
        """Selects and deletes a random pod from the namespace."""
        logger.info(f"Looking for pods to target... Selector: {label_selector}")
        
        if label_selector:
            pods = self.v1.list_namespaced_pod(self.namespace, label_selector=label_selector)
        else:
            pods = self.v1.list_namespaced_pod(self.namespace)
        
        if not pods.items:
            logger.warning("No pods found matching the criteria.")
            return False
        
        target = random.choice(pods.items)
        pod_name = target.metadata.name
        
        logger.warning(f"CHAOS: Deleting pod {pod_name}...")
        self.v1.delete_namespaced_pod(pod_name, self.namespace)
        logger.info(f"Pod {pod_name} successfully terminated.")
        return True

    def run_experiment(self, duration_seconds=60, interval_seconds=10):
        """Runs the chaos experiment over a specified duration."""
        logger.info(f"Starting Experiment: {duration_seconds}s total, every {interval_seconds}s.")
        start_time = time.time()
        
        while time.time() - start_time < duration_seconds:
            self.kill_random_pod()
            time.sleep(interval_seconds)
            
        logger.info("Resilience test complete.")

if __name__ == "__main__":
    engine = ChaosEngine()
    # Simple example: run for 30s, ogni 5s
    engine.run_experiment(30, 5)
