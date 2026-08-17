"""Self-check mínimo: construcción del comando `tb run` y manejo de errores
(timeout, results.json ausente), sin lanzar Docker de verdad."""
import json
import subprocess
from unittest.mock import MagicMock, patch

import terminal_bench_eval as tbe

MODEL = {"id": "qwen3", "model_name": "qwen3.8-27b", "base_url": "http://localhost:8082/v1", "api_key": "sk-x"}


def test_run_one_parses_results_json(tmp_path, monkeypatch):
    monkeypatch.setattr(tbe, "RUNS_DIR", tmp_path)
    out_dir = tmp_path / f"{MODEL['id']}-{__import__('os').getpid()}"
    out_dir.mkdir()
    (out_dir / "results.json").write_text(json.dumps({"n_resolved": 7, "n_unresolved": 3, "accuracy": 0.7}))
    with patch("terminal_bench_eval.subprocess.run", return_value=MagicMock(returncode=0)):
        result = tbe.run_one(MODEL, n_tasks=10, agent="terminus-2", timeout_s=60)
    assert result == {"n_resolved": 7, "n_unresolved": 3, "accuracy": 0.7}


def test_run_one_reports_missing_results_json(tmp_path, monkeypatch):
    monkeypatch.setattr(tbe, "RUNS_DIR", tmp_path)
    with patch("terminal_bench_eval.subprocess.run", return_value=MagicMock(returncode=1)):
        result = tbe.run_one(MODEL, n_tasks=10, agent="terminus-2", timeout_s=60)
    assert "error" in result


def test_run_one_reports_timeout(tmp_path, monkeypatch):
    monkeypatch.setattr(tbe, "RUNS_DIR", tmp_path)
    with patch("terminal_bench_eval.subprocess.run", side_effect=subprocess.TimeoutExpired(cmd="tb", timeout=60)):
        result = tbe.run_one(MODEL, n_tasks=10, agent="terminus-2", timeout_s=60)
    assert "timeout" in result["error"]


def test_run_one_uses_fixed_task_ids_not_n_tasks_when_given():
    with patch("terminal_bench_eval.subprocess.run", return_value=MagicMock(returncode=1)) as mock_run:
        tbe.run_one(MODEL, n_tasks=10, agent="terminus-2", timeout_s=60, task_ids=["foo", "bar"])
    cmd = mock_run.call_args.args[0]
    assert "--task-id" in cmd
    assert "foo" in cmd and "bar" in cmd
    assert "--n-tasks" not in cmd


def test_run_one_uses_openai_prefixed_model_and_api_base():
    with patch("terminal_bench_eval.subprocess.run", return_value=MagicMock(returncode=1)) as mock_run:
        tbe.run_one(MODEL, n_tasks=5, agent="terminus-2", timeout_s=60)
    cmd = mock_run.call_args.args[0]
    assert "openai/qwen3.8-27b" in cmd
    assert f"api_base={MODEL['base_url']}" in cmd
    assert tbe.DATASET in cmd  # version fija — ver comentario junto a DATASET


if __name__ == "__main__":
    import tempfile
    from pathlib import Path as _Path

    class _MonkeyPatch:
        def setattr(self, obj, name, value):
            setattr(obj, name, value)

    mp = _MonkeyPatch()
    with tempfile.TemporaryDirectory() as d:
        test_run_one_parses_results_json(_Path(d), mp)
    with tempfile.TemporaryDirectory() as d:
        test_run_one_reports_missing_results_json(_Path(d), mp)
    with tempfile.TemporaryDirectory() as d:
        test_run_one_reports_timeout(_Path(d), mp)
    test_run_one_uses_fixed_task_ids_not_n_tasks_when_given()
    test_run_one_uses_openai_prefixed_model_and_api_base()
    print("OK")
