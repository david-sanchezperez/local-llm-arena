"""Cliente mínimo OpenAI-compatible + carga de roster. Sin dependencias nuevas."""
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
