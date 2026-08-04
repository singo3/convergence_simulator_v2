"""Code/spec fingerprint and strict resume-match tests."""

from __future__ import annotations

from dataclasses import replace

import pytest

from symbiotic_sim_v2.experiments.fatigue_sigma_auto_search import fingerprint
from symbiotic_sim_v2.experiments.fatigue_sigma_auto_search.fingerprint import (
    AUTO_SEARCH_CODE_CHANGED,
    CodeFingerprint,
    CodeFingerprintError,
)


def _capture(monkeypatch, *, status="", head="a" * 40):
    def fake_git(_root, *arguments):
        if arguments[0] == "status":
            return status
        if arguments == ("rev-parse", "HEAD"):
            return head
        raise AssertionError(arguments)

    monkeypatch.setattr(fingerprint, "_git", fake_git)
    return CodeFingerprint.capture(fingerprint.NORMATIVE_SPEC_PATH.parent)


def test_clean_repository_fingerprint_has_all_required_fields(monkeypatch) -> None:
    result = _capture(monkeypatch)
    body = result.to_dict()
    assert body["git_head_sha"] == "a" * 40
    assert body["working_tree_clean"] is True
    assert body["project_version"] == "0.12.0"
    assert body["stage_08a1_project_version"] == "0.11.0"
    assert body["normative_spec_sha256"] == fingerprint.NORMATIVE_SPEC_SHA256
    assert body["python_version"]
    assert body["platform"]
    assert len(body["fingerprint_digest"]) == 64


def test_dirty_repository_is_rejected_by_default(monkeypatch) -> None:
    monkeypatch.setattr(fingerprint, "_git", lambda *_args: " M source.py")
    with pytest.raises(CodeFingerprintError, match=AUTO_SEARCH_CODE_CHANGED):
        CodeFingerprint.capture(fingerprint.NORMATIVE_SPEC_PATH.parent)


def test_explicit_development_override_records_dirty(monkeypatch) -> None:
    def fake_git(_root, *arguments):
        return " M source.py" if arguments[0] == "status" else "a" * 40

    monkeypatch.setattr(fingerprint, "_git", fake_git)
    result = CodeFingerprint.capture(
        fingerprint.NORMATIVE_SPEC_PATH.parent,
        allow_dirty=True,
    )
    assert result.working_tree_clean is False


@pytest.mark.parametrize(
    ("field", "value"),
    (
        ("git_head_sha", "b" * 40),
        ("working_tree_clean", False),
        ("project_version", "future"),
        ("python_version", "future"),
        ("platform", "future"),
        ("normative_spec_sha256", "0" * 64),
    ),
)
def test_each_resume_fingerprint_change_is_rejected(monkeypatch, field, value) -> None:
    original = _capture(monkeypatch)
    changed = replace(original, **{field: value})
    with pytest.raises(CodeFingerprintError, match=AUTO_SEARCH_CODE_CHANGED):
        original.require_match(changed)


def test_fingerprint_dict_detects_attached_digest_tampering(monkeypatch) -> None:
    body = _capture(monkeypatch).to_dict()
    body["fingerprint_digest"] = "0" * 64
    with pytest.raises(CodeFingerprintError, match="digest mismatch"):
        CodeFingerprint.from_dict(body)


@pytest.mark.parametrize(
    ("size", "sha"),
    (
        (1, fingerprint.NORMATIVE_SPEC_SHA256),
        (fingerprint.NORMATIVE_SPEC_SIZE, "0" * 64),
    ),
)
def test_spec_fingerprint_change_stops_new_run(monkeypatch, size, sha) -> None:
    monkeypatch.setattr(fingerprint, "_git", lambda *_args: "")
    monkeypatch.setattr(fingerprint, "_sha256_file", lambda _path: sha)
    monkeypatch.setattr(fingerprint, "NORMATIVE_SPEC_SIZE", size)
    with pytest.raises(CodeFingerprintError, match="SPEC_CHANGED"):
        CodeFingerprint.capture(fingerprint.NORMATIVE_SPEC_PATH.parent)
