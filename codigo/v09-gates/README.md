# Capítulo 9 — Código

| Archivo | Qué es |
|---|---|
| `gates.py` | Las tres capas de autoridad, sin depender de PowerShell ni de MCP. |

`gates.py` se puede ejecutar solo y trae una autoprueba que enseña los seis casos del
capítulo.

## Probar

En modo por defecto (todo cerrado):

```powershell
python gates.py
```

Abriendo las dos puertas, para ver el flujo completo del token:

```powershell
$env:PSMCP_ALLOW_WRITE=1
$env:PSMCP_ALLOW_DESTRUCTIVE=1
python gates.py
```

La autoprueba comprueba seis cosas:

1. Una herramienta de lectura pasa siempre.
2. Una de escritura se bloquea si no se abrió esa puerta.
3. Una destructiva pide confirmación antes de hacer nada.
4. Un token emitido para un objetivo **no vale para otro**.
5. El token correcto deja pasar la operación.
6. Reutilizar el mismo token falla: es de un solo uso.

## Estado de verificación

`[VERIFICAR: Denis]` — pendiente de ejecutar y pegar la salida en
`pruebas/cap09-gates.txt`.

No se pudo ejecutar desde la sesión de escritura: el MCP `windows` vuelve a bloquearse al
lanzar `python` como proceso hijo. Es el mismo deadlock del capítulo 8.
