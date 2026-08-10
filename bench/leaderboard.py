#!/usr/bin/env python3
"""Junta results/*.json en una tabla markdown, comparados contra un baseline elegible."""
import argparse
import json
from pathlib import Path

RESULTS = Path(__file__).parent.parent / "results"


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--baseline", default=None, help="id de modelo contra el que comparar code pass (por defecto: el primero con resultados)")
    args = ap.parse_args()

    perf = {r["model"]: r for r in json.loads((RESULTS / "perf.json").read_text())} if (RESULTS / "perf.json").exists() else {}
    code = json.loads((RESULTS / "code_eval.json").read_text()) if (RESULTS / "code_eval.json").exists() else {}
    agent = json.loads((RESULTS / "agent_eval.json").read_text()) if (RESULTS / "agent_eval.json").exists() else {}

    ids = sorted(set(perf) | set(code) | set(agent))
    baseline = args.baseline or next(iter(code), None)
    base_passed = code.get(baseline, {}).get("passed") if baseline else None

    lines = [
        f"| modelo | code pass | vs {baseline} | agent pass | avg turns | tool errors | ttft (s) | tok/s |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for mid in ids:
        c = code.get(mid)
        p = perf.get(mid)
        a = agent.get(mid)
        code_str = f"{c['passed']}/{c['total']}" if c else "-"
        if c and base_passed is not None and mid != baseline:
            delta = c["passed"] - base_passed
            delta_str = f"{delta:+d}"
        elif mid == baseline:
            delta_str = "(baseline)"
        else:
            delta_str = "-"
        agent_str = f"{a['passed']}/{a['total']}" if a else "-"
        turns_str = str(a["avg_turns"]) if a else "-"
        errs_str = str(a["tool_errors"]) if a else "-"
        ttft_str = str(p["ttft_s"]) if p else "-"
        toks_str = str(p["tok_s"]) if p else "-"
        lines.append(f"| {mid} | {code_str} | {delta_str} | {agent_str} | {turns_str} | {errs_str} | {ttft_str} | {toks_str} |")

    out = "\n".join(lines)
    (RESULTS / "leaderboard.md").write_text(out + "\n")
    print(out)


if __name__ == "__main__":
    main()
