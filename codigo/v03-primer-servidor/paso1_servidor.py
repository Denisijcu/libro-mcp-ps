# -*- coding: utf-8 -*-
"""
Capitulo 3, paso 1: el servidor MCP mas pequeno que hace algo util.

Una sola herramienta, sin parametros. El objetivo de este paso no es que el
servidor sea util, es verlo aparecer en el cliente y comprobar que responde.

Ejecutar:  no se ejecuta a mano. Lo arranca el host (Claude Desktop, LM Studio).
Para comprobar que al menos carga sin errores de sintaxis:

    python -c "import paso1_servidor"
"""

import subprocess

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("PowerShell Basico")


@mcp.tool()
def get_date() -> str:
    """Gets the current date and time from the Windows machine."""
    result = subprocess.run(
        ["powershell.exe", "-NoProfile", "-NonInteractive",
         "-Command", "Get-Date -Format 'yyyy-MM-dd HH:mm:ss'"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=15,
    )
    return result.stdout.strip()


if __name__ == "__main__":
    mcp.run()
