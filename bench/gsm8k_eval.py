#!/usr/bin/env python3
"""Bateria oficial: GSM8K (razonamiento matematico, grade-school), otro benchmark
estandar en release notes. Dataset real via HF (openai/gsm8k). El test set tiene
1319 problemas; por defecto se evalua una submuestra reproducible (--n, default 100)
para que correrlo contra un modelo local no tome horas."""
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
FINAL_RE = re.compile(r"-?\d[\d,]*\.?\d*")


def gold_answer(answer_field):
    return answer_field.split("####")[-1].strip().replace(",", "")


def parse_final_number(text):
    nums = FINAL_RE.findall(text.replace(",", ""))
    return nums[-1] if nums else None


def run_problem(model, problem):
    prompt = (
        "Resuelve el siguiente problema paso a paso. Termina tu respuesta con "
        "una linea exactamente 'Respuesta final: <numero>'.\n\n" + problem["question"]
    )
    try:
        raw = chat(model, [{"role": "user", "content": prompt}], max_tokens=1000)
    except Exception as e:
        return {"passed": False, "error": f"api_error: {e}"}

    gold = gold_answer(problem["answer"])
    pred = parse_final_number(raw)
    try:
        passed = pred is not None and float(pred) == float(gold)
    except ValueError:
        passed = False
    return {"passed": passed, "gold": gold, "pred": pred}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--n", type=int, default=100, help="tamano de la submuestra (0 = test set completo, 1319 problemas)")
    args = ap.parse_args()

    problems = list(load_hf_dataset("openai/gsm8k", "main", split="test"))
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

    with open(RESULTS / "gsm8k_eval.json", "w") as f:
        json.dump(results, f, indent=2)
    print(f"guardado en {RESULTS / 'gsm8k_eval.json'}", file=sys.stderr)


if __name__ == "__main__":
    main()
