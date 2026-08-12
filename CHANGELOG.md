# Changelog

Formato basado en [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

### Fixed

- `results/` no se creaba antes de escribir en ella en `perf.py`,
  `code_eval.py`, `agent_eval.py`, `humaneval_eval.py`, `gsm8k_eval.py` y
  `mmlu_eval.py`. En un clon nuevo del repo (`results/` está en
  `.gitignore` y no existe hasta la primera ejecución) el quick start del
  README (`python3 run.py`) fallaba con `FileNotFoundError` al intentar
  guardar el primer resultado. `swebench_agent.py` y
  `scripts/candidate_bench.py` ya creaban el directorio correctamente; se
  igualó el resto para que hagan lo mismo.
