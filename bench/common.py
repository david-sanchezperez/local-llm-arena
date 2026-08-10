"""Cliente mínimo OpenAI-compatible + carga de roster. Sin dependencias nuevas."""
import json
import os
import re
import time
import yaml
import requests
from pathlib import Path

CONFIG = Path(__file__).parent.parent / "config" / "models.yaml"


def load_models():
    cfg = yaml.safe_load(CONFIG.read_text())
    models = cfg["models"]
    for m in models:
        m["base_url"] = os.path.expandvars(m["base_url"])
        m["api_key"] = os.path.expandvars(m["api_key"])
    return models


def chat(model, messages, max_tokens=512, timeout=120):
    url = f"{model['base_url']}/chat/completions"
    headers = {"Authorization": f"Bearer {model['api_key']}"}
    payload = {"model": model["model_name"], "messages": messages, "max_tokens": max_tokens}
    r = requests.post(url, json=payload, headers=headers, timeout=timeout)
    r.raise_for_status()
    msg = r.json()["choices"][0]["message"]
    # modelos "thinking" pueden agotar max_tokens en el razonamiento y dejar content vacio
    return msg.get("content") or msg.get("reasoning_content") or ""


def is_alive(model, timeout=5):
    try:
        r = requests.get(f"{model['base_url']}/models", headers={"Authorization": f"Bearer {model['api_key']}"}, timeout=timeout)
        return r.ok
    except requests.RequestException:
        return False


def load_hf_dataset(*args, **kwargs):
    """datasets.load_dataset(), con mensaje claro si falta la dependencia opcional."""
    try:
        from datasets import load_dataset
    except ImportError:
        raise SystemExit(
            "Falta el paquete 'datasets' (solo lo necesitan las baterias oficiales "
            "humaneval/gsm8k/mmlu). Instala con: pip install -r requirements-official.txt"
        )
    return load_dataset(*args, **kwargs)


def extract_code(text):
    m = re.search(r"```(?:python)?\n(.*?)```", text, re.DOTALL)
    if m:
        return m.group(1)
    m = re.search(r"```(?:python)?\n(.*)", text, re.DOTALL)  # bloque sin cerrar (truncado)
    return m.group(1) if m else text


def _as_json(s):
    try:
        return json.loads(s)
    except (json.JSONDecodeError, TypeError):
        return None


def parse_fallback_tool_calls(content, tool_names):
    """llama-server con --jinja no tiene parser de tool_calls registrado para
    todas las plantillas (visto con GLM-4, Qwen2.5-Coder y DeepSeek-Coder-V2:
    el modelo llama a la tool bien, pero el texto queda crudo en `content` en
    vez de estructurado). Reconoce esos 3 formatos y los convierte al formato
    tool_calls de OpenAI. Devuelve None si no reconoce nada (no es un tool call
    fallido, es que el modelo respondio texto normal)."""
    if not content:
        return None

    # Qwen2.5 (esquema con varias tools): JSON suelto {"name": ..., "arguments": {...}}
    # al principio del mensaje, sin envoltorio <tools> (con una sola tool en el
    # esquema a veces si lo envuelve, ver caso de abajo) -- puede llevar texto
    # detras, por eso raw_decode en vez de json.loads sobre el string entero.
    stripped = content.strip()
    if stripped.startswith("{"):
        try:
            obj, _ = json.JSONDecoder().raw_decode(stripped)
        except json.JSONDecodeError:
            obj = None
        if obj and obj.get("name") in tool_names and "arguments" in obj:
            return [{"id": "fallback-0", "type": "function",
                     "function": {"name": obj["name"], "arguments": json.dumps(obj["arguments"])}}]

    # DeepSeek: <｜tool▁calls▁begin｜><｜tool▁call▁begin｜>function<｜tool▁sep｜>NOMBRE\n```json\n{...}\n```
    m = re.search(r"tool▁sep｜>\s*(\w+).*?(\{.*?\})", content, re.DOTALL)
    if m and m.group(1) in tool_names:
        args = _as_json(m.group(2))
        if args is not None:
            return [{"id": "fallback-0", "type": "function", "function": {"name": m.group(1), "arguments": json.dumps(args)}}]

    # Qwen2.5: <tools>{"name": "...", "arguments": {...}}</tools> (puede haber varias)
    calls = []
    for i, m in enumerate(re.finditer(r"<tools?>\s*(\{.*?\})\s*</tools?>", content, re.DOTALL)):
        obj = _as_json(m.group(1))
        if obj and obj.get("name") in tool_names:
            calls.append({"id": f"fallback-{i}", "type": "function",
                          "function": {"name": obj["name"], "arguments": json.dumps(obj.get("arguments", {}))}})
    if calls:
        return calls

    # GLM-4: NOMBRE\n{JSON} al principio del mensaje, sin marcadores
    m = re.match(r"\s*([a-zA-Z_]\w*)\s*\n\s*(\{.*?\})", content, re.DOTALL)
    if m and m.group(1) in tool_names:
        args = _as_json(m.group(2))
        if args is not None:
            return [{"id": "fallback-0", "type": "function", "function": {"name": m.group(1), "arguments": json.dumps(args)}}]

    return None


def _self_check():
    names = {"list_files", "read_file"}
    cases = {
        "glm": ('list_files\n{"path": "."}\ntexto de sobra', "list_files"),
        "qwen_wrapped": ('<tools>\n{"name": "list_files", "arguments": {"path": "."}}\n</tools>', "list_files"),
        "qwen_bare": ('{"name": "read_file", "arguments": {"path": "notes.txt"}}', "read_file"),
        "deepseek": (' <｜tool▁calls▁begin｜><｜tool▁call▁begin｜>function<｜tool▁sep｜>list_files\n```json\n{"path": "."}\n```', "list_files"),
    }
    for label, (content, expected_name) in cases.items():
        r = parse_fallback_tool_calls(content, names)
        assert r and r[0]["function"]["name"] == expected_name, f"{label}: {r}"
    assert parse_fallback_tool_calls("texto normal sin tool call", names) is None
    assert parse_fallback_tool_calls("list_files\n{...", names) is None  # json invalido, no revienta
    print("common.parse_fallback_tool_calls: ok")


if __name__ == "__main__":
    _self_check()
