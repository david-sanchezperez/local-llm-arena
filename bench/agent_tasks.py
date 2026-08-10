"""Bateria 2: tool-use/agente. Tareas largas, multi-turno, sobre el sandbox de tools.py.
Cada tarea: seed (estado inicial del FS), goal (mensaje de usuario), checker(fs) -> bool, max_turns."""
import json


def _check_notes_summary(fs):
    summary = fs.files.get("notas/resumen.txt", "")
    names = [l.strip() for l in summary.strip().splitlines() if l.strip()]
    return names == ["1.txt", "2.txt", "3.txt"]


def _check_config_increment(fs):
    raw = fs.files.get("config.json")
    if not raw:
        return False
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return False
    return data.get("retries") == 5 and data.get("timeout") == 10


def _check_error_recovery(fs):
    # manifest.txt lista un archivo que no existe (roto.txt); la tarea pide sumar
    # los tamanos de los archivos listados que SI existen y escribir el total.
    return fs.files.get("total.txt", "").strip() == "9"


def _check_log_search(fs):
    report = fs.files.get("logs/report.txt", "")
    return "count=3" in report and "app.log" in report and "worker.log" in report and "db.log" not in report


def _check_mean(fs):
    val = fs.files.get("data/mean.txt", "").strip()
    try:
        return abs(float(val) - 4.75) < 0.01
    except ValueError:
        return False


def _check_rename_preserve(fs):
    return (
        "final/report.md" in fs.files
        and fs.files["final/report.md"] == "contenido original\nlinea 2"
        and "draft/report.md" not in fs.files
    )


TASKS = [
    {
        "id": "notes_summary",
        "seed": {"notas/1.txt": "nota 1", "notas/2.txt": "nota 2", "notas/3.txt": "nota 3"},
        "goal": (
            "En el sistema de archivos hay varias notas bajo el prefijo 'notas/'. "
            "Usa list_files para averiguar cuales existen (no las asumas), y crea "
            "'notas/resumen.txt' que liste sus nombres de archivo (sin el prefijo 'notas/'), "
            "uno por linea, ordenados alfabeticamente."
        ),
        "checker": _check_notes_summary,
        "max_turns": 6,
    },
    {
        "id": "config_increment",
        "seed": {"config.json": json.dumps({"retries": 3, "timeout": 10})},
        "goal": (
            "Lee 'config.json', incrementa el valor de 'retries' en 2 (deja 'timeout' igual), "
            "y reescribe el archivo con el JSON actualizado."
        ),
        "checker": _check_config_increment,
        "max_turns": 6,
    },
    {
        "id": "error_recovery",
        "seed": {"manifest.txt": "a.txt\nb.txt\nroto.txt", "a.txt": "1234", "b.txt": "12345"},
        "goal": (
            "Lee 'manifest.txt': lista archivos, uno por linea. Para cada uno que EXISTA "
            "de verdad, suma la longitud en caracteres de su contenido (ignora los que no "
            "existan, sin fallar). Escribe el total en 'total.txt'."
        ),
        "checker": _check_error_recovery,
        "max_turns": 8,
    },
    {
        "id": "log_search",
        "seed": {
            "logs/app.log": "INFO start\nERROR db down\nINFO retry",
            "logs/worker.log": "ERROR timeout\nERROR timeout\nINFO ok",
            "logs/db.log": "INFO connected\nINFO query ok",
        },
        "goal": (
            "Busca la palabra 'ERROR' en todos los archivos bajo 'logs/'. Crea "
            "'logs/report.txt' con el conteo total de apariciones en formato 'count=N' "
            "(N el numero total) y, en otra linea, los nombres de archivo (sin prefijo) "
            "donde aparece al menos una vez, separados por coma."
        ),
        "checker": _check_log_search,
        "max_turns": 8,
    },
    {
        "id": "mean_calc",
        "seed": {"data/numbers.txt": "3, 5, 4.2, 6.8"},
        "goal": (
            "Lee 'data/numbers.txt' (numeros separados por comas), calcula la media "
            "usando la tool calc, y escribe el resultado en 'data/mean.txt' con exactamente "
            "dos decimales (formato '0.00')."
        ),
        "checker": _check_mean,
        "max_turns": 6,
    },
    {
        "id": "rename_preserve",
        "seed": {"draft/report.md": "contenido original\nlinea 2"},
        "goal": (
            "Mueve 'draft/report.md' a 'final/report.md' preservando el contenido "
            "exactamente igual, y borra el original de 'draft/'."
        ),
        "checker": _check_rename_preserve,
        "max_turns": 6,
    },
]
