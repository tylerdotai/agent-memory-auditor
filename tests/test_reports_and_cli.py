import json
import subprocess
import sys
from pathlib import Path

from memory_auditor.cli import run

FIXTURE = Path(__file__).parent / "fixtures" / "hermes"


def test_cli_writes_markdown_html_and_json(tmp_path):
    code = run(["scan", "--home", str(FIXTURE), "--include-skills", "--output-dir", str(tmp_path)])
    assert code == 1
    md = tmp_path / "memory-audit.md"
    html = tmp_path / "memory-audit.html"
    js = tmp_path / "memory-audit.json"
    assert md.exists()
    assert html.exists()
    assert js.exists()
    data = json.loads(js.read_text())
    assert data["summary"]["total"] > 0
    assert "example-sensitive-value" not in md.read_text()
    assert "Agent Memory Audit" in html.read_text()


def test_installed_module_help_works():
    result = subprocess.run(
        [sys.executable, "-m", "memory_auditor.cli", "--help"],
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0
    assert "memory-audit" in result.stdout
