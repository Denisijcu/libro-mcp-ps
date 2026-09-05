# Capítulo 3 — Código

Dos versiones del mismo servidor. La primera funciona; la segunda funciona bien.

| Archivo | Qué es |
|---|---|
| `paso1_servidor.py` | El servidor mínimo. Una herramienta, sin manejo de errores. |
| `paso2_servidor.py` | El mismo con las seis correcciones del capítulo. |

## Instalación

```powershell
pip install "mcp[cli]>=1.10,<2"
```

## Comprobar que carga

Estos servidores no se ejecutan a mano: los arranca el host. Para verificar que no hay
errores de sintaxis ni de importación, desde esta carpeta:

```powershell
python -c "import paso2_servidor"
```

Si no imprime nada, está bien. Si falla con `ModuleNotFoundError: No module named
'mcp.server.fastmcp'`, tienes instalada la versión 2.x del SDK: reinstala con la
restricción `<2`.

## Configuración en Claude Desktop

En `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "powershell-basico": {
      "command": "python",
      "args": ["F:\\libro-mcp-ps\\codigo\\v03-primer-servidor\\paso2_servidor.py"]
    }
  }
}
```

Rutas absolutas y barras dobles. Después hay que cerrar y volver a abrir la aplicación:
los servidores se lanzan al arrancar.

## Estado de verificación

- Los comandos de PowerShell de cada herramienta: **verificados** el 2026-09-04 en la
  máquina del autor. Salidas en `pruebas/cap03-comandos.txt`.
- El servidor completo cargado en un cliente MCP: `[VERIFICAR: Denis]`.

No se pudo comprobar el servidor entero desde la sesión de escritura porque hace falta un
host que lo arranque, y porque el MCP `windows` se bloquea con procesos hijos de
PowerShell.
