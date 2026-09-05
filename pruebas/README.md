# Pruebas

Salidas reales de ejecución. Nada de este directorio se escribe a mano: se pega tal cual
sale de la máquina, con fecha y entorno.

Regla del libro: si una salida aparece citada en el manuscrito, tiene que existir aquí el
archivo del que se copió.

## Formato

Un archivo por prueba, nombrado `capNN-descripcion.txt`. Cabecera obligatoria:

```
Fecha   : 2026-09-04
Maquina : HP Omen / Windows 11 build 26100
Comando : python demo_inyeccion.py
Cwd     : F:\libro-mcp-ps\codigo\v08-inyeccion
---
<salida literal>
```

## Pendientes

| Archivo | Capítulo | Estado |
|---|---|---|
| `cap08-demo-inyeccion.txt` | 8 | PENDIENTE — Denis debe ejecutar la demo |

## Nota sobre la ejecución desde la sesión de escritura

El servidor MCP `windows` se bloquea cuando el script que se le pasa lanza un
`powershell.exe` hijo. Comprobado el 2026-09-04 con un caso mínimo:

```
python -c "import subprocess; subprocess.run(['powershell.exe','-NoProfile','-Command','1+1'], ...)"
```

También se colgó. Mientras eso no se resuelva, **las pruebas que invocan PowerShell las
ejecuta Denis y pega la salida aquí**. Comandos simples de una sola capa
(`$PSVersionTable`, `python --version`) sí funcionan por esa vía.
