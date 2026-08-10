#!/usr/bin/env python3
"""Bateria 4: SWE-bench (Lite), solo modelo local por ahora.
Genera un model_patch por instancia dejando al agente explorar/editar un clon real
del repo (bench/swebench_tools.py), luego extrae `git diff` como prediccion.
La evaluacion real (aplicar patch + correr tests en Docker) la hace el harness oficial
`swebench.harness.run_evaluation` (pip install swebench) via run_swebench_eval.sh.

Scope deliberado: 6 instancias de psf/requests (repo pequeno, sin deps pesadas,
imagen Docker rapida de construir) en vez de las 300 de Lite completo -> acotar tiempo.
"""
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

import requests

# ponytail: llama.cpp a veces no reconoce la tool call del modelo cuando llega
# tras reasoning_content largo, y la deja como texto plano sin parsear dentro de
# reasoning_content en vez de como tool_calls estructurado (finish_reason=stop).
# Este regex recupera ese caso concreto (<tool_call><function=X><parameter=Y>V</parameter>...).
# Si llama.cpp arregla su parser de tool-calls, esto deja de hacer falta.
TOOL_CALL_FALLBACK_RE = re.compile(
    r"<tool_call>\s*<function=(\w+)>(.*?)</function>\s*</tool_call>", re.DOTALL
)
PARAM_RE = re.compile(r"<parameter=(\w+)>\n?(.*?)\n?</parameter>", re.DOTALL)


def _recover_tool_call_from_text(text):
    if not text:
        return None
    m = TOOL_CALL_FALLBACK_RE.search(text)
    if not m:
        return None
    name, body = m.group(1), m.group(2)
    args = {k: v for k, v in PARAM_RE.findall(body)}
    return {"id": "recovered", "type": "function", "function": {"name": name, "arguments": json.dumps(args)}}

BENCH_DIR = Path(__file__).parent
ROOT = BENCH_DIR.parent
CACHE_REPO = ROOT / ".cache" / "requests.git"
WORK_BASE = ROOT / ".cache" / "work"
RESULTS = ROOT / "results"
TEST_PYTHON = ROOT / ".cache" / "test-venv" / "bin" / "python"

sys.path.insert(0, str(BENCH_DIR))
from common import load_models, is_alive  # noqa: E402
from swebench_tools import RepoFS, TOOL_SCHEMAS  # noqa: E402

MAX_TURNS = 20
SYSTEM = (
    "Eres un ingeniero de software resolviendo un issue real en un repo Python. "
    "Usa las tools para explorar el codigo (grep, list_files, read_file) antes de editar. "
    "Aplica el fix minimo necesario con replace_in_file o write_file. "
    "IMPORTANTE: antes de dar la tarea por terminada, usa run_tests para comprobar que "
    "tu cambio no rompe nada. Si algo falla, corrigelo y vuelve a correr los tests. "
    "Solo responde con un mensaje de texto normal (sin tool call) cuando los tests "
    "relevantes pasen. No edites archivos de test."
)


def ensure_repo_cache():
    if not CACHE_REPO.exists():
        CACHE_REPO.parent.mkdir(parents=True, exist_ok=True)
        print("[setup] clonando psf/requests (una vez)...", file=sys.stderr)
        subprocess.run(["git", "clone", "--bare", "https://github.com/psf/requests.git", str(CACHE_REPO)], check=True)


def checkout_instance(instance_id, base_commit):
    workdir = WORK_BASE / instance_id
    if workdir.exists():
        shutil.rmtree(workdir)
    workdir.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "clone", str(CACHE_REPO), str(workdir)], check=True, capture_output=True)
    subprocess.run(["git", "checkout", base_commit], check=True, capture_output=True, cwd=workdir)
    return workdir


def call_with_tools(model, messages, timeout=180):
    url = f"{model['base_url']}/chat/completions"
    headers = {"Authorization": f"Bearer {model['api_key']}"}
    payload = {"model": model["model_name"], "messages": messages, "tools": TOOL_SCHEMAS, "max_tokens": 3000}
    r = requests.post(url, json=payload, headers=headers, timeout=timeout)
    r.raise_for_status()
    return r.json()["choices"][0]["message"]


def run_instance(model, instance):
    workdir = checkout_instance(instance["instance_id"], instance["base_commit"])
    fs = RepoFS(workdir, test_python=TEST_PYTHON if TEST_PYTHON.exists() else None)
    messages = [
        {"role": "system", "content": SYSTEM},
        {"role": "user", "content": f"Issue:\n{instance['problem_statement']}"},
    ]
    turns, stop_reason = 0, "max_turns"
    for turns in range(1, MAX_TURNS + 1):
        try:
            msg = call_with_tools(model, messages)
        except Exception as e:
            stop_reason = f"api_error: {e}"
            break
        tool_calls = msg.get("tool_calls")
        recovered = False
        if not tool_calls:
            fallback = _recover_tool_call_from_text(msg.get("reasoning_content") or msg.get("content"))
            if fallback:
                tool_calls = [fallback]
                recovered = True
        if not tool_calls:
            stop_reason = "final_message"
            break
        messages.append({
            "role": "assistant", "content": "" if recovered else (msg.get("content") or ""),
            "tool_calls": [{"id": tc["id"], "type": "function", "function": tc["function"]} for tc in tool_calls],
        })
        for tc in tool_calls:
            result = fs.dispatch(tc["function"]["name"], tc["function"]["arguments"])
            messages.append({"role": "tool", "tool_call_id": tc["id"], "content": result[:4000]})

    diff = subprocess.run(["git", "diff"], cwd=workdir, capture_output=True, text=True).stdout
    return {
        "instance_id": instance["instance_id"], "model_patch": diff, "turns": turns,
        "tool_calls": len(fs.calls), "stop_reason": stop_reason,
    }


def main():
    from datasets import load_dataset
    ds = load_dataset("princeton-nlp/SWE-bench_Lite", split="test")
    instances = [x for x in ds if x["repo"] == "psf/requests"]
    print(f"[info] {len(instances)} instancias de psf/requests", file=sys.stderr)

    ensure_repo_cache()

    model_id = sys.argv[1] if len(sys.argv) > 1 else "qwen3.6-35b-a3b"
    model = next(m for m in load_models() if m["id"] == model_id)
    if not is_alive(model):
        print("modelo local no responde", file=sys.stderr)
        sys.exit(1)

    predictions = []
    meta = []
    for inst in instances:
        print(f"[run] {inst['instance_id']}...", file=sys.stderr)
        r = run_instance(model, inst)
        predictions.append({
            "instance_id": r["instance_id"], "model_name_or_path": model["id"], "model_patch": r["model_patch"],
        })
        meta.append(r)
        print(f"  turns={r['turns']} tool_calls={r['tool_calls']} stop={r['stop_reason']} patch_bytes={len(r['model_patch'])}", file=sys.stderr)

    RESULTS.mkdir(exist_ok=True)
    pred_path = RESULTS / f"swebench_predictions.{model_id}.json"
    pred_path.write_text(json.dumps(predictions, indent=2))
    (RESULTS / f"swebench_meta.{model_id}.json").write_text(json.dumps(meta, indent=2))
    print(f"guardado en {pred_path}", file=sys.stderr)


if __name__ == "__main__":
    main()
