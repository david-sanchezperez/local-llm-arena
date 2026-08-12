#!/usr/bin/env python3
"""Bateria oficial: MMLU (conocimiento general, opcion multiple), el benchmark
estandar de "conocimiento" en release notes. Dataset real via HF (cais/mmlu, config
'all'). El test set tiene 14042 preguntas de 57 materias; por defecto se evalua una
submuestra reproducible (--n, default 200)."""
import argparse
import json
import random
import re
import sys
from pathlib import Path

RESULTS = Path(__file__).parent.parent / "results"
RESULTS.mkdir(exist_ok=True)

from common import load_models, chat, is_alive, load_hf_dataset

SEED = 42
LETTERS = "ABCD"
ANSWER_RE = re.compile(r"\b([ABCD])\b")


def format_prompt(problem):
    opts = "\n".join(f"{LETTERS[i]}. {c}" for i, c in enumerate(problem["choices"]))
    return (
        f"Pregunta de opcion multiple sobre {problem['subject'].replace('_', ' ')}. "
        "Responde SOLO con la letra correcta (A, B, C o D).\n\n"
        f"{problem['question']}\n\n{opts}"
    )


def run_problem(model, problem):
    try:
        raw = chat(model, [{"role": "user", "content": format_prompt(problem)}], max_tokens=200)
    except Exception as e:
        return {"passed": False, "error": f"api_error: {e}"}

    m = ANSWER_RE.search(raw.strip().upper())
    pred = m.group(1) if m else None
    gold = LETTERS[problem["answer"]]
    return {"passed": pred == gold, "gold": gold, "pred": pred, "subject": problem["subject"]}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--n", type=int, default=200, help="tamano de la submuestra (0 = test set completo, 14042 preguntas)")
    args = ap.parse_args()

    problems = list(load_hf_dataset("cais/mmlu", "all", split="test"))
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
        print(f"  {passed}/{len(problems)} correctas", file=sys.stderr)

    with open(RESULTS / "mmlu_eval.json", "w") as f:
        json.dump(results, f, indent=2)
    print(f"guardado en {RESULTS / 'mmlu_eval.json'}", file=sys.stderr)


if __name__ == "__main__":
    main()
