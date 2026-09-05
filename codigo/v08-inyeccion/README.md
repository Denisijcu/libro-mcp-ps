# Capítulo 8 — Código

Tres archivos, sin dependencias externas. No hace falta el SDK de MCP ni un modelo.

| Archivo | Qué es |
|---|---|
| `vulnerable.py` | El patrón con f-strings. Solo para demostración. |
| `seguro.py` | El mismo comportamiento con variables de entorno y `-EncodedCommand`. |
| `demo_inyeccion.py` | Ejecuta ambos con la misma carga útil y compara. |

## Cómo se ejecuta

Desde `F:\libro-mcp-ps\codigo\v08-inyeccion`:

```powershell
python demo_inyeccion.py
```

Sale con código 0 si la versión vulnerable ejecutó código ajeno **y** la segura resistió.
Cualquier otro código de salida significa que algo no está midiendo lo que debería.

## Sobre la carga útil

Es inofensiva a propósito: crea `%TEMP%\PWNED_DEMO_CAP8.txt` con una línea de texto, y
el propio script lo borra después. No toca el registro, no toca la red, no borra nada.

Lo único que demuestra es que PowerShell ejecutó una sentencia que el programador nunca
escribió. Para el argumento del capítulo con eso basta: si se puede crear un archivo, se
puede hacer cualquier otra cosa.

## Estado de verificación

`[VERIFICAR: Denis]` — pendiente de ejecutar en la máquina del autor y pegar la salida
real en `pruebas/cap08-demo-inyeccion.txt`.

No se pudo ejecutar desde la sesión de escritura: el servidor MCP `windows` se bloquea
cuando el script que le pasas lanza un `powershell.exe` hijo. Comprobado con un caso
mínimo (`python -c "subprocess.run(['powershell.exe', ...])"`), que también se colgó.
