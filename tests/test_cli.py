"""CLI integration tests using a saved snapshot (no live cluster needed)."""

from __future__ import annotations

import json

from typer.testing import CliRunner

from gpuctl.cli import app
from gpuctl.models import ClusterSnapshot, NodeInfo

runner = CliRunner()


def _write_ready_snapshot(path):
    snap = ClusterSnapshot(
        reachable=True,
        server_version="v1.31.4",
        nodes=[
            NodeInfo(
                name="gpu-1",
                labels={"nvidia.com/gpu.present": "true"},
                taints=[{"key": "nvidia.com/gpu", "effect": "NoSchedule"}],
                allocatable={"nvidia.com/gpu": "1"},
            )
        ],
        pods=[],
    )
    path.write_text(snap.to_json(), encoding="utf-8")


def test_version():
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert "gpuctl" in result.stdout


def test_preflight_from_file_json(tmp_path):
    snap = tmp_path / "snap.json"
    _write_ready_snapshot(snap)
    result = runner.invoke(app, ["preflight", "--from-file", str(snap), "-o", "json"])
    # GPU node present but no operator pods in the snapshot -> critical fail.
    assert result.exit_code == 1
    payload = json.loads(result.stdout)
    assert payload["state"] == "missing_operator"


def test_preflight_unreachable_exit_code(tmp_path):
    snap = tmp_path / "unreachable.json"
    ClusterSnapshot(reachable=False, error="refused")
    snap.write_text(
        json.dumps({"reachable": False, "error": "connection refused"}), encoding="utf-8"
    )
    result = runner.invoke(app, ["preflight", "--from-file", str(snap)])
    assert result.exit_code == 1
    assert "unreachable" in result.stdout


def test_preflight_text_output(tmp_path):
    snap = tmp_path / "snap.json"
    _write_ready_snapshot(snap)
    result = runner.invoke(app, ["preflight", "--from-file", str(snap)])
    assert "GPU Kubernetes preflight" in result.stdout
    assert "api-connectivity" in result.stdout
