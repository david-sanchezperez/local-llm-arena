#!/usr/bin/env python3
"""Bateria oficial: Terminal-Bench (laude-institute/terminal-bench), agentic terminal
coding real. No reimplementa el harness — orquesta el CLI oficial `tb run` (paquete
`terminal-bench`, requiere Docker) y traduce su results.json al formato del repo
({model_id: {...}} en results/terminal_bench_eval.json).

Requisitos: `pip install terminal-bench` (trae el CLI `tb`), Docker corriendo.
Cada tarea es mucho más pesada que un problema de HumanEval (agente multi-turno
en un sandbox real) — por defecto se corre una submuestra pequeña, no el dataset
completo (ver --n-tasks).
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

BENCH_DIR = Path(__file__).parent
ROOT = BENCH_DIR.parent
RESULTS = ROOT / "results"
RESULTS.mkdir(exist_ok=True)
RUNS_DIR = ROOT / ".cache" / "terminal-bench-runs"

sys.path.insert(0, str(BENCH_DIR))
from common import load_models, is_alive  # noqa: E402

DEFAULT_N_TASKS = 10
# Version fija: "terminal-bench-core" sin version resuelve al registro de forma
# poco fiable (visto el 15/08/2026: FileNotFoundError en el download del dataset).
# "==0.1.1" es la version soportada por terminal-bench >=0.2.4 (ver `tb datasets list`).
DATASET = "terminal-bench-core==0.1.1"


def run_one(model: dict, n_tasks: int, agent: str, timeout_s: int, task_ids: list[str] | None = None) -> dict:
    run_id = f"{model['id']}-{os.getpid()}"
    out_dir = RUNS_DIR / run_id
    env = {**os.environ, "OPENAI_API_KEY": model["api_key"]}
    cmd = [
        "tb", "run",
        "--dataset", DATASET,
        "--agent", agent,
        "--model", f"openai/{model['model_name']}",
        "--agent-kwarg", f"api_base={model['base_url']}",
        "--n-concurrent", "1",  # una GPU local: sin concurrencia, evita saturarla
        "--no-livestream",
        "--output-path", str(RUNS_DIR),
        "--run-id", run_id,
    ]
    if task_ids:
        # --task-id explicito, no --n-tasks: --n-tasks muestrea un subconjunto
        # DISTINTO en cada corrida (visto el 15/08/2026 comparando dos modelos
        # con --n-tasks 10 cada uno: solo 1 de 10 tareas coincidia). Para que la
        # comparacion entre modelos sea valida, hace falta la MISMA lista fija.
        for tid in task_ids:
            cmd += ["--task-id", tid]
    else:
        cmd += ["--n-tasks", str(n_tasks)]
    try:
        subprocess.run(cmd, env=env, cwd=ROOT, timeout=timeout_s, check=False, capture_output=True, text=True)
    except subprocess.TimeoutExpired:
        return {"error": f"timeout tras {timeout_s}s"}

    results_path = out_dir / "results.json"
    if not results_path.exists():
        return {"error": f"tb no generó {results_path} — ver logs en {out_dir}"}
    raw = json.loads(results_path.read_text())
    return {
        "n_resolved": raw.get("n_resolved"),
        "n_unresolved": raw.get("n_unresolved"),
        "accuracy": raw.get("accuracy"),
    }


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--n-tasks", type=int, default=DEFAULT_N_TASKS,
                     help=f"submuestra ALEATORIA de tareas (default {DEFAULT_N_TASKS}); "
                          "no reproducible entre corridas -- para comparar modelos usa --task-ids")
    ap.add_argument("--task-ids", type=str, default=None,
                     help="lista fija de task-id separados por coma (reproducible, recomendado al comparar modelos)")
    ap.add_argument("--agent", default="terminus-2", help="agente de terminal-bench a usar (default terminus-2)")
    ap.add_argument("--timeout-s", type=int, default=1800, help="timeout por modelo, en segundos")
    args = ap.parse_args()
    task_ids = [t.strip() for t in args.task_ids.split(",")] if args.task_ids else None

    if shutil.which("tb") is None:
        sys.exit("Falta el CLI 'tb'. Instala con: pip install terminal-bench (requiere Docker).")

    results = {}
    for model in load_models():
        if not is_alive(model):
            print(f"[skip] {model['id']}: no responde", file=sys.stderr)
            continue
        n_desc = f"task_ids={task_ids}" if task_ids else f"n_tasks={args.n_tasks} (aleatorio)"
        print(f"[run] {model['id']}... ({n_desc}, esto puede tardar)", file=sys.stderr)
        result = run_one(model, args.n_tasks, args.agent, args.timeout_s, task_ids=task_ids)
        results[model["id"]] = result
        if "error" in result:
            print(f"  ERROR: {result['error']}", file=sys.stderr)
        else:
            print(f"  {result['n_resolved']}/{result['n_resolved'] + result['n_unresolved']} resueltas "
                  f"({result['accuracy']:.1%})", file=sys.stderr)

    with open(RESULTS / "terminal_bench_eval.json", "w") as f:
        json.dump(results, f, indent=2)
    print(f"guardado en {RESULTS / 'terminal_bench_eval.json'}", file=sys.stderr)


if __name__ == "__main__":
    main()
