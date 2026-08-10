"""Tools de agente sobre un repo real (clon local), para la bateria SWE-bench.
A diferencia de tools.py (sandbox en memoria), aqui SI hay filesystem real,
asi que cada path se valida contra escapes de directorio (../, absolutos)."""
import subprocess
from pathlib import Path


class RepoFS:
    def __init__(self, repo_dir, test_python=None):
        self.root = Path(repo_dir).resolve()
        self.calls = []
        # ponytail: python del venv de test cacheado (bench/../. cache/test-venv), no
        # el interprete del sistema -> hace falta version de python compatible con el
        # repo historico (ver README, bateria 4). None = tool run_tests deshabilitada.
        self.test_python = test_python

    def _safe_path(self, rel):
        p = (self.root / rel).resolve()
        if not str(p).startswith(str(self.root)):
            raise ValueError(f"path fuera del repo: {rel}")
        return p

    def dispatch(self, name, args_json):
        import json
        try:
            args = json.loads(args_json)
        except json.JSONDecodeError as e:
            self.calls.append((name, args_json, False))
            return f"error: argumentos no son JSON valido: {e}"
        try:
            result = getattr(self, f"_tool_{name}")(**args)
            self.calls.append((name, args, True))
            return result
        except AttributeError:
            self.calls.append((name, args, False))
            return f"error: tool desconocida '{name}'"
        except Exception as e:
            self.calls.append((name, args, False))
            return f"error: {e}"

    def _tool_read_file(self, path, start_line=1, end_line=None):
        p = self._safe_path(path)
        start_line = int(start_line)
        lines = p.read_text(errors="replace").splitlines()
        end_line = int(end_line) if end_line else len(lines)
        snippet = lines[start_line - 1:end_line]
        return "\n".join(f"{i}: {l}" for i, l in enumerate(snippet, start=start_line))

    def _tool_list_files(self, dir="."):
        p = self._safe_path(dir)
        return "\n".join(sorted(str(x.relative_to(self.root)) for x in p.rglob("*.py") if x.is_file())[:200])

    def _tool_grep(self, pattern, dir="."):
        p = self._safe_path(dir)
        r = subprocess.run(
            ["grep", "-rnE", "--include=*.py", pattern, str(p)],
            capture_output=True, text=True, timeout=20,
        )
        return "\n".join(l.replace(str(self.root) + "/", "") for l in r.stdout.splitlines()[:100]) or "(sin resultados)"

    def _tool_write_file(self, path, content):
        p = self._safe_path(path)
        p.write_text(content)
        return f"ok: escrito {path} ({len(content)} bytes)"

    def _tool_run_tests(self, expr=""):
        if not self.test_python:
            return "error: run_tests no disponible en este repo"
        import os
        env = dict(os.environ, PYTHONPATH=str(self.root))
        cmd = [str(self.test_python), "-m", "pytest", "-rA", "-q"]
        if expr:
            cmd += ["-k", expr]
        try:
            r = subprocess.run(cmd, cwd=self.root, env=env, capture_output=True, text=True, timeout=90)
        except subprocess.TimeoutExpired:
            return "error: timeout ejecutando tests (90s)"
        out = (r.stdout + r.stderr)
        return out[-3000:]  # cola: ahi esta el resumen pass/fail

    def _tool_replace_in_file(self, path, old, new):
        p = self._safe_path(path)
        text = p.read_text()
        if old not in text:
            return f"error: no se encontro el texto exacto a reemplazar en {path}"
        p.write_text(text.replace(old, new, 1))
        return f"ok: reemplazado en {path}"


TOOL_SCHEMAS = [
    {"type": "function", "function": {
        "name": "read_file", "description": "Lee lineas de un archivo del repo (con numeros de linea).",
        "parameters": {"type": "object", "properties": {
            "path": {"type": "string"}, "start_line": {"type": "integer"}, "end_line": {"type": "integer"}},
            "required": ["path"]},
    }},
    {"type": "function", "function": {
        "name": "list_files", "description": "Lista archivos .py bajo un directorio del repo.",
        "parameters": {"type": "object", "properties": {"dir": {"type": "string"}}, "required": []},
    }},
    {"type": "function", "function": {
        "name": "grep", "description": "Busca un patron de texto en archivos .py del repo (como grep -rn).",
        "parameters": {"type": "object", "properties": {
            "pattern": {"type": "string"}, "dir": {"type": "string"}}, "required": ["pattern"]},
    }},
    {"type": "function", "function": {
        "name": "run_tests", "description": "Corre la suite de tests del repo (pytest). expr filtra por -k (nombre de test), vacio = todos.",
        "parameters": {"type": "object", "properties": {"expr": {"type": "string"}}, "required": []},
    }},
    {"type": "function", "function": {
        "name": "replace_in_file", "description": "Reemplaza un fragmento de texto EXACTO por otro en un archivo (primera ocurrencia).",
        "parameters": {"type": "object", "properties": {
            "path": {"type": "string"}, "old": {"type": "string"}, "new": {"type": "string"}},
            "required": ["path", "old", "new"]},
    }},
    {"type": "function", "function": {
        "name": "write_file", "description": "Sobreescribe un archivo completo con el contenido dado.",
        "parameters": {"type": "object", "properties": {
            "path": {"type": "string"}, "content": {"type": "string"}}, "required": ["path", "content"]},
    }},
]
