# chaos/README.md

# KubeResilience Chaos Engine 🛡️💥

A production-safe chaos engineering module for the **Online Boutique** microservice app running on Kubernetes. Integrates with **Chaos Mesh** for advanced failure injection with an automatic `kubectl` fallback for pod kills.

---

## 📋 Quick Start

```bash
cd kuberesilience-backend
pip install -r requirements.txt

# Test Chaos Mesh connectivity
python -c "from chaos.chaos_engine import check_chaos_mesh_available; check_chaos_mesh_available()"

# Inject a pod kill into cartservice
python -c "
from chaos.chaos_engine import inject_chaos_safe
import json
print(json.dumps(inject_chaos_safe('cartservice', 'pod_kill'), indent=2))
"

# Cleanup everything
python -c "from chaos.chaos_engine import cleanup_all; cleanup_all()"
```

---

## ✅ Prerequisites

| Tool | Version | Purpose |
|------|---------|---------|
| Python | 3.11+ | Engine runtime |
| kubectl | any | Cluster interaction |
| Chaos Mesh | v2.x | Advanced chaos injection |
| Prometheus | v2.x | Observability & alerting |
| Kubernetes | 1.25+ | Target cluster |

### Install Chaos Mesh (if not installed)

```bash
helm repo add chaos-mesh https://charts.chaos-mesh.org
helm install chaos-mesh chaos-mesh/chaos-mesh \
  --namespace=chaos-mesh \
  --create-namespace \
  --set chaosDaemon.runtime=containerd \
  --set chaosDaemon.socketPath=/run/containerd/containerd.sock
```

---

## 📁 Folder Structure

```
chaos/
├── __init__.py           # Public exports
├── chaos_engine.py       # Core logic (6 functions)
├── README.md             # This file
└── manifests/
    ├── pod_kill.yaml         # PodChaos (30s)
    ├── cpu_stress.yaml       # StressChaos 90% CPU (60s)
    ├── memory_stress.yaml    # StressChaos 256MB RAM (60s)
    ├── network_latency.yaml  # NetworkChaos 300ms delay (60s)
    └── packet_loss.yaml      # NetworkChaos 45% loss (60s)
```

---

## 🔥 The 5 Chaos Scenarios

| Scenario | What Breaks | Duration | Impact |
|----------|------------|----------|--------|
| `pod_kill` | Kills one pod | 30s | Tests K8s self-healing |
| `cpu_stress` | 90% CPU on 4 workers | 60s | Tests latency detection |
| `memory_stress` | 256MB RAM fill | 60s | Tests memory monitoring |
| `network_latency` | 300ms ± 50ms delay | 60s | Tests timeout handling |
| `packet_loss` | 45% packet drop | 60s | Tests retry logic |

---

## 🐍 API Reference

### `check_chaos_mesh_available() -> bool`
Tests connectivity to Chaos Mesh.  
Returns `True` if running, `False` if absent.

### `inject_chaos_safe(service: str, scenario: str) -> dict` ← **Main Entry**
Primary entry point. Uses Chaos Mesh if available; falls back to kubectl for `pod_kill`.

### `inject_chaos(service: str, scenario: str) -> dict`
Direct Chaos Mesh injection (requires Chaos Mesh to be running).

### `cleanup_chaos(scenario: str) -> dict`
Deletes the Chaos Mesh resource for a single scenario.

### `cleanup_all() -> dict`
Deletes Chaos Mesh resources for all 5 scenarios.

### `fallback_pod_kill(service: str) -> dict`
Kill a pod using plain kubectl (no Chaos Mesh required).

---

## 🌐 FastAPI Integration (Dhruv's Routes)

```python
from chaos.chaos_engine import inject_chaos_safe, cleanup_all

@app.post("/api/chaos/inject")
async def inject_chaos_api(service: str, scenario: str):
    return inject_chaos_safe(service, scenario)

@app.post("/api/chaos/cleanup")
async def cleanup_api():
    return cleanup_all()
```

### Example cURL Requests

```bash
# Inject CPU stress into paymentservice
curl -X POST "http://localhost:8000/api/chaos/inject?service=paymentservice&scenario=cpu_stress"

# Inject pod kill into cartservice
curl -X POST "http://localhost:8000/api/chaos/inject?service=cartservice&scenario=pod_kill"

# Cleanup all
curl -X POST "http://localhost:8000/api/chaos/cleanup"
```

---

## 🧪 Testing

```bash
# Run full test suite
pytest tests/test_chaos_engine.py -v

# With coverage report
pytest tests/test_chaos_engine.py -v --cov=chaos --cov-report=term-missing
```

### Manual Verification Steps

```bash
# 1. Check Chaos Mesh
python -c "from chaos.chaos_engine import check_chaos_mesh_available; check_chaos_mesh_available()"

# 2. Inject pod_kill into cartservice
python -c "
from chaos.chaos_engine import inject_chaos_safe
import json
print(json.dumps(inject_chaos_safe('cartservice', 'pod_kill'), indent=2))
"
# Verify: kubectl get podchaos -n chaos-mesh

# 3. Verify running pod restarted
kubectl get pods -n boutique -l app=cartservice

# 4. Cleanup all
python -c "
from chaos.chaos_engine import cleanup_all
import json
print(json.dumps(cleanup_all(), indent=2))
"
# Verify: kubectl get podchaos,stresschaos,networkchaos -n chaos-mesh
```

---

## 🛡️ Safety Rules

1. **Protected services** — `frontend` & `checkoutservice` can never be attacked.  
2. **One experiment at a time** — always call `cleanup_all()` before starting a new injection.  
3. **Auto-expiry** — experiments expire after 30s (pod_kill) or 60s (all others). Still call cleanup explicitly.  
4. **Local clusters only** — verify your context before running.
   ```bash
   kubectl config current-context
   # Should be: kind-kuberesience, docker-desktop, or minikube
   ```

---

## 🔧 Troubleshooting

| Issue | Fix |
|-------|-----|
| `Chaos Mesh not found` | Install Chaos Mesh via Helm |
| `Pod not found` | Check boutique namespace: `kubectl get pods -n boutique` |
| `Permission denied` | Apply `k8s/rbac.yaml` |
| `YAML syntax error` | `kubectl apply -f chaos/manifests/pod_kill.yaml --dry-run=client` |
| `Import error` | Run from `kuberesilience-backend/` directory |

---

## 📄 License

MIT — built for KubeResilience chaos engineering project.
