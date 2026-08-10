"""Sandbox de herramientas con estado real para la bateria de agente.
Sistema de archivos virtual en memoria + una calculadora. Nada de disco real,
nada de red -> seguro para dejar que cualquier modelo llame estas tools."""
import json


class VirtualFS:
    def __init__(self, seed=None):
        self.files = dict(seed or {})
        self.calls = []  # (name, args, ok) para metrica de tool-use

    def dispatch(self, name, args_json):
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

    def _tool_write_file(self, path, content):
        self.files[path] = content
        return f"ok: escrito {path} ({len(content)} bytes)"

    def _tool_read_file(self, path):
        if path not in self.files:
            return f"error: {path} no existe"
        return self.files[path]

    def _tool_list_files(self, prefix=""):
        matches = sorted(p for p in self.files if p.startswith(prefix))
        return json.dumps(matches)

    def _tool_delete_file(self, path):
        if path not in self.files:
            return f"error: {path} no existe"
        del self.files[path]
        return f"ok: borrado {path}"

    def _tool_calc(self, expression):
        # ponytail: eval restringido a aritmetica, sin builtins ni acceso a self/globales.
        # vale para un sandbox de benchmark local; no exponer esto a input no confiable en produccion.
        allowed = set("0123456789+-*/(). ")
        if not set(expression) <= allowed:
            return "error: expresion contiene caracteres no permitidos"
        return str(eval(expression, {"__builtins__": {}}, {}))


TOOL_SCHEMAS = [
    {"type": "function", "function": {
        "name": "write_file", "description": "Escribe (o sobreescribe) un archivo con el contenido dado.",
        "parameters": {"type": "object", "properties": {
            "path": {"type": "string"}, "content": {"type": "string"}}, "required": ["path", "content"]},
    }},
    {"type": "function", "function": {
        "name": "read_file", "description": "Lee el contenido de un archivo.",
        "parameters": {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]},
    }},
    {"type": "function", "function": {
        "name": "list_files", "description": "Lista los archivos cuyo path empieza por prefix (vacio = todos).",
        "parameters": {"type": "object", "properties": {"prefix": {"type": "string"}}, "required": []},
    }},
    {"type": "function", "function": {
        "name": "delete_file", "description": "Borra un archivo.",
        "parameters": {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]},
    }},
    {"type": "function", "function": {
        "name": "calc", "description": "Evalua una expresion aritmetica simple (+ - * / parentesis) y devuelve el resultado.",
        "parameters": {"type": "object", "properties": {"expression": {"type": "string"}}, "required": ["expression"]},
    }},
]
