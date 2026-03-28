import uvicorn
from fastapi import FastAPI, HTTPException
from typing import Dict, Any

from chaos.chaos_engine import inject_chaos_safe, cleanup_all

app = FastAPI(
    title="KubeResilience Chaos API",
    description="API for injecting controlled chaos into the Online Boutique microservices.",
    version="1.0.0"
)


@app.post("/api/chaos/inject")
async def inject_chaos_api(service: str, scenario: str) -> Dict[str, Any]:
    """
    Inject a chaos scenario into a specified service.
    
    Supported scenarios: pod_kill, cpu_stress, memory_stress, network_latency, packet_loss
    """
    result = inject_chaos_safe(service, scenario)
    if not result.get("success"):
        # Let's return a 400 Bad Request if it failed for predictable reasons,
        # but technically we could just return the dict too.
        # We'll just return the dict directly so the frontend can parse the "reason".
        return result
    return result

@app.post("/api/chaos/cleanup")
async def cleanup_api() -> Dict[str, Any]:
    """
    Remove all active Chaos Mesh scenarios and clean up.
    """
    return cleanup_all()

@app.get("/health")
async def health_check() -> Dict[str, str]:
    return {"status": "ok"}

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
