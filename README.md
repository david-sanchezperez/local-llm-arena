# local-llm-arena

Harness para comparar LLMs — locales (llama.cpp, cualquier servidor
OpenAI-compatible) o de pago vía API — en varios ejes: código, tool-use/agente,
rendimiento, y (opcional) SWE-bench Lite real. Local y API comparten la misma
interfaz OpenAI-compatible, así que el harness no distingue entre ambos: un
modelo local puede compararse contra el último frontera, o contra un modelo
barato tipo Haiku/DeepSeek-Flash si eso es lo relevante para tu caso.

## Quick start

```bash
cp config/models.yaml.example config/models.yaml   # edita con tus modelos/endpoints
cd bench
python3 run.py --list                 # ver baterias disponibles y categorias
python3 run.py                        # lanza perf + code + agent, genera results/leaderboard.md
python3 run.py --baseline glm-5.2     # compara "code pass" contra ese modelo en vez del primero
python3 run.py --suites code,agent    # solo esas baterias
python3 run.py --categories dev       # todas las baterias etiquetadas "dev"

# SWE-bench Lite (bateria "oficial", solo modelos locales, requiere venv aparte):
cd .. && python3 -m venv .venv && .venv/bin/pip install swebench datasets pyyaml requests
.venv/bin/python bench/swebench_agent.py <model_id>
```

Roster de modelos en `config/models.yaml` (no se versiona — usa
`config/models.yaml.example` como plantilla; `base_url`/`api_key` admiten
`${VARS_DE_ENTORNO}`). Un modelo se salta automáticamente si su endpoint no
responde (`is_alive`).

## Baterías disponibles

| bateria | script | categoria | tipo | que mide |
|---|---|---|---|---|
| `perf` | `perf.py` | perf, short | propio | TTFT y tok/s via streaming |
| `code` | `code_eval.py` | dev, short | propio | 30 problemas estilo HumanEval, prompt -> exec -> assert |
| `agent` | `agent_eval.py` | agentic, tool-use, short | propio | 6 tareas multi-turno con tool-use real sobre un sandbox con estado |
| `swebench` | `swebench_agent.py` | dev, agentic, long | **oficial** | SWE-bench Lite real (Docker, harness oficial `swebench`) |

"oficial" = benchmark público/estándar, comparable con resultados de otros
proyectos (útil al liberar un modelo o producto). "propio" = tests definidos
en este repo, más rápidos de correr pero solo comparables entre sí.

### Añadir otra batería (propia o benchmark público)

Cada batería es un script independiente en `bench/` que: carga modelos con
`common.load_models()`, corre su tarea, y escribe `results/<nombre>.json` con
`{model_id: {...métricas...}}`. Para añadir una nueva:

1. Escribe el script siguiendo ese contrato (mira `code_eval.py` para una
   batería simple, o `swebench_agent.py` para una que envuelve un benchmark
   público externo).
2. Regístrala en `SUITES` dentro de `bench/run.py` (script, categorías,
   `official: True/False`, y `needs` si requiere dependencias extra).
3. Si quieres que aparezca en `leaderboard.py`, añade sus columnas ahí (hoy
   soporta perf/code/agent; swebench se reporta aparte por ahora, ver bateria
   4 más abajo).

Ejemplos de benchmarks públicos que encajarían con este mismo patrón:
BFCL (tool-use), LiveCodeBench (código con fecha de corte), MMLU-Pro
(conocimiento general) — ninguno está integrado todavía, se deja como
siguiente paso natural una vez haya interés real en compararse contra ellos.

## Resultado actual

30 problemas (strings, matematicas, listas/dicts, recursion, ordenacion,
bordes/errores). Baseline fijo: **deepseek-v4-flash**.

| modelo | code pass | vs deepseek | ttft (s) | tok/s |
|---|---|---|---|---|
| claude-sonnet-5 | 30/30 | +1 | 1.5 | 92.9 |
| glm-5.2 | 30/30 | +1 | 4.0 | 119.0 |
| deepseek-v4-flash | 29/30 | (baseline) | 1.3 | 112.4 |
| qwen3.6-35b-a3b (local) | 27/30 | -2 | 0.3 | 56.8 |

Lectura: con muestra de 30 (vs 8 antes), el modelo local queda 2 problemas
por debajo del baseline (27/30 vs 29/30) — una diferencia real pero pequeña,
no una brecha grande. Sigue ganando en TTFT (sin latencia de red) y pierde
en tok/s (56.8 vs 93-119, 3B activos en tu 3090 Ti vs infraestructura de
datacenter). Para tareas de código aisladas y acotadas, el local rinde
razonablemente cerca de frontier.

### Bateria 4: SWE-bench Lite (solo modelo local)

Version real (no oracle): el agente clona `psf/requests` en el commit base
de cada instancia y tiene que explorar el repo real (`grep`/`list_files`/
`read_file`) y editarlo (`replace_in_file`/`write_file`) el mismo, sin que
se le den los archivos correctos de antemano. Se probaron 6 instancias
(todo `psf/requests`, para compartir clon y acotar tiempo — de las 300 de
Lite completo). Generacion de patches con `bench/swebench_agent.py`
(`.venv/bin/python bench/swebench_agent.py`); evaluacion real via Docker
con el harness oficial `swebench` (`pip install swebench`) queda montada
pero sin ejecutar — ver nota abajo.

**Primera corrida (harness sin `run_tests`, max_turns=12): 0/6**, y en 5
de 6 el modelo se rendia tras 1-2 tool calls con un mensaje vacio, sin
intentar editar nada. Investigando el porque, aparecieron **dos bugs reales
del harness**, no del modelo:

1. **El fallback de tool-calls no existia**: llama.cpp, en ciertos turnos,
   devuelve la llamada a herramienta como texto plano dentro de
   `reasoning_content` (`<tool_call><function=X>...`) en vez de como
   `tool_calls` estructurado, con `finish_reason: stop`. Nuestro loop lo
   interpretaba como "el modelo ha terminado" cuando en realidad el modelo
   queria seguir explorando. Se anadio un parser de recuperacion
   (`_recover_tool_call_from_text` en `swebench_agent.py`) para este caso.
2. **Sin forma de verificar el propio trabajo**: no habia tool para correr
   tests. Se anadio `run_tests` (`swebench_tools.py`), respaldada por un
   venv de test dedicado con **Python 3.9** — el codigo historico de estas
   instancias usa `collections.MutableMapping` y `ssl.match_hostname`,
   ambos eliminados en Python 3.10+, asi que hacia falta la version exacta
   que el propio `swebench` especifica para este repo (visible en
   `swebench.harness.constants.MAP_REPO_VERSION_TO_SPECS`).

Ademas, dos bugs menores: `grep` no soportaba alternancia regex (`patron1|patron2`,
faltaba `-E`) y `read_file` rompia si el modelo mandaba `start_line` como
string en vez de int (el JSON schema lo declara integer pero nada obliga
al modelo a respetarlo).

**Con los 4 fixes, misma corrida (max_turns=20): 1/6 con patch no vacio**
(`psf__requests-2317`, un cambio de una linea: `builtin_str` ->
`to_native_string`). Los otros 5 siguen en patch vacio (exploran mas —
8-20 tool calls en vez de 1-2 — pero no cierran el ciclo edicion+
verificacion; hay variabilidad real entre corridas por el muestreo).

**Verificado con el harness oficial** (`swebench.harness.run_evaluation`,
Docker real, aplica el patch y corre los tests del repo — no solo "compila"):

| resultado | instancias |
|---|---|
| resuelto (tests pasan) | 1 (`psf__requests-2317`) |
| patch vacio (no lo intento) | 5 |
| patch generado pero no resuelve | 0 |

Los 5 patches vacios fallan trivialmente sin gastar tiempo de build/tests
para confirmarlo — el harness ya lo reporta como "empty_patch_instances".

Lectura: pasar de 0/6 a 1/6 verificado moviendo solo el harness (sin tocar
el modelo) confirma la sospecha original — parte del problema **si** era
la falta de tooling (verificacion propia, parser de tool-calls robusto),
no (solo) capacidad del modelo. Sigue habiendo una brecha real frente a
frontier (ver bateria 1: 27/30 en codigo aislado vs 1/6 en SWE-bench real),
pero es mas pequena de lo que parecia con el harness sin arreglar.

Nota metodologica: esto sigue siendo el escenario dificil (sin pistas de
que archivo tocar). El baseline "oracle" de los papers de SWE-bench (dar
los archivos correctos de antemano) da numeros mas altos para todos los
modelos — no se implemento aqui porque es una forma mas floja de medir
"resuelve el issue solo".

### Bateria 4b: mismo modelo, quant menos agresiva (IQ4_XS vs TQ3)

Hipotesis pendiente del analisis anterior: cuanto del 1/6 era el
harness (ya arreglado arriba) y cuanto era la cuantizacion TQ3 (~3
bits/parametro, muy agresiva). Se descargo `Qwen3.6-35B-A3B-UD-IQ4_XS.gguf`
(quant dinamica de Unsloth, 17.7GB, ~4 bits/parametro) de
[unsloth/Qwen3.6-35B-A3B-GGUF](https://huggingface.co/unsloth/Qwen3.6-35B-A3B-GGUF)
y se sirvio en un `llama-server` temporal aparte (puerto 8081, build mainline
de `~/llama.cpp`, sin tocar el servicio systemd de produccion que sirve TQ3
en :8080) para comparar sin interferir con nada mas que use el modelo actual.

Mismo harness (con los 4 fixes ya aplicados), las 4 baterias:

| modelo | code (30) | agent (6) | ttft (s) | tok/s | SWE-bench (6) |
|---|---|---|---|---|---|
| TQ3_4S (produccion, :8080) | 18/30* | 4/6 | 1.03 | 56.2 | 1/6 |
| UD-IQ4_XS (test, :8081) | 26/30 | 5/6 | 0.29 | 73.3 | **4/6** |

\* la bateria de codigo tiene varianza real entre corridas por el
muestreo (ver bateria 1: la primera corrida de TQ3 dio 27/30, esta 18/30
con el mismo codigo) — la cifra de SWE-bench es la que mas pesa aqui
porque es determinista via tests, no por parecido de texto.

**Con el mismo harness, sin tocar el modelo mas que la cuantizacion:
1/6 -> 4/6 en SWE-bench real.** Ademas la quant mas alta va *mas rapida*
(73 vs 56 tok/s) y con menos TTFT (0.29s vs 1.03s), porque con -ncmoe mas
bajo entra casi entera en la 3090 Ti (~11GB de VRAM con contexto de 32k)
en vez de tener que compartir computo con CPU. Osea: **no hay trade-off
aqui, la quant TQ3 actual es estrictamente peor** en todo lo medido
(calidad y velocidad) para esta tarjeta — probablemente el ahorro de TQ3
solo compensa en tarjetas con bastante menos de 24GB de VRAM libre.

**Aplicado (2026-08-10)**: `llama-server.service` (systemd --user) ahora
sirve `Qwen3.6-35B-A3B-UD-IQ4_XS.gguf` con el build mainline
(`~/llama.cpp/build/bin/llama-server`) en vez de TQ3_4S con el fork
`llama.cpp-tq3`. Backup del unit anterior en
`~/.config/systemd/user/llama-server.service.bak-tq3` por si hace falta
volver atras (`cp` de vuelta + `systemctl --user daemon-reload && systemctl
--user restart llama-server.service`). El servidor de prueba temporal en
:8081 se paro tras la migracion. VRAM en uso ahora: ~15.5GB de 24GB (con
contexto completo de 262144), dejando ~8GB libres.

Nota: `litellm_config.yaml` sigue anunciando el modelo como
`Qwen3.6-35B-A3B-TQ3_4S` (solo una etiqueta, no se valida contra lo que
realmente sirve `:8080`) — funciona igual, pero el nombre ha quedado
desactualizado si algun dia quieres renombrarlo por claridad.

### Bateria 2: agente / tool-use (6 tareas, multi-turno)

6 tareas sobre un sandbox de sistema de archivos virtual con estado real
(`bench/tools.py`): crear/leer/listar/borrar archivos + una calculadora,
expuestas como tools OpenAI-compatibles. Cada tarea exige encadenar varias
llamadas (leer -> calcular/transformar -> escribir), algunas obligan a leer
el resultado de una tool antes de decidir el siguiente paso (no se puede
resolver "de memoria" sin ejecutar), y una fuerza recuperarse de un archivo
listado que no existe. Se mide pass/fail contra el estado final real del
sandbox (no contra el texto de la respuesta), turnos usados, y tool calls
que fallan (JSON invalido / tool inexistente).

| modelo | agent pass | avg turns | tool errors |
|---|---|---|---|
| claude-sonnet-5 | 6/6 | 3.8 | 0 |
| deepseek-v4-flash | 6/6 | 3.8 | 0 |
| glm-5.2 | 5/6 | 3.7 | 0 |
| qwen3.6-35b-a3b (local) | 5/6 | 4.2 | 0 |

Lectura: el modelo local completa 5 de 6 tareas multi-turno, empatado con
GLM-5.2 y solo una por detrás de Claude/DeepSeek — **cero errores de
formato en las tool calls** en los cuatro modelos, señal de que el
function-calling del backend (llama.cpp) es fiable, no solo "parece"
funcionar. Usa algo mas de turnos de media (4.2 vs 3.7-3.8), pero no se
atasca ni entra en bucle. Con esto, la sospecha inicial ("la brecha se abre
en tareas largas y multi-turno") no se confirma con esta muestra: el modelo
local aguanta el tool-use encadenado casi igual que los frontier.

## Qué falta (deliberadamente fuera del scope inicial)

- **BFCL / PawBench / tarea propia sobre el tablero de granja-agentes**:
  la bateria de agente actual es un sandbox propio de 6 tareas, no estos
  benchmarks publicos — utiles si quieres comparar contra el resto del
  mundo, no solo entre tus 4 modelos.
- **SWE-bench con modelos de pago**: solo se corrio con el modelo local
  (lo pedido). Correr tambien con claude-sonnet-5/deepseek-v4-flash/glm-5.2
  daria el punto de comparacion real en la tarea donde mas importa —
  sobre todo ahora que el harness ya tiene `run_tests` y el fallback de
  tool-calls, asi que la comparacion seria mas justa que antes.
- **Confirmar SWE-bench con el roster completo de la pending list**
  (Qwen3.6-27B, Gemma4-27B/E4B) en cuanto se descarguen — el mismo harness
  ya deberia servir sin cambios, solo anadir la entrada en `models.yaml`.
- **Matriz de quant (Q4/Q5/Q8) para VRAM/tok-s**: requiere recargar el
  server de llama.cpp con distintos ggufs. Se deja para `llama-bench`
  manual (`~/llama.cpp/build/bin/llama-bench`) en vez de automatizarlo.
- **SWE-bench Verified**: benchmark pesado, requiere agente con acceso a
  shell/editor por tarea. Fuera de esta primera versión.

## Diseño

- `bench/common.py`: cliente HTTP mínimo (requests) contra cualquier
  endpoint OpenAI-compatible. Sin SDK — no hace falta.
- `bench/problems.py`: 8 problemas propios estilo HumanEval, en vez de la
  librería `human-eval` (no instalada, evita una dependencia nueva).
- Ejecución de código generado por el modelo: `subprocess` local sin
  sandbox — vale para modelos de confianza en tu propia máquina; si algún
  día evalúas modelos no confiables, mete Docker.
- `bench/tools.py`: sandbox de tool-use en memoria (sin disco real, sin
  red). La tool `calc` usa `eval` restringido a caracteres aritméticos y
  sin builtins — vale para este sandbox local, no exponer a input externo
  no confiable.
