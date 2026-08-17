#!/usr/bin/env python3
"""Runner unico: elige que baterias lanzar (por nombre o por categoria) y el baseline
del leaderboard final. No reimplementa nada, solo orquesta los scripts existentes."""
import argparse
import subprocess
import sys
from pathlib import Path

BENCH = Path(__file__).parent

# Registro de baterias disponibles. "categories" sirve para filtrar (--categories),
# "official" marca si es un benchmark publico/estandar (comparable fuera de este repo)
# o uno propio del harness. "needs" documenta requisitos extra (ver README).
SUITES = {
    "perf": {
        "script": "perf.py",
        "categories": ["perf", "short"],
        "official": False,
        "needs": None,
    },
    "code": {
        "script": "code_eval.py",
        "categories": ["dev", "short"],
        "official": False,
        "needs": None,
    },
    "agent": {
        "script": "agent_eval.py",
        "categories": ["agentic", "tool-use", "short"],
        "official": False,
        "needs": None,
    },
    "swebench": {
        "script": "swebench_agent.py",
        "categories": ["dev", "agentic", "long"],
        "official": True,
        "needs": "venv separado con swebench+datasets (ver README), y solo evalua modelos locales por ahora",
    },
    "humaneval": {
        "script": "humaneval_eval.py",
        "categories": ["dev", "short"],
        "official": True,
        "needs": "pip install -r requirements-official.txt",
    },
    "gsm8k": {
        "script": "gsm8k_eval.py",
        "categories": ["reasoning", "short"],
        "official": True,
        "needs": "pip install -r requirements-official.txt",
    },
    "mmlu": {
        "script": "mmlu_eval.py",
        "categories": ["knowledge", "short"],
        "official": True,
        "needs": "pip install -r requirements-official.txt",
    },
    "terminal-bench": {
        "script": "terminal_bench_eval.py",
        "categories": ["dev", "agentic", "long"],
        "official": True,
        "needs": "pip install terminal-bench (CLI 'tb'), Docker corriendo",
    },
}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--suites", help=f"lista separada por comas de {{{','.join(SUITES)}}} (por defecto: todas las baterias propias, no las oficiales)")
    ap.add_argument("--categories", help="filtra baterias por categoria (dev, agentic, perf, tool-use, short, long)")
    ap.add_argument("--baseline", default=None, help="id de modelo baseline para el leaderboard final")
    ap.add_argument("--list", action="store_true", help="lista las baterias disponibles con su categoria y sale")
    args = ap.parse_args()

    if args.list:
        for name, s in SUITES.items():
            tag = "oficial" if s["official"] else "propio"
            print(f"{name:10s} [{tag:7s}] categorias={','.join(s['categories'])}" + (f"  (necesita: {s['needs']})" if s["needs"] else ""))
        return

    if args.suites:
        names = [s.strip() for s in args.suites.split(",")]
    elif args.categories:
        wanted = {c.strip() for c in args.categories.split(",")}
        names = [n for n, s in SUITES.items() if wanted & set(s["categories"])]
    else:
        names = [n for n, s in SUITES.items() if not s["official"]]  # las oficiales necesitan datasets/venv extra, no por defecto

    for name in names:
        suite = SUITES.get(name)
        if suite is None:
            sys.exit(f"bateria desconocida: {name} (opciones: {', '.join(SUITES)})")
        print(f"\n=== {name} ({suite['script']}) ===", file=sys.stderr)
        subprocess.run([sys.executable, str(BENCH / suite["script"])], check=True, cwd=BENCH)

    leaderboard_cmd = [sys.executable, str(BENCH / "leaderboard.py")]
    if args.baseline:
        leaderboard_cmd += ["--baseline", args.baseline]
    subprocess.run(leaderboard_cmd, check=True, cwd=BENCH)


if __name__ == "__main__":
    main()
