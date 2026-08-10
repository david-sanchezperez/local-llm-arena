#!/usr/bin/env python3
"""Bateria 1: codigo. Subset propio (8 problemas) via prompt -> exec -> assert.

ponytail: exec() sin sandbox (subprocess local, sin docker). Vale para
modelos de confianza en tu propia maquina; si algun dia evaluas output no
confiable, mete un contenedor. No hace falta hoy.
"""
import json
import subprocess
import sys
import tempfile
import textwrap
from pathlib import Path

RESULTS = Path(__file__).parent.parent / "results"

from common import load_models, chat, is_alive, extract_code
from problems import PROBLEMS

TIMEOUT_S = 10


def run_problem(model, problem):
    prompt = (
        "Completa la siguiente funcion en Python. Responde SOLO con el codigo, "
        "sin explicaciones, dentro de un bloque ```python.\n\n" + problem["prompt"]
    )
    try:
        raw = chat(model, [{"role": "user", "content": prompt}], max_tokens=1500)
    except Exception as e:
        return {"id": problem["id"], "passed": False, "error": f"api_error: {e}"}

    code = textwrap.dedent(extract_code(raw)).strip("\n")
    full = code + "\n\n" + problem["test"] + "\n"

    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        f.write(full)
        path = f.name

    try:
        r = subprocess.run([sys.executable, path], capture_output=True, timeout=TIMEOUT_S, text=True)
        passed = r.returncode == 0
        err = None if passed else (r.stderr or "").strip()[-300:]
    except subprocess.TimeoutExpired:
        passed, err = False, "timeout"

    return {"id": problem["id"], "passed": passed, "error": err}


def main():
    results = {}
    for model in load_models():
        if not is_alive(model):
            print(f"[skip] {model['id']}: no responde", file=sys.stderr)
            continue
        print(f"[run] {model['id']}...", file=sys.stderr)
        outcomes = [run_problem(model, p) for p in PROBLEMS]
        passed = sum(o["passed"] for o in outcomes)
        results[model["id"]] = {"passed": passed, "total": len(PROBLEMS), "detail": outcomes}
        print(f"  {passed}/{len(PROBLEMS)} pass", file=sys.stderr)

    with open(RESULTS / "code_eval.json", "w") as f:
        json.dump(results, f, indent=2)
    print(f"guardado en {RESULTS / 'code_eval.json'}", file=sys.stderr)


if __name__ == "__main__":
    main()
