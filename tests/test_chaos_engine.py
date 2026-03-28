"""
tests/test_chaos_engine.py
==========================
Pytest suite for chaos/chaos_engine.py.
Uses unittest.mock.patch so no real Kubernetes cluster is needed.

Function-based test names match the spec from the guide:
  test_check_chaos_mesh_available_true
  test_check_chaos_mesh_available_false
  test_inject_chaos_valid_service
  test_inject_chaos_protected_service
  test_inject_chaos_unknown_service
  test_inject_chaos_unknown_scenario
  test_cleanup_chaos_single
  test_cleanup_all
  test_fallback_pod_kill_success
  test_fallback_pod_kill_failure
  test_inject_chaos_safe_with_mesh
  test_inject_chaos_safe_without_mesh
  + extra edge-case tests for full coverage
"""

import pytest
from unittest.mock import MagicMock, patch
from unittest import mock


# ─────────────────────────────────────────────────────────────────────────────
# Helpers — fake CompletedProcess results
# ─────────────────────────────────────────────────────────────────────────────
def _ok(stdout: str = "ok", stderr: str = "") -> MagicMock:
    m = MagicMock()
    m.returncode = 0
    m.stdout = stdout
    m.stderr = stderr
    return m


def _fail(stderr: str = "error occurred") -> MagicMock:
    m = MagicMock()
    m.returncode = 1
    m.stdout = ""
    m.stderr = stderr
    return m


# Internal _run patch path
RUN = "chaos.chaos_engine._run"


# ─────────────────────────────────────────────────────────────────────────────
# 1. check_chaos_mesh_available — TRUE path
# ─────────────────────────────────────────────────────────────────────────────
@patch(RUN, return_value=_ok(stdout="chaos-controller-manager Running"))
def test_check_chaos_mesh_available_true(_mock):
    from chaos.chaos_engine import check_chaos_mesh_available
    result = check_chaos_mesh_available()
    assert result is True


# ─────────────────────────────────────────────────────────────────────────────
# 2. check_chaos_mesh_available — FALSE path
# ─────────────────────────────────────────────────────────────────────────────
@patch(RUN, return_value=_ok(stdout="No resources found"))
def test_check_chaos_mesh_available_false(_mock):
    from chaos.chaos_engine import check_chaos_mesh_available
    result = check_chaos_mesh_available()
    assert result is False


@patch(RUN, return_value=_fail())
def test_check_chaos_mesh_available_kubectl_fail(_mock):
    from chaos.chaos_engine import check_chaos_mesh_available
    result = check_chaos_mesh_available()
    assert result is False


@patch(RUN, side_effect=Exception("cluster unreachable"))
def test_check_chaos_mesh_available_exception(_mock):
    from chaos.chaos_engine import check_chaos_mesh_available
    result = check_chaos_mesh_available()
    assert result is False


# ─────────────────────────────────────────────────────────────────────────────
# 3. inject_chaos — valid service
# ─────────────────────────────────────────────────────────────────────────────
@patch(RUN, return_value=_ok(stdout="podchaos.chaos-mesh.org/... created"))
def test_inject_chaos_valid_service(_mock):
    from chaos.chaos_engine import inject_chaos
    result = inject_chaos("cartservice", "pod_kill")
    assert result["success"] is True
    assert result["service"] == "cartservice"
    assert result["scenario"] == "pod_kill"
    assert result["method"] == "chaos_mesh"
    assert result["duration_seconds"] == 30
    assert "timestamp" in result
    assert "resource_name" in result


@patch(RUN, return_value=_ok())
def test_inject_chaos_non_pod_kill_duration_60(_mock):
    """All non-pod_kill scenarios return 60s duration."""
    from chaos.chaos_engine import inject_chaos
    for scenario in ["cpu_stress", "memory_stress", "network_latency", "packet_loss"]:
        result = inject_chaos("adservice", scenario)
        assert result.get("duration_seconds") == 60, f"{scenario} should have 60s"


# ─────────────────────────────────────────────────────────────────────────────
# 4. inject_chaos — protected service (critical_service_protected)
# ─────────────────────────────────────────────────────────────────────────────
def test_inject_chaos_protected_service():
    from chaos.chaos_engine import inject_chaos
    for svc in ["frontend", "checkoutservice"]:
        result = inject_chaos(svc, "pod_kill")
        assert result["success"] is False
        assert result["reason"] == "critical_service_protected"
        assert result["service"] == svc


# ─────────────────────────────────────────────────────────────────────────────
# 5. inject_chaos — unknown service
# ─────────────────────────────────────────────────────────────────────────────
def test_inject_chaos_unknown_service():
    from chaos.chaos_engine import inject_chaos
    result = inject_chaos("alien-service", "pod_kill")
    assert result["success"] is False
    assert result["reason"] == "unknown_service"
    assert "valid_services" in result


# ─────────────────────────────────────────────────────────────────────────────
# 6. inject_chaos — unknown scenario
# ─────────────────────────────────────────────────────────────────────────────
def test_inject_chaos_unknown_scenario():
    from chaos.chaos_engine import inject_chaos
    result = inject_chaos("cartservice", "supernova_blast")
    assert result["success"] is False
    assert result["reason"] == "unknown_scenario"
    assert "valid_scenarios" in result


@patch(RUN, return_value=_fail(stderr="RBAC denied"))
def test_inject_chaos_kubectl_fails(_mock):
    from chaos.chaos_engine import inject_chaos
    result = inject_chaos("cartservice", "pod_kill")
    assert result["success"] is False
    assert result["reason"] == "kubectl_apply_failed"
    assert "stderr" in result


# ─────────────────────────────────────────────────────────────────────────────
# 7. cleanup_chaos — single scenario
# ─────────────────────────────────────────────────────────────────────────────
@patch(RUN, return_value=_ok(stdout='podchaos "kuberesilience-pod-kill" deleted'))
def test_cleanup_chaos_single(_mock):
    from chaos.chaos_engine import cleanup_chaos
    result = cleanup_chaos("pod_kill")
    assert result["success"] is True
    assert result["scenario"] == "pod_kill"


def test_cleanup_chaos_unknown_scenario():
    from chaos.chaos_engine import cleanup_chaos
    result = cleanup_chaos("unknown_thing")
    assert result["success"] is False
    assert result["reason"] == "unknown_scenario"


@patch(RUN, return_value=_fail())
def test_cleanup_chaos_kubectl_fails(_mock):
    from chaos.chaos_engine import cleanup_chaos
    result = cleanup_chaos("cpu_stress")
    assert result["success"] is False
    assert result["reason"] == "kubectl_delete_failed"


# ─────────────────────────────────────────────────────────────────────────────
# 8. cleanup_all — all 5 scenarios
# ─────────────────────────────────────────────────────────────────────────────
@patch(RUN, return_value=_ok(stdout="deleted"))
def test_cleanup_all(_mock):
    from chaos.chaos_engine import cleanup_all, SCENARIO_MANIFEST
    result = cleanup_all()
    assert result["total"] == len(SCENARIO_MANIFEST)  # 5
    assert result["cleaned"] == 5
    assert len(result["scenarios"]) == 5
    for r in result["scenarios"]:
        assert r["success"] is True


@patch(RUN, return_value=_fail())
def test_cleanup_all_partial_failure(_mock):
    from chaos.chaos_engine import cleanup_all
    result = cleanup_all()
    assert result["cleaned"] == 0
    assert result["total"] == 5


# ─────────────────────────────────────────────────────────────────────────────
# 9. fallback_pod_kill — success
# ─────────────────────────────────────────────────────────────────────────────
@patch(RUN)
def test_fallback_pod_kill_success(mock_run):
    mock_run.side_effect = [
        _ok(stdout="cartservice-abc-123"),
        _ok(stdout='pod "cartservice-abc-123" deleted'),
    ]
    from chaos.chaos_engine import fallback_pod_kill
    result = fallback_pod_kill("cartservice")
    assert result["success"] is True
    assert result["pod_deleted"] == "cartservice-abc-123"
    assert result["service"] == "cartservice"
    assert result["method"] == "kubectl_fallback"
    assert "timestamp" in result


# ─────────────────────────────────────────────────────────────────────────────
# 10. fallback_pod_kill — failure (no pod found)
# ─────────────────────────────────────────────────────────────────────────────
@patch(RUN, return_value=_ok(stdout=""))  # empty output = no pod
def test_fallback_pod_kill_failure(_mock):
    from chaos.chaos_engine import fallback_pod_kill
    result = fallback_pod_kill("cartservice")
    assert result["success"] is False
    assert result["reason"] == "pod_not_found"
    assert result["method"] == "kubectl_fallback"


@patch(RUN)
def test_fallback_pod_kill_delete_fails(mock_run):
    mock_run.side_effect = [
        _ok(stdout="some-pod"),
        _fail(stderr="delete failed"),
    ]
    from chaos.chaos_engine import fallback_pod_kill
    result = fallback_pod_kill("cartservice")
    assert result["success"] is False
    assert result["reason"] == "pod_delete_failed"


# ─────────────────────────────────────────────────────────────────────────────
# 11. inject_chaos_safe — WITH Chaos Mesh (mesh delegates to inject_chaos)
# ─────────────────────────────────────────────────────────────────────────────
@patch("chaos.chaos_engine.inject_chaos")
@patch("chaos.chaos_engine.check_chaos_mesh_available", return_value=True)
def test_inject_chaos_safe_with_mesh(_avail, mock_inject):
    mock_inject.return_value = {"success": True, "method": "chaos_mesh", "service": "cartservice"}
    from chaos.chaos_engine import inject_chaos_safe
    result = inject_chaos_safe("cartservice", "pod_kill")
    mock_inject.assert_called_once_with("cartservice", "pod_kill")
    assert result["success"] is True
    assert result["method"] == "chaos_mesh"


# ─────────────────────────────────────────────────────────────────────────────
# 12. inject_chaos_safe — WITHOUT Chaos Mesh (fallback for pod_kill)
# ─────────────────────────────────────────────────────────────────────────────
@patch("chaos.chaos_engine.fallback_pod_kill")
@patch("chaos.chaos_engine.check_chaos_mesh_available", return_value=False)
def test_inject_chaos_safe_without_mesh(_avail, mock_fallback):
    mock_fallback.return_value = {"success": True, "method": "kubectl_fallback"}
    from chaos.chaos_engine import inject_chaos_safe
    result = inject_chaos_safe("cartservice", "pod_kill")
    mock_fallback.assert_called_once_with("cartservice")
    assert result["success"] is True
    assert result["method"] == "kubectl_fallback"


@patch("chaos.chaos_engine.check_chaos_mesh_available", return_value=False)
def test_inject_chaos_safe_without_mesh_non_pod_kill(_avail):
    """Non pod_kill scenarios must fail gracefully without Chaos Mesh."""
    from chaos.chaos_engine import inject_chaos_safe
    for scenario in ["cpu_stress", "memory_stress", "network_latency", "packet_loss"]:
        result = inject_chaos_safe("cartservice", scenario)
        assert result["success"] is False
        assert result["reason"] == "chaos_mesh_required_for_this_scenario"


# ─────────────────────────────────────────────────────────────────────────────
# 13. Critical service guard fires BEFORE Chaos Mesh check
# ─────────────────────────────────────────────────────────────────────────────
def test_inject_chaos_safe_critical_service_blocked():
    from chaos.chaos_engine import inject_chaos_safe
    result = inject_chaos_safe("frontend", "pod_kill")
    assert result["success"] is False
    assert result["reason"] == "critical_service_protected"


def test_inject_chaos_safe_checkoutservice_blocked():
    from chaos.chaos_engine import inject_chaos_safe
    result = inject_chaos_safe("checkoutservice", "cpu_stress")
    assert result["success"] is False
    assert result["reason"] == "critical_service_protected"


# ─────────────────────────────────────────────────────────────────────────────
# 14. Constants sanity checks
# ─────────────────────────────────────────────────────────────────────────────
def test_all_services_count():
    from chaos.chaos_engine import ALL_SERVICES
    assert len(ALL_SERVICES) == 10


def test_critical_services_in_all_services():
    from chaos.chaos_engine import ALL_SERVICES, CRITICAL_SERVICES
    for svc in CRITICAL_SERVICES:
        assert svc in ALL_SERVICES


def test_scenario_manifest_has_5_entries():
    from chaos.chaos_engine import SCENARIO_MANIFEST
    assert len(SCENARIO_MANIFEST) == 5


def test_scenario_manifest_tuple_structure():
    from chaos.chaos_engine import SCENARIO_MANIFEST
    for key, val in SCENARIO_MANIFEST.items():
        assert len(val) == 3, f"{key!r} tuple must have 3 elements"
