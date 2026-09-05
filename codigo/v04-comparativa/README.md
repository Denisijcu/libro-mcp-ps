# Capítulo 4 — Código

Un solo archivo: `banco_pruebas.py`.

Mide lo único que de verdad cambia cuando cambias de modelo: **si acierta la herramienta
y los argumentos**. No ejecuta nada en la máquina; solo mira qué habría llamado. Es
seguro correrlo tantas veces como quieras.

## Requisitos

```powershell
pip install requests
```

LM Studio abierto, con un modelo cargado y el servidor local activo. En la máquina de
referencia escucha en `127.0.0.1:1234`.

## Uso

Desde esta carpeta:

```powershell
python banco_pruebas.py --listar
python banco_pruebas.py --modelo google/gemma-4-12b-qat
```

Sin `--modelo` usa el primero de la lista.

## Qué mide

Doce casos repartidos en cinco familias:

| Familia | Qué comprueba |
|---|---|
| `directo-*` | Peticiones explícitas. Lo mínimo exigible. |
| `indirecto-*` | El usuario describe un síntoma, no pide una herramienta. |
| `args-*` | Si extrae bien los argumentos del enunciado. |
| `negativo-*` | Si sabe **no** llamar a nada cuando no hace falta. |
| `imposible-1` | Si admite que no tiene herramienta en vez de forzar otra. |

Los casos negativos son los importantes. Un modelo que llama a una herramienta en cada
turno no está acertando: está disparando. Y en un servidor con permisos sobre el sistema,
disparar sale caro.

## Veredictos

- **OK** — herramienta correcta y argumentos correctos.
- **PARCIAL** — herramienta correcta, argumentos mal.
- **FALLO** — herramienta equivocada, ninguna cuando tocaba, o alguna cuando no tocaba.
- **ERROR** — la petición ni siquiera llegó a completarse.

Cada ejecución deja un `resultados_<modelo>.json` con el detalle.

## Modelos disponibles en la máquina de referencia

Detectados el 2026-09-04 vía `GET /v1/models`:

```
google/gemma-4-12b-qat
lmstudio-community/qwen2.5-coder-7b-instruct
qwen/qwen3-vl-4b
qwen/qwen3.8-27b
qwen/qwen2.5-coder-7b-instruct
text-embedding-nomic-embed-text-v1.5
```

## Estado de verificación

`[VERIFICAR: Denis]` — falta ejecutar el banco contra al menos tres modelos y pegar los
resultados en `pruebas/cap04-comparativa.md`. Sin esos números, las tablas del capítulo 4
están vacías y el capítulo no se puede cerrar.

Sugerencia de barrido, de más pequeño a más grande:

```powershell
python banco_pruebas.py --modelo qwen/qwen3-vl-4b
python banco_pruebas.py --modelo lmstudio-community/qwen2.5-coder-7b-instruct
python banco_pruebas.py --modelo google/gemma-4-12b-qat
python banco_pruebas.py --modelo qwen/qwen3.8-27b
```

Para la columna de Claude hay que correr los mismos doce casos contra la API de
Anthropic. Se añadirá al script cuando decidamos si el libro asume que el lector tiene
clave de API.
