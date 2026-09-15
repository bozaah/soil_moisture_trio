import json
from dataclasses import fields, replace
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest
import xarray as xr

import scripts.slga_build_swaz_artifact as build_script
from src.soil_moisture_trio.slga import artifact as artifact_module
from src.soil_moisture_trio.slga.artifact import load_soil_artifact
from src.soil_moisture_trio.slga.cog import ReaderMetrics
from src.soil_moisture_trio.slga.grid import sha256_file
from test_slga_artifact import _write_contracts
from test_slga_checkpoint import _full_data, _stripe


def test_clean_git_commit_is_required(monkeypatch):
    responses = iter(
        [
            SimpleNamespace(stdout="/repo\n"),
            SimpleNamespace(stdout="a" * 40 + "\n"),
            SimpleNamespace(stdout=""),
        ]
    )
    monkeypatch.setattr(
        build_script.subprocess,
        "run",
        lambda *_args, **_kwargs: next(responses),
    )

    assert build_script._require_clean_git_commit() == "a" * 40

    dirty = iter(
        [
            SimpleNamespace(stdout="/repo\n"),
            SimpleNamespace(stdout="a" * 40 + "\n"),
            SimpleNamespace(stdout=" M changed.py\n"),
        ]
    )
    monkeypatch.setattr(
        build_script.subprocess,
        "run",
        lambda *_args, **_kwargs: next(dirty),
    )
    with pytest.raises(RuntimeError, match="clean Git worktree"):
        build_script._require_clean_git_commit()


def test_runtime_limit_stops_between_stripes_and_preserves_resume_message(monkeypatch):
    monkeypatch.setattr(build_script.time, "perf_counter", lambda: 11.0)

    with pytest.raises(TimeoutError, match="2/16.*retained for resume"):
        build_script._require_runtime_remaining(1.0, 10.0, 2, 16)


def test_unknown_checkpoint_entries_fail(tmp_path):
    (tmp_path / "stripe_0000").mkdir()
    (tmp_path / "unexpected").mkdir()

    with pytest.raises(RuntimeError, match="unexpected entries"):
        build_script._reject_unknown_checkpoint_entries(tmp_path, 2)


@pytest.mark.parametrize("failure", ["timeout", "source", "publication"])
def test_builder_interruption_resume_verified_publication_and_cleanup(monkeypatch, tmp_path, failure):
    """Mock source work only. Exercise real checkpoints, assembly, bundle I/O and loader."""
    source_path, contract_path, grid = _write_contracts(tmp_path / "inputs")
    full = _full_data()  # Two non-trivial 2-row stripes, with real float-valued fields.
    contract = json.loads(contract_path.read_text())
    contract["coordinate_contract"]["approved_swaz_artifact_footprint"].update({
        "latitude_last": float(full.latitude[-1]), "latitude_length": 4, "cell_count": 12,
    })
    contract_path.write_text(json.dumps(contract))
    grid = replace(grid, latitude=full.latitude, contract_sha256=sha256_file(contract_path))
    catalogue = SimpleNamespace(
        manifest_id="synthetic_sources_v1", sha256=sha256_file(source_path),
        layers={"AWC_TEST": None, "DES_TEST": None},
    )
    args = SimpleNamespace(
        awral_grid_input=tmp_path / "unused.nc",
        bundle_dir=tmp_path / "resumed",
        checkpoint_dir=tmp_path / "checkpoints",
        max_runtime_seconds=10.0, resume=True, keep_checkpoints=False,
    )
    monkeypatch.setattr(build_script, "parse_args", lambda: args)
    monkeypatch.setattr(build_script, "_require_clean_git_commit", lambda: "a" * 40)
    monkeypatch.setattr(build_script, "load_canonical_grid", lambda path: grid)
    monkeypatch.setattr(build_script, "load_source_catalogue", lambda path: catalogue)
    monkeypatch.setattr(build_script, "DEFAULT_GRID_CONTRACT_PATH", contract_path)
    monkeypatch.setattr(build_script, "SOURCE_MANIFEST_PATH", source_path)
    monkeypatch.setattr(build_script, "STRIPE_ROWS", 2)
    monkeypatch.setattr(build_script, "AuthenticatedCogReader", lambda *a, **k: object())
    monkeypatch.delenv("TERN_API_KEY", raising=False)
    clock = SimpleNamespace(now=0.0)
    monkeypatch.setattr(build_script, "time", SimpleNamespace(perf_counter=lambda: clock.now))
    calls = []
    injected = {"active": True}
    metrics = ReaderMetrics(**{field.name: 0 for field in fields(ReaderMetrics)})

    def build(catalogue, reader, latitude, longitude, **kwargs):
        first = int(np.flatnonzero(full.latitude == latitude[0])[0])
        calls.append(first)
        if injected["active"] and failure == "source" and first == 2:
            raise OSError("simulated source interruption")
        clock.now += 11 if injected["active"] and failure == "timeout" else 1
        return SimpleNamespace(
            artifact_data=_stripe(full, slice(first, first + len(latitude))),
            reader_counter_delta={"cog_window_fetches": 2},
            reader_metrics_after=metrics, source_window_reads=2, tile_metrics=(),
            source_retrieval_timestamps_utc={
                "AWC_TEST": "2026-09-11T01:00:00Z", "DES_TEST": "2026-09-11T01:00:00Z",
            },
        )
    monkeypatch.setattr(build_script, "build_tiled_artifact_data", build)
    rename = artifact_module.os.rename
    def rename_with_failure(source, destination):
        if injected["active"] and failure == "publication" and Path(destination) == args.bundle_dir:
            raise OSError("simulated publication interruption")
        return rename(source, destination)
    monkeypatch.setattr(artifact_module.os, "rename", rename_with_failure)

    with pytest.raises((TimeoutError, OSError)):
        build_script.main()
    assert not args.bundle_dir.exists()
    assert not list(tmp_path.glob(".resumed.*.staging"))
    completed = 2 if failure == "publication" else 1
    assert len(list(args.checkpoint_dir.glob("stripe_*"))) == completed
    first_checkpoint = args.checkpoint_dir / "stripe_0000"
    before = {path.name: path.read_bytes() for path in first_checkpoint.iterdir()}

    # A changed commit must fail before source work, without deleting completed work.
    calls_before = list(calls)
    monkeypatch.setattr(build_script, "_require_clean_git_commit", lambda: "b" * 40)
    with pytest.raises(ValueError, match="identity mismatch"):
        build_script.main()
    assert calls == calls_before
    assert {path.name: path.read_bytes() for path in first_checkpoint.iterdir()} == before
    monkeypatch.setattr(build_script, "_require_clean_git_commit", lambda: "a" * 40)

    injected["active"] = False
    clock.now = 0.0
    build_script.main()
    # Completed stripes were reused, not fetched again. Failed stripe retries are allowed.
    assert calls[len(calls_before):] == ([] if completed == 2 else [2])
    assert not args.checkpoint_dir.exists()
    resumed_bundle = args.bundle_dir
    artifact = resumed_bundle / build_script.DEFAULT_ARTIFACT_FILENAME
    sidecar = resumed_bundle / build_script.DEFAULT_SIDECAR_FILENAME
    report = json.loads((resumed_bundle / build_script.BUILD_REPORT_FILENAME).read_text())
    assert report["checkpoint_count"] == 2
    assert report["reader_counter_totals"] == {"cog_window_fetches": 4}
    assert report["target_cell_count"] == 12
    assert json.loads(sidecar.read_text())["artifact_sha256"] == sha256_file(artifact)
    resumed = load_soil_artifact(
        artifact, sidecar, full.latitude, full.longitude,
        source_manifest_path=source_path, grid_contract_path=contract_path,
    )
    with pytest.raises(FileExistsError, match="Immutable bundle"):
        build_script.main()

    # Compare all numerical output variables with an uninterrupted build.
    args.bundle_dir = tmp_path / "uninterrupted"
    args.checkpoint_dir = tmp_path / "fresh-checkpoints"
    clock.now = 0.0
    build_script.main()
    uninterrupted = load_soil_artifact(
        args.bundle_dir / build_script.DEFAULT_ARTIFACT_FILENAME,
        args.bundle_dir / build_script.DEFAULT_SIDECAR_FILENAME,
        full.latitude, full.longitude, source_manifest_path=source_path,
        grid_contract_path=contract_path,
    )
    xr.testing.assert_equal(resumed, uninterrupted)
    assert not args.checkpoint_dir.exists()
