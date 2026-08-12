#!/usr/bin/env python3
"""Bateria 2: tool-use/agente. Loop multi-turno real: el modelo llama tools sobre un
sandbox con estado (tools.py), nosotros ejecutamos y devolvemos el resultado, hasta
que el modelo termina o se agota max_turns. Se mide: pass/fail, turnos usados, nº de
tool calls, nº de tool calls fallidas (json invalido / tool inexistente / excepcion)."""
import json
import sys
from pathlib import Path

import requests

from common import load_models, is_alive, parse_fallback_tool_calls
from tools import VirtualFS, TOOL_SCHEMAS
from agent_tasks import TASKS

TOOL_NAMES = {t["function"]["name"] for t in TOOL_SCHEMAS}

RESULTS = Path(__file__).parent.parent / "results"
RESULTS.mkdir(exist_ok=True)

SYSTEM = (
    "Eres un agente con acceso a un sistema de archivos via tools. Usa las tools "
    "necesarias para completar la tarea del usuario. Cuando termines, responde con "
    "un mensaje de texto normal (sin tool call) confirmando que has terminado."
)


def call_with_tools(model, messages, timeout=120):
    url = f"{model['base_url']}/chat/completions"
    headers = {"Authorization": f"Bearer {model['api_key']}"}
    payload = {
        "model": model["model_name"],
        "messages": messages,
        "tools": TOOL_SCHEMAS,
        "max_tokens": 1000,
    }
    r = requests.post(url, json=payload, headers=headers, timeout=timeout)
    r.raise_for_status()
    return r.json()["choices"][0]["message"]


def run_task(model, task):
    fs = VirtualFS(seed=task["seed"])
    messages = [
        {"role": "system", "content": SYSTEM},
        {"role": "user", "content": task["goal"]},
    ]
    turns = 0
    used_fallback = False
    for turns in range(1, task["max_turns"] + 1):
        try:
            msg = call_with_tools(model, messages)
        except Exception as e:
            return {"id": task["id"], "passed": False, "turns": turns, "tool_calls": len(fs.calls),
                    "tool_errors": sum(1 for c in fs.calls if not c[2]), "stop_reason": f"api_error: {e}",
                    "used_fallback_parser": used_fallback}

        tool_calls = msg.get("tool_calls")
        if not tool_calls:
            # algunas plantillas (GLM-4, Qwen2.5-Coder, DeepSeek-Coder-V2) no las
            # parsea llama-server con --jinja y devuelve la llamada como texto
            # crudo en content -- lo reconocemos ahi como fallback.
            tool_calls = parse_fallback_tool_calls(msg.get("content"), TOOL_NAMES)
            if tool_calls:
                used_fallback = True
        if not tool_calls:
            break

        # el mensaje del assistant con tool_calls debe ir en el historial tal cual
        messages.append({
            "role": "assistant", "content": msg.get("content") or "",
            "tool_calls": [{"id": tc["id"], "type": "function", "function": tc["function"]} for tc in tool_calls],
        })
        for tc in tool_calls:
            result = fs.dispatch(tc["function"]["name"], tc["function"]["arguments"])
            messages.append({"role": "tool", "tool_call_id": tc["id"], "content": result})
    else:
        return {"id": task["id"], "passed": False, "turns": turns, "tool_calls": len(fs.calls),
                "tool_errors": sum(1 for c in fs.calls if not c[2]), "stop_reason": "max_turns",
                "used_fallback_parser": used_fallback}

    passed = task["checker"](fs)
    return {"id": task["id"], "passed": passed, "turns": turns, "tool_calls": len(fs.calls),
            "tool_errors": sum(1 for c in fs.calls if not c[2]), "stop_reason": "final_message",
            "used_fallback_parser": used_fallback}


def main():
    results = {}
    for model in load_models():
        if not is_alive(model):
            print(f"[skip] {model['id']}: no responde", file=sys.stderr)
            continue
        print(f"[run] {model['id']}...", file=sys.stderr)
        outcomes = [run_task(model, t) for t in TASKS]
        passed = sum(o["passed"] for o in outcomes)
        avg_turns = sum(o["turns"] for o in outcomes) / len(outcomes)
        tool_errors = sum(o["tool_errors"] for o in outcomes)
        fallback_used = sum(o.get("used_fallback_parser", False) for o in outcomes)
        results[model["id"]] = {
            "passed": passed, "total": len(TASKS), "avg_turns": round(avg_turns, 1),
            "tool_errors": tool_errors, "fallback_parser_used": fallback_used, "detail": outcomes,
        }
        note = f" (fallback parser en {fallback_used}/{len(TASKS)})" if fallback_used else ""
        print(f"  {passed}/{len(TASKS)} pass, avg_turns={avg_turns:.1f}, tool_errors={tool_errors}{note}", file=sys.stderr)

    with open(RESULTS / "agent_eval.json", "w") as f:
        json.dump(results, f, indent=2)
    print(f"guardado en {RESULTS / 'agent_eval.json'}", file=sys.stderr)


if __name__ == "__main__":
    main()
