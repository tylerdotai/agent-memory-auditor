from pathlib import Path

from memory_auditor.collectors import collect_hermes_documents
from memory_auditor.models import AuditContext
from memory_auditor.scanners.registry import run_scanners

FIXTURE = Path(__file__).parent / "fixtures" / "hermes"


def findings():
    docs = collect_hermes_documents(FIXTURE, include_skills=True)
    return run_scanners(docs, AuditContext(root=FIXTURE))


def categories():
    return {f.category for f in findings()}


def test_secret_like_strings_are_redacted():
    secret = [f for f in findings() if f.category == "secret-like"]
    assert secret
    assert "example-sensitive-value" not in secret[0].snippet
    assert "[REDACTED" in secret[0].snippet


def test_imperative_memory_detected():
    assert "imperative-memory" in categories()


def test_stale_task_progress_detected():
    assert "stale-task-progress" in categories()


def test_duplicate_near_duplicate_detected():
    assert "duplicate-memory" in categories()


def test_repo_path_mismatch_detected():
    assert "repo-path-missing" in categories()


def test_naming_drift_detected():
    assert "naming-drift" in categories()


def test_skill_candidate_detected():
    assert "skill-candidate" in categories()
