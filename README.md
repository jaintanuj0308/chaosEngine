# KubeResilience Backend 🛡️

A powerful Kubernetes chaos engineering engine designed to test the resilience of your microservices.

## 🚀 Overview

KubeResilience allows you to define and execute chaos experiments directly on your Kubernetes clusters. Whether it's pod deletion, network stress, or resource starvation, this engine provides the tools to ensure your application can handle the unexpected.

## 📁 File Structure

```text
kuberesilience-backend/
├── src/
│   └── chaos_engine.py      # Core Python Logic
├── tests/
│   └── test_chaos_engine.py # Pytest Suite
├── k8s/                     # Kubernetes Manifests
│   ├── deployment.yaml
│   ├── service.yaml
│   ├── configmap.yaml
│   ├── rbac.yaml
│   └── chaos_profile.yaml   # Custom Resilience Config
├── docs/                    # Feature Docs
├── config/                  # local environment config
├── requirements.txt         # Dependencies
└── README.md                # This File
```

## 🛠️ Installation

1. Clone this repository:
   ```bash
   git clone https://github.com/your-repo/kuberesilience-backend.git
   cd kuberesilience-backend
   ```

2. Create a virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

## 🧪 Running Tests

To run the unit tests, use Pytest:

```bash
pytest tests/
```

## ☸️ Kubernetes Deployment

Deploy the engine to your cluster:

```bash
kubectl apply -f k8s/rbac.yaml
kubectl apply -f k8s/configmap.yaml
kubectl apply -f k8s/deployment.yaml
kubectl apply -f k8s/service.yaml
```

## 🛡️ License

MIT License
