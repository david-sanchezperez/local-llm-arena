#!/usr/bin/env python3
"""Bateria 3: rendimiento (TTFT, tok/s) via streaming SSE contra el endpoint OpenAI-compatible.

VRAM/quant matrix (Q4 vs Q5 vs Q8) se deja fuera: requiere recargar el server con
distintos ggufs, mejor hecho a mano con llama-bench por ahora.
ponytail: sin eso, add cuando quieras automatizar swaps de quant.
"""
import json
import sys
import time
from pathlib import Path
import requests

from common import load_models, is_alive

PROMPT = "Explica en 3 frases que es un arbol binario de busqueda."


def stream_chat_timed(model, max_tokens=200):
    url = f"{model['base_url']}/chat/completions"
    headers = {"Authorization": f"Bearer {model['api_key']}"}
    payload = {
        "model": model["model_name"],
        "messages": [{"role": "user", "content": PROMPT}],
        "max_tokens": max_tokens,
        "stream": True,
        "stream_options": {"include_usage": True},
    }
    t0 = time.perf_counter()
    ttft = None
    n_tokens = 0
    with requests.post(url, json=payload, headers=headers, stream=True, timeout=120) as r:
        r.raise_for_status()
        for line in r.iter_lines():
            if not line or not line.startswith(b"data: "):
                continue
            data = line[len(b"data: "):]
            if data == b"[DONE]":
                break
            chunk = json.loads(data)
            if chunk.get("usage"):
                n_tokens = chunk["usage"]["completion_tokens"]
            delta_obj = chunk["choices"][0]["delta"] if chunk.get("choices") else {}
            delta = delta_obj.get("content") or delta_obj.get("reasoning_content")
            if delta and ttft is None:
                ttft = time.perf_counter() - t0
    total = time.perf_counter() - t0
    gen_time = total - (ttft or 0)
    tok_s = n_tokens / gen_time if gen_time > 0 and n_tokens > 0 else 0.0
    return {"ttft_s": round(ttft or 0, 3), "tok_s": round(tok_s, 1), "n_tokens": n_tokens, "total_s": round(total, 2)}


def main():
    results = []
    for model in load_models():
        if not is_alive(model):
            print(f"[skip] {model['id']}: no responde", file=sys.stderr)
            continue
        print(f"[run] {model['id']}...", file=sys.stderr)
        r = stream_chat_timed(model)
        r["model"] = model["id"]
        results.append(r)
        print(f"  ttft={r['ttft_s']}s  tok/s={r['tok_s']}  tokens={r['n_tokens']}", file=sys.stderr)

    out = Path(__file__).parent.parent / "results" / "perf.json"
    with open(out, "w") as f:
        json.dump(results, f, indent=2)
    print(f"guardado en {out}", file=sys.stderr)


if __name__ == "__main__":
    main()
