#!/usr/bin/env python3
"""Sirve cada modelo candidato uno a uno en :8081 (sin tocar el qwen3 de
produccion en :8080), corre la bateria rapida (perf+code+agent) contra el,
y guarda los resultados en results/candidates/<id>/. No reimplementa el
harness, solo orquesta el swap de modelo + llamada a run.py."""
import argparse
import shutil
import subprocess
import sys
import time
from pathlib import Path

import requests
import yaml

ROOT = Path(__file__).parent.parent
CONFIG_PATH = ROOT / "config" / "models.yaml"
RESULTS_DIR = ROOT / "results"
CANDIDATES_DIR = RESULTS_DIR / "candidates"
LLAMA_SERVER = "/home/david/llama.cpp/build/bin/llama-server"
PORT = 8081

CANDIDATES = {
    "devstral": "/home/david/models/devstral/mistralai_Devstral-Small-2-24B-Instruct-2512-Q4_K_M.gguf",
    "glm4-32b": "/home/david/models/glm4-32b/THUDM_GLM-4-32B-0414-Q4_K_M.gguf",
    "qwen25-coder-32b": "/home/david/models/qwen25-coder-32b/Qwen2.5-Coder-32B-Instruct-Q4_K_M.gguf",
    "deepseek-coder-v2-lite": "/home/david/models/deepseek-coder-v2-lite/DeepSeek-Coder-V2-Lite-Instruct-Q4_K_M.gguf",
    "glimmer-30b": "/home/david/models/glimmer-30b/Muse-Glimmer-30B-UD-Q4_K_XL.gguf",
    "devstral-q6": "/home/david/models/devstral-q6/Devstral-Small-2-24B-Instruct-2512-UD-Q6_K_XL.gguf",
}


def stop_existing_server():
    subprocess.run(["pkill", "-f", f"llama-server.*--port {PORT}"], check=False)
    time.sleep(3)


def stop_production():
    """VRAM no da para produccion (qwen3, :8080, ~15.5GB) + un candidato de
    32B denso (~19-20GB) a la vez. Se para temporalmente durante el benchmark
    y se restaura siempre al terminar (ver finally en main)."""
    print("[prod] parando llama-server.service (qwen3, :8080) para liberar VRAM...")
    subprocess.run(["systemctl", "--user", "stop", "llama-server.service"], check=False)
    time.sleep(3)


def start_production():
    print("[prod] restaurando llama-server.service (qwen3, :8080)...")
    subprocess.run(["systemctl", "--user", "start", "llama-server.service"], check=False)
    start = time.time()
    while time.time() - start < 120:
        try:
            r = requests.get("http://localhost:8080/v1/models", timeout=3)
            if r.ok:
                print("[prod] qwen3 de vuelta y respondiendo en :8080")
                return True
        except requests.RequestException:
            pass
        time.sleep(3)
    print("[prod][AVISO] qwen3 no respondio en :8080 tras 120s, revisar systemctl --user status llama-server.service")
    return False


def start_server(gguf_path, log_path):
    log = open(log_path, "w")
    proc = subprocess.Popen(
        [
            LLAMA_SERVER,
            "-m", gguf_path,
            "--host", "0.0.0.0",
            "--port", str(PORT),
            "-ngl", "99",
            "-b", "512", "-ub", "512",
            "-fa", "on",
            "-c", "8192",
            "--jinja",
            "--log-disable",
        ],
        stdout=log,
        stderr=subprocess.STDOUT,
    )
    return proc


def wait_ready(timeout=300):
    start = time.time()
    while time.time() - start < timeout:
        try:
            r = requests.get(f"http://localhost:{PORT}/v1/models", timeout=3)
            if r.ok:
                return True
        except requests.RequestException:
            pass
        time.sleep(3)
    return False


def write_candidate_config(model_id):
    # Reemplaza el roster entero (no solo añade): produccion (:8080) esta parada
    # durante el benchmark, y run.py no filtra por is_alive antes de fallar
    # (perf.py hace raise_for_status y run.py corta con check=True), asi que
    # cualquier otro modelo listado rompe la corrida entera.
    cfg = {"models": [{
        "id": f"candidate-{model_id}",
        "label": f"Candidato: {model_id} (temporal, :8081)",
        "base_url": f"http://localhost:{PORT}/v1",
        "api_key": "sk-not-required",
        "model_name": model_id,
        "kind": "local",
    }]}
    CONFIG_PATH.write_text(yaml.dump(cfg, allow_unicode=True, sort_keys=False))


def restore_config(backup):
    CONFIG_PATH.write_text(backup)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", nargs="*", help="subset de ids a evaluar (por defecto todos)")
    ap.add_argument("--suites", default="perf,code,agent")
    args = ap.parse_args()

    ids = args.only or list(CANDIDATES.keys())
    backup = CONFIG_PATH.read_text()
    CANDIDATES_DIR.mkdir(parents=True, exist_ok=True)

    for model_id in ids:
        gguf = CANDIDATES[model_id]
        if not Path(gguf).exists():
            print(f"[skip] {model_id}: {gguf} no existe todavia")
            continue

        print(f"\n=== {model_id} ===")
        stop_existing_server()
        proc = None
        try:
            stop_production()
            log_path = CANDIDATES_DIR / f"{model_id}.server.log"
            proc = start_server(gguf, log_path)
            print("esperando a que llama-server cargue el modelo...")
            if not wait_ready():
                print(f"[error] {model_id}: llama-server no respondio a tiempo, ver {log_path}")
                continue

            write_candidate_config(model_id)
            out_dir = CANDIDATES_DIR / model_id
            out_dir.mkdir(exist_ok=True)

            result = subprocess.run(
                [sys.executable, "run.py", "--suites", args.suites, "--baseline", f"candidate-{model_id}"],
                cwd=ROOT / "bench",
                capture_output=True,
                text=True,
            )
            (out_dir / "run.stdout.log").write_text(result.stdout)
            (out_dir / "run.stderr.log").write_text(result.stderr)
            print(result.stdout[-2000:])

            for f in RESULTS_DIR.glob("*.json"):
                shutil.copy(f, out_dir / f.name)
            leaderboard = RESULTS_DIR / "leaderboard.md"
            if leaderboard.exists():
                shutil.copy(leaderboard, out_dir / "leaderboard.md")

        finally:
            restore_config(backup)
            if proc is not None:
                proc.terminate()
                try:
                    proc.wait(timeout=15)
                except subprocess.TimeoutExpired:
                    proc.kill()
            stop_existing_server()
            start_production()

    print("\n=== HECHO ===")
    print(f"Resultados por modelo en {CANDIDATES_DIR}/<id>/")


if __name__ == "__main__":
    main()
