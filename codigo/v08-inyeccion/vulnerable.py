# -*- coding: utf-8 -*-
"""
VERSION VULNERABLE - solo para demostracion del capitulo 8.

Este archivo reproduce el patron que usa la mayoria de los servidores MCP de
PowerShell que hay publicados: construir el comando con f-strings e interpolar
directamente el valor que llega del modelo.

NO USES ESTE PATRON EN PRODUCCION. Existe aqui para poder medir el fallo.
"""

import subprocess


def run_powershell(command: str) -> str:
    """Ejecuta un comando PowerShell y devuelve la salida como texto."""
    try:
        result = subprocess.run(
            [
                "powershell.exe",
                "-NoProfile",
                "-NonInteractive",
                "-ExecutionPolicy", "Bypass",
                "-Command", command,
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=15,
        )
        if result.returncode != 0:
            return f"Fallo. Codigo {result.returncode}: {result.stderr.strip()}"
        return result.stdout.strip()
    except subprocess.TimeoutExpired:
        return "Error: timeout."


# ------------------------------------------------------------------
# Las tres formas del mismo fallo
# ------------------------------------------------------------------

def get_user_info(username: str) -> str:
    """Consulta un usuario local. El valor se mete dentro de comillas simples."""
    command = f"Get-LocalUser -Name '{username}' | Select-Object Name, Enabled | ConvertTo-Json"
    return run_powershell(command)


def list_directory(path: str) -> str:
    """Lista un directorio. Mismo patron, distinto cmdlet."""
    command = f"Get-ChildItem -Path '{path}' | Select-Object Name | ConvertTo-Json"
    return run_powershell(command)


def search_software(name_filter: str) -> str:
    """Busca software instalado. Aqui el valor va dentro de un scriptblock."""
    command = (
        "Get-ItemProperty HKLM:\\Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\* | "
        f"Where-Object {{ $_.DisplayName -like '*{name_filter}*' }} | "
        "Select-Object DisplayName | ConvertTo-Json"
    )
    return run_powershell(command)
