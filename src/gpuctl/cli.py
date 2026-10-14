"""Command-line entry point for gpuctl.

Commands:

* ``gpuctl preflight``  - run checks against a live cluster (or a saved snapshot).
* ``gpuctl snapshot``   - capture a cluster snapshot to JSON for offline analysis.

Exit codes: 0 = healthy, 1 = a critical check failed, 2 = warnings only.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import typer

from gpuctl import __version__
from gpuctl.checks import classify, exit_code, run_all_checks
from gpuctl.models import ClusterSnapshot
from gpuctl.report import render_json, render_text

app = typer.Typer(
    add_completion=False,
    help="Preflight and validation for GPU-aware Kubernetes clusters.",
    no_args_is_help=True,
)


def _version_callback(value: bool) -> None:
    if value:
        typer.echo(f"gpuctl {__version__}")
        raise typer.Exit()


@app.callback()
def main(
    _version: bool = typer.Option(
        False, "--version", callback=_version_callback, is_eager=True, help="Show version and exit."
    ),
) -> None:
    """GPU-aware Kubernetes preflight CLI."""


def _load_snapshot(
    from_file: Path | None,
    kubeconfig: str | None,
    context: str | None,
    operator_namespace: str,
    timeout: int,
) -> ClusterSnapshot:
    if from_file is not None:
        data = json.loads(from_file.read_text(encoding="utf-8"))
        return ClusterSnapshot.from_dict(data)
    # Import here so `--from-file` works without the kubernetes client.
    from gpuctl.kube import collect_snapshot

    return collect_snapshot(
        kubeconfig=kubeconfig,
        context=context,
        operator_namespace=operator_namespace,
        timeout=timeout,
    )


@app.command()
def preflight(
    output: str = typer.Option("text", "--output", "-o", help="Output format: text or json."),
    operator_namespace: str = typer.Option(
        "gpu-operator", "--operator-namespace", help="Namespace where the GPU Operator runs."
    ),
    kubeconfig: str | None = typer.Option(None, help="Path to a kubeconfig file."),
    context: str | None = typer.Option(None, help="kubeconfig context to use."),
    timeout: int = typer.Option(15, help="Per-request API timeout in seconds."),
    from_file: Path | None = typer.Option(
        None, "--from-file", help="Analyze a snapshot JSON instead of a live cluster."
    ),
) -> None:
    """Run all preflight checks and report cluster readiness."""

    snapshot = _load_snapshot(from_file, kubeconfig, context, operator_namespace, timeout)
    results = run_all_checks(snapshot, operator_namespace=operator_namespace)
    state = classify(snapshot, results)

    if output == "json":
        typer.echo(render_json(results, state))
    elif output == "text":
        typer.echo(render_text(results, state))
    else:
        typer.echo(f"Unknown output format: {output}", err=True)
        raise typer.Exit(code=2)

    raise typer.Exit(code=exit_code(results))


@app.command()
def snapshot(
    out: Path = typer.Option(Path("snapshot.json"), "--out", help="Where to write the snapshot."),
    operator_namespace: str = typer.Option("gpu-operator", "--operator-namespace"),
    kubeconfig: str | None = typer.Option(None, help="Path to a kubeconfig file."),
    context: str | None = typer.Option(None, help="kubeconfig context to use."),
    timeout: int = typer.Option(15, help="Per-request API timeout in seconds."),
) -> None:
    """Capture a cluster snapshot to JSON for offline analysis or sharing."""

    from gpuctl.kube import collect_snapshot

    snap = collect_snapshot(
        kubeconfig=kubeconfig,
        context=context,
        operator_namespace=operator_namespace,
        timeout=timeout,
    )
    out.write_text(snap.to_json(), encoding="utf-8")
    typer.echo(f"Wrote snapshot to {out} (reachable={snap.reachable}).")
    if not snap.reachable:
        sys.exit(1)


if __name__ == "__main__":
    app()
