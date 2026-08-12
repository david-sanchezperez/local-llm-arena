#!/usr/bin/env python3
"""Bateria oficial: HumanEval (164 problemas, pass@1), el benchmark de codigo
mas citado en release notes de modelos. Dataset real via HF (openai/openai_humaneval).

ponytail: exec() sin sandbox, igual que code_eval.py — mismo trust boundary
(modelos de confianza en tu propia maquina).
"""
import argparse
import json
import random
import subprocess
import sys
import tempfile
import textwrap
from pathlib import Path

RESULTS = Path(__file__).parent.parent / "results"
RESULTS.mkdir(exist_ok=True)

from common import load_models, chat, is_alive, extract_code, load_hf_dataset

SEED = 42
TIMEOUT_S = 10


def run_problem(model, problem):
    prompt = (
        "Completa la siguiente funcion en Python. Responde SOLO con el codigo "
        "completo de la funcion (incluida la firma), sin explicaciones, dentro "
        "de un bloque ```python.\n\n" + problem["prompt"]
    )
    try:
        raw = chat(model, [{"role": "user", "content": prompt}], max_tokens=1500)
    except Exception as e:
        return {"id": problem["task_id"], "passed": False, "error": f"api_error: {e}"}

    code = textwrap.dedent(extract_code(raw)).strip("\n")
    full = code + "\n\n" + problem["test"] + f"\n\ncheck({problem['entry_point']})\n"

    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        f.write(full)
        path = f.name

    try:
        r = subprocess.run([sys.executable, path], capture_output=True, timeout=TIMEOUT_S, text=True)
        passed = r.returncode == 0
        err = None if passed else (r.stderr or "").strip()[-300:]
    except subprocess.TimeoutExpired:
        passed, err = False, "timeout"

    return {"id": problem["task_id"], "passed": passed, "error": err}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--n", type=int, default=0, help="tamano de la submuestra (0 = test set completo, 164 problemas)")
    args = ap.parse_args()

    problems = list(load_hf_dataset("openai/openai_humaneval", split="test"))
    if args.n:
        problems = random.Random(SEED).sample(problems, min(args.n, len(problems)))

    results = {}
    for model in load_models():
        if not is_alive(model):
            print(f"[skip] {model['id']}: no responde", file=sys.stderr)
            continue
        print(f"[run] {model['id']}...", file=sys.stderr)
        outcomes = [run_problem(model, p) for p in problems]
        passed = sum(o["passed"] for o in outcomes)
        results[model["id"]] = {"passed": passed, "total": len(problems), "detail": outcomes}
        print(f"  {passed}/{len(problems)} pass@1", file=sys.stderr)

    with open(RESULTS / "humaneval_eval.json", "w") as f:
        json.dump(results, f, indent=2)
    print(f"guardado en {RESULTS / 'humaneval_eval.json'}", file=sys.stderr)


if __name__ == "__main__":
    main()
