from types import SimpleNamespace

import pytest

import scripts.slga_build_swaz_artifact as build_script


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
