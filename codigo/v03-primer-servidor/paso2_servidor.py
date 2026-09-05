# -*- coding: utf-8 -*-
"""
Capitulo 3, paso 2: el mismo servidor, arreglado.

Cambios respecto al paso 1, cada uno explicado en el capitulo:

  1. Un ejecutor central en vez de repetir subprocess.run en cada herramienta.
  2. Manejo de errores: si PowerShell falla, el modelo recibe un mensaje util
     en vez de una cadena vacia.
  3. Las enumeraciones se convierten a texto: "Running" en vez de 4.
  4. La salida siempre es un array JSON, tenga uno o cien elementos.
  5. Descripciones escritas para el modelo, no para el programador.
  6. Los mensajes de depuracion van a stderr, NUNCA a stdout.

AVISO: este servidor todavia interpola valores en el comando (get_service).
Es vulnerable a inyeccion a proposito. Se arregla en el capitulo 8.
"""

import subprocess
import sys

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("PowerShell Basico")


def run_powershell(command: str, timeout: int = 15) -> str:
    """Ejecuta un comando de PowerShell y devuelve su salida como texto."""
    try:
        result = subprocess.run(
            [
                "powershell.exe",
                "-NoProfile",        # no cargar el perfil del usuario: mas rapido y predecible
                "-NonInteractive",   # que nunca se quede esperando a que alguien teclee
                "-Command", command,
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",        # que un caracter raro no reviente la llamada
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return f"[ERROR] El comando tardo mas de {timeout} segundos y se cancelo."
    except FileNotFoundError:
        return "[ERROR] No se encontro powershell.exe en este sistema."

    salida = (result.stdout or "").strip()
    error = (result.stderr or "").strip()

    if result.returncode != 0:
        return f"[ERROR] PowerShell devolvio el codigo {result.returncode}: {error or salida}"
    if salida:
        return salida
    if error:
        return f"[AVISO] Sin resultados. Detalle: {error}"
    return "[OK] El comando se ejecuto pero no devolvio nada."


@mcp.tool()
def get_date() -> str:
    """Gets the current date and time of the Windows machine, formatted as yyyy-MM-dd HH:mm:ss."""
    return run_powershell("Get-Date -Format 'yyyy-MM-dd HH:mm:ss'")


@mcp.tool()
def get_disk_space() -> str:
    """Lists every drive letter with its total, used and free space in GB.

    Use it to check whether the machine is running out of disk space.
    """
    command = """
Get-PSDrive -PSProvider FileSystem | Where-Object { $_.Used -ne $null } | ForEach-Object {
    [PSCustomObject]@{
        Unidad  = $_.Name
        UsadoGB = [math]::Round($_.Used / 1GB, 2)
        LibreGB = [math]::Round($_.Free / 1GB, 2)
    }
} | ConvertTo-Json -Depth 3
"""
    return run_powershell(command)


@mcp.tool()
def get_service(service_name: str) -> str:
    """Gets the status, start type and display name of a single Windows service.

    Use it to check whether a specific service is running. The name is the short
    service name, not the display name: for example 'WinDefend', not
    'Microsoft Defender Antivirus Service'.
    """
    # OJO: esto es vulnerable a inyeccion. Se arregla en el capitulo 8.
    command = f"""
Get-Service -Name '{service_name}' |
    Select-Object Name,
                  DisplayName,
                  @{{ Name='Status';    Expression={{ $_.Status.ToString() }} }},
                  @{{ Name='StartType'; Expression={{ $_.StartType.ToString() }} }} |
    ConvertTo-Json -Depth 3
"""
    return run_powershell(command)


@mcp.tool()
def get_top_processes(count: int = 5) -> str:
    """Lists the processes using the most memory right now, with their PID and memory in MB.

    Use it when the machine feels slow or the user asks what is consuming resources.
    Maximum 20 processes.
    """
    if count < 1:
        count = 1
    if count > 20:
        count = 20

    command = f"""
$lista = Get-Process | Sort-Object WorkingSet64 -Descending | Select-Object -First {count} |
    ForEach-Object {{
        [PSCustomObject]@{{
            Nombre     = $_.Name
            PID        = $_.Id
            MemoriaMB  = [math]::Round($_.WorkingSet64 / 1MB, 2)
        }}
    }}
ConvertTo-Json -InputObject @($lista) -Depth 3
"""
    return run_powershell(command)


if __name__ == "__main__":
    # A stderr, nunca a stdout: stdout es el canal del protocolo.
    print("Servidor PowerShell Basico arrancando...", file=sys.stderr)
    mcp.run()
