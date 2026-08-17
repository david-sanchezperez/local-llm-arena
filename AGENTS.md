# AGENTS.md

Instrucciones para agentes (humanos o LLM) que trabajen en este repo.

## Build / test

```bash
pip install -r requirements.txt
cd bench && python3 run.py --list
```

Ver `README.md` para las baterías disponibles y cómo añadir una nueva.

## Capacidades para dispatch automático

Bloque leído por `obsidian-ideas/generate_projects.py` para que el
clasificador de encaje (`review.evaluate_fit`) sepa qué puede pedirle a este
proyecto, no solo que existe.

```yaml
capabilities:
  - id: evaluate-llm-candidate
    when: >
      una noticia o idea menciona un modelo LLM nuevo con pesos abiertos
      (checkpoint público, GGUF disponible o cuantizable) cuyo tamaño quepa
      en 24GB de VRAM en alguna cuantización razonable (4-6 bit)
    action: >
      crear una tarea con tenant=host_gpu y task_kind=evaluate pidiendo que
      se compare el candidato contra el campeón actual (ver `models:` en
      config/models.yaml) con las baterías perf+code+agent y, si el
      resultado es prometedor, humaneval con muestra
    constraints:
      - nunca promocionar el candidato a producción automáticamente — la
        tarea solo debe producir un veredicto con datos, nunca aplicar
        cambios en litellm_config.yaml ni en systemd de producción
      - requiere GPU real del host — no ejecutable en un contenedor
        agent-loops normal (sin acceso a /dev/nvidia*)
      - respetar el guardarraíl térmico (BENCH_PAUSE_S) entre peticiones
```
