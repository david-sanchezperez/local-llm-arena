#!/usr/bin/env python3
"""Vigilante térmico reutilizable: en un hilo aparte, si la GPU supera MAX_TEMP_C,
mata el proceso servido en PORT. Extraído de la comprobación manual del 15/08/2026
(evaluación de Qwen3.8-27B) para que cualquier evaluación futura en el host lo use
sin reinventarlo. Ver AGENTS.md, capability evaluate-llm-candidate.

MAX_TEMP_C=83 (valor original) resultó ser la "GPU Target Temperature" de nvidia-smi
-- el objetivo normal de la curva de ventilador, no un límite de seguridad. En esta
RTX 3090 Ti el throttle real ("Slowdown Temp") es 94C y el apagado 97C (ver
`nvidia-smi -q -d TEMPERATURE`). 88C deja ~6C de margen real antes del throttle,
sin matar corridas largas por alcanzar temperatura de funcionamiento normal (visto
el 16/08/2026: cortes espurios a mitad de una tanda de Terminal-bench)."""
import subprocess
import threading
import time

MAX_TEMP_C = 88
POLL_INTERVAL_S = 15


class ThermalGuard(threading.Thread):
    def __init__(self, port: int, max_temp_c: int = MAX_TEMP_C, interval_s: float = POLL_INTERVAL_S):
        super().__init__(daemon=True)
        self.port = port
        self.max_temp_c = max_temp_c
        self.interval_s = interval_s
        self._stop_event = threading.Event()
        self.triggered = False

    def _gpu_temp(self) -> int | None:
        try:
            out = subprocess.run(
                ["nvidia-smi", "--query-gpu=temperature.gpu", "--format=csv,noheader,nounits"],
                capture_output=True, text=True, timeout=5,
            )
            return int(out.stdout.strip().splitlines()[0]) if out.returncode == 0 else None
        except (FileNotFoundError, subprocess.TimeoutExpired, ValueError, IndexError):
            return None

    def run(self) -> None:
        while not self._stop_event.wait(self.interval_s):
            temp = self._gpu_temp()
            if temp is not None and temp >= self.max_temp_c:
                self.triggered = True
                # -9: visto el 16/08/2026 que un SIGTERM (pkill sin -9) puede dejar
                # el proceso colgado (VRAM sin liberar, puerto sin responder) en vez
                # de terminar limpio.
                subprocess.run(["pkill", "-9", "-f", f"llama-server.*--port {self.port}"], check=False)
                break

    def stop(self) -> None:
        self._stop_event.set()
