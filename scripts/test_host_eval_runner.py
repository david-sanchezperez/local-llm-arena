"""Self-check mínimo: las llamadas HTTP al tablero de agent-loops y la extracción del
candidato, sin tocar GPU/red real."""
import json
from unittest.mock import MagicMock, patch

import host_eval_runner as runner


def test_fetch_ready_tasks_filters_by_board_tenant_status():
    fake_resp = MagicMock(json=lambda: [{"id": "t1"}], raise_for_status=lambda: None)
    with patch("host_eval_runner.requests.get", return_value=fake_resp) as mock_get:
        tasks = runner.fetch_ready_tasks()
    assert tasks == [{"id": "t1"}]
    _, kwargs = mock_get.call_args
    assert kwargs["params"] == {"board": "local-llm-arena", "tenant": "host_gpu", "status": "ready"}


def test_fetch_ready_tasks_returns_empty_when_board_missing():
    fake_resp = MagicMock(status_code=404)
    with patch("host_eval_runner.requests.get", return_value=fake_resp):
        assert runner.fetch_ready_tasks() == []


def test_claim_returns_true_on_200():
    with patch("host_eval_runner.requests.post", return_value=MagicMock(status_code=200)):
        assert runner.claim("t1") is True


def test_claim_returns_false_on_conflict():
    with patch("host_eval_runner.requests.post", return_value=MagicMock(status_code=409)):
        assert runner.claim("t1") is False


def test_report_posts_comment_with_author():
    with patch("host_eval_runner.requests.post", return_value=MagicMock()) as mock_post:
        runner.report("t1", "veredicto")
    _, kwargs = mock_post.call_args
    assert kwargs["json"] == {"comment": "veredicto", "author": "host-gpu-runner"}


def _fake_litellm_response(content: str) -> MagicMock:
    resp = MagicMock()
    resp.json.return_value = {"choices": [{"message": {"content": content}}]}
    resp.raise_for_status = lambda: None
    return resp


def test_extract_candidate_parses_hf_repo_and_filename():
    payload = json.dumps({"hf_repo": "unsloth/Qwen3.8-27B-GGUF", "gguf_filename": "Qwen3.8-27B-UD-Q4_K_XL.gguf"})
    with patch("host_eval_runner.requests.post", return_value=_fake_litellm_response(payload)) as mock_post:
        candidate = runner.extract_candidate("prueba Qwen3.8-27B en la 3090")
    assert candidate == {"hf_repo": "unsloth/Qwen3.8-27B-GGUF", "gguf_filename": "Qwen3.8-27B-UD-Q4_K_XL.gguf"}
    _, kwargs = mock_post.call_args
    assert kwargs["json"]["model"] == "deepseek-v4-flash"


def test_extract_candidate_none_when_not_identifiable():
    payload = json.dumps({"hf_repo": None, "gguf_filename": None})
    with patch("host_eval_runner.requests.post", return_value=_fake_litellm_response(payload)):
        assert runner.extract_candidate("nota vaga sin modelo concreto") is None


def test_draft_verdict_uses_checker_model(tmp_path):
    with patch("host_eval_runner.requests.post", return_value=_fake_litellm_response("veredicto en prosa")) as mock_post:
        verdict = runner.draft_verdict("qwen3.8-27b", tmp_path)
    assert verdict == "veredicto en prosa"
    _, kwargs = mock_post.call_args
    assert kwargs["json"]["model"] == "claude-sonnet-5"


def test_draft_verdict_falls_back_on_checker_failure(tmp_path):
    import requests as _requests
    with patch("host_eval_runner.requests.post", side_effect=_requests.RequestException("caido")):
        verdict = runner.draft_verdict("qwen3.8-27b", tmp_path)
    assert "revisar" in verdict.lower() or "falló" in verdict.lower()


def test_process_task_reports_cleanly_when_extractor_fails():
    # regresión: extract_candidate() vive fuera del try/except de process_task --
    # una respuesta malformada del extractor no debe tumbar el poller entero
    # (la tarea ya esta 'claimed', sin report() se queda huerfana para siempre).
    with patch("host_eval_runner.claim", return_value=True), \
         patch("host_eval_runner.extract_candidate", side_effect=json.JSONDecodeError("x", "y", 0)), \
         patch("host_eval_runner.report") as mock_report:
        runner.process_task({"id": "t1", "body": "algo"})
    mock_report.assert_called_once()
    args, _ = mock_report.call_args
    assert args[0] == "t1"
    assert "extract" in args[1].lower() or "candidato" in args[1].lower()


if __name__ == "__main__":
    import tempfile
    from pathlib import Path as _Path

    test_fetch_ready_tasks_filters_by_board_tenant_status()
    test_fetch_ready_tasks_returns_empty_when_board_missing()
    test_claim_returns_true_on_200()
    test_claim_returns_false_on_conflict()
    test_report_posts_comment_with_author()
    test_extract_candidate_parses_hf_repo_and_filename()
    test_extract_candidate_none_when_not_identifiable()
    with tempfile.TemporaryDirectory() as d:
        test_draft_verdict_uses_checker_model(_Path(d))
    with tempfile.TemporaryDirectory() as d:
        test_draft_verdict_falls_back_on_checker_failure(_Path(d))
    print("OK")
