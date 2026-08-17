#!/usr/bin/env python3
"""Poller del host: recoge tareas tenant=host_gpu del tablero de agent-loops para el
board 'local-llm-arena', evalúa el modelo candidato contra el campeón actual, y cierra
la tarea con un veredicto — NUNCA promociona nada a producción. Pensado para correr
periódicamente via un timer systemd --user (ver deploy/host-eval-runner.{service,timer}).

Reutiliza los helpers de candidate_bench.py (arranque/parada de llama-server,
stop/start de producción) y bench/run.py (perf+code+agent, humaneval opcional) — no
reimplementa el harness. Ver AGENTS.md (capability evaluate-llm-candidate) y
proj_qwen38_evaluacion.md para el precedente manual del 15/08/2026 del que sale esto.
"""
import json
import logging
import os
import subprocess
import sys
from pathlib import Path

import requests
import yaml

sys.path.insert(0, str(Path(__file__).parent))
from candidate_bench import (  # noqa: E402
    PORT, ROOT, CONFIG_PATH, RESULTS_DIR,
    start_server, stop_existing_server, stop_production, start_production, wait_ready,
)
from thermal_guard import ThermalGuard  # noqa: E402

log = logging.getLogger(__name__)

AGENT_LOOPS_URL = os.environ.get("AGENT_LOOPS_URL", "http://localhost:3000")
BOARD_SLUG = "local-llm-arena"
CANDIDATES_DIR = RESULTS_DIR / "candidates"
BENCH_PAUSE_S = os.environ.get("BENCH_PAUSE_S", "15")

EXTRACT_PROMPT = """Extrae de esta descripción de tarea el repo de Hugging Face y el \
fichero GGUF exactos del modelo candidato a evaluar. Responde SOLO JSON: \
{{"hf_repo": "<owner/repo>", "gguf_filename": "<archivo .gguf exacto o null si no se \
puede determinar>"}}. Si no hay información suficiente para identificar un modelo \
descargable, responde {{"hf_repo": null, "gguf_filename": null}}.

Tarea:
{task_body}
"""


def fetch_ready_tasks() -> list[dict]:
    resp = requests.get(
        f"{AGENT_LOOPS_URL}/api/tasks",
        params={"board": BOARD_SLUG, "tenant": "host_gpu", "status": "ready"},
        timeout=15,
    )
    if resp.status_code == 404:
        return []  # el board 'local-llm-arena' aun no existe (se crea con la primera tarea)
    resp.raise_for_status()
    return resp.json()


def claim(task_id: str) -> bool:
    resp = requests.post(f"{AGENT_LOOPS_URL}/api/tasks/{task_id}/claim-host", timeout=15)
    return resp.status_code == 200


def report(task_id: str, comment: str) -> None:
    requests.post(
        f"{AGENT_LOOPS_URL}/api/tasks/{task_id}/report",
        json={"comment": comment, "author": "host-gpu-runner"},
        timeout=15,
    )


def _litellm_chat(model: str, content: str, max_tokens: int, **extra) -> str:
    """Todas las llamadas a LLM del poller pasan por el proxy LiteLLM ya autenticado
    (mismo master key que usa el resto del stack) — el poller no necesita sus propias
    claves de API."""
    resp = requests.post(
        "http://localhost:4000/v1/chat/completions",
        headers={"Authorization": "Bearer sk-litellm-local"},
        json={"model": model, "messages": [{"role": "user", "content": content}], "max_tokens": max_tokens, **extra},
        timeout=120,
    )
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"]


def extract_candidate(task_body: str) -> dict | None:
    """Rol 'maker': deepseek barato convierte la prosa de la tarea en {hf_repo, gguf_filename}."""
    content = _litellm_chat(
        "deepseek-v4-flash", EXTRACT_PROMPT.format(task_body=task_body), 500,
        response_format={"type": "json_object"},
    )
    result = json.loads(content)
    return result if result.get("hf_repo") and result.get("gguf_filename") else None


def download_gguf(hf_repo: str, filename: str, dest_dir: Path) -> Path:
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / filename
    if dest.exists():
        return dest
    url = f"https://huggingface.co/{hf_repo}/resolve/main/{filename}"
    subprocess.run(["curl", "-L", "-o", str(dest), url], check=True)
    return dest


def write_candidate_config(candidate_id: str) -> None:
    cfg = {"models": [{
        "id": f"candidate-{candidate_id}",
        "label": f"Candidato host_eval: {candidate_id} (temporal, :{PORT})",
        "base_url": f"http://localhost:{PORT}/v1",
        "api_key": "sk-not-required",
        "model_name": candidate_id,
        "kind": "local",
    }]}
    CONFIG_PATH.write_text(yaml.dump(cfg, allow_unicode=True, sort_keys=False))


def run_battery(env_extra: dict) -> None:
    env = {**os.environ, **env_extra}
    subprocess.run(
        [sys.executable, "run.py", "--suites", "perf,code,agent", "--baseline", env_extra["BENCH_BASELINE"]],
        cwd=ROOT / "bench", env=env, check=False,
    )


def draft_verdict(candidate_id: str, results_dir: Path) -> str:
    """Rol 'checker': Sonnet (via LiteLLM) redacta el veredicto a partir de los datos crudos.
    Solo texto — nunca toca litellm_config.yaml ni systemd de producción."""
    files = {}
    for f in results_dir.glob("*.json"):
        try:
            files[f.stem] = json.loads(f.read_text())
        except json.JSONDecodeError:
            continue
    content = (
        f"Estos son los resultados crudos de evaluar el candidato '{candidate_id}' "
        f"contra el modelo en producción, con local-llm-arena "
        f"(perf.json, code_eval.json, agent_eval.json):\n\n{json.dumps(files, indent=2)}\n\n"
        "Redacta un veredicto corto en castellano: tabla comparativa, y una "
        "recomendación clara de si merece la pena promocionarlo o no. No apliques "
        "ningún cambio — esto es solo para que el humano decida."
    )
    try:
        return _litellm_chat("claude-sonnet-5", content, 1500)
    except requests.RequestException as exc:
        return f"Evaluación completada, datos en {results_dir}. El checker (Sonnet via LiteLLM) falló: {exc}. Revisar JSON a mano."


def process_task(task: dict) -> None:
    task_id = task["id"]
    if not claim(task_id):
        log.info("no se pudo reclamar %s (¿ya reclamada por otro poller?)", task_id)
        return

    try:
        candidate = extract_candidate(task.get("body") or "")
    except (requests.RequestException, json.JSONDecodeError) as exc:
        # extract_candidate llama a un LLM barato (deepseek-v4-flash) y parsea su
        # salida como JSON -- una respuesta truncada/malformada o LiteLLM caido no
        # deben tumbar el poller entero (main() no envuelve process_task en try/except,
        # y la tarea ya esta 'claimed': sin este report se queda huerfana para siempre).
        report(task_id, f"No se pudo extraer el candidato de la descripción de la tarea (fallo del extractor): {exc}. Revisar manualmente.")
        return
    if not candidate:
        report(task_id, "No se pudo identificar un repo/fichero GGUF concreto en la descripción de la tarea. Revisar manualmente.")
        return

    candidate_id = candidate["hf_repo"].split("/")[-1].lower()
    backup = CONFIG_PATH.read_text()
    guard = None
    proc = None
    try:
        gguf = download_gguf(candidate["hf_repo"], candidate["gguf_filename"], Path.home() / "models" / candidate_id)

        stop_existing_server()
        stop_production()
        log_path = CANDIDATES_DIR / f"{candidate_id}.server.log"
        CANDIDATES_DIR.mkdir(parents=True, exist_ok=True)
        proc = start_server(str(gguf), log_path)
        guard = ThermalGuard(port=PORT)
        guard.start()

        if not wait_ready():
            report(task_id, f"El servidor no arrancó a tiempo con {candidate_id}. Log: {log_path}")
            return

        write_candidate_config(candidate_id)
        out_dir = CANDIDATES_DIR / candidate_id
        out_dir.mkdir(exist_ok=True)
        run_battery({"BENCH_PAUSE_S": BENCH_PAUSE_S, "BENCH_BASELINE": f"candidate-{candidate_id}"})

        if guard.triggered:
            report(task_id, f"El guardarraíl térmico cortó la evaluación de {candidate_id} (GPU >= {guard.max_temp_c}°C). Resultados parciales en {out_dir}, revisar y relanzar si hace falta.")
            return

        for f in RESULTS_DIR.glob("*.json"):
            (out_dir / f.name).write_text(f.read_text())

        verdict = draft_verdict(candidate_id, out_dir)
        (out_dir / "verdict.md").write_text(verdict)
        report(task_id, verdict)
    except Exception as exc:
        log.exception("fallo evaluando %s", task_id)
        report(task_id, f"Evaluación de {candidate_id} falló con un error: {exc}")
    finally:
        CONFIG_PATH.write_text(backup)
        if guard is not None:
            guard.stop()
        if proc is not None:
            proc.terminate()
            try:
                proc.wait(timeout=15)
            except subprocess.TimeoutExpired:
                proc.kill()
        stop_existing_server()
        start_production()


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    tasks = fetch_ready_tasks()
    if not tasks:
        log.info("sin tareas host_gpu pendientes")
        return
    for task in tasks:
        process_task(task)


if __name__ == "__main__":
    main()
