# -*- coding: utf-8 -*-
"""
VERSION SEGURA - capitulo 8.

Los valores nunca tocan el texto del script. Viajan por variables de entorno del
proceso hijo y el script de PowerShell los lee con $env:PSMCP_P_*.

Dos propiedades importantes:

1. El contenido de una variable de entorno NUNCA se parsea como codigo PowerShell.
   Aunque valga  x'; Remove-Item C:\\ -Recurse; '  sigue siendo una cadena.
2. El script se envia en -EncodedCommand (base64 UTF-16LE), asi que tampoco hay
   que pelear con las comillas en la linea de comandos de Windows.
"""

import base64
import os
import re
import subprocess
from typing import Any, Dict, Optional

PARAM_NAME_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")

PS_PRELUDE = r"""
$ProgressPreference = 'SilentlyContinue'
try { [Console]::OutputEncoding = [System.Text.Encoding]::UTF8 } catch {}
"""

# Con ErrorActionPreference en SilentlyContinue, PowerShell devuelve codigo de salida
# distinto de cero pero no escribe nada en stderr: el servidor se queda con un error
# mudo. $Error se rellena igual, asi que lo recuperamos al final del script.
EPILOGO_ERRORES = r"""
if ($Error.Count -gt 0) {
    [Console]::Error.WriteLine('PSERROR: ' + $Error[0].Exception.Message)
}
"""


def run_ps(
    script: str,
    params: Optional[Dict[str, Any]] = None,
    timeout: int = 15,
    strict: bool = True,
) -> str:
    """Ejecuta PowerShell sin interpolar ningun valor en el codigo."""
    env = os.environ.copy()
    preamble = []

    for name, value in (params or {}).items():
        # El nombre lo elige el programador, nunca el modelo. Aun asi se valida.
        if not PARAM_NAME_RE.match(name):
            return f"[ERROR] Nombre de parametro invalido: {name}"
        env_name = "PSMCP_P_" + name.upper()
        env[env_name] = "" if value is None else str(value)
        preamble.append(f"${name} = $env:{env_name}")

    error_pref = "Stop" if strict else "SilentlyContinue"
    full_script = (
        f"$ErrorActionPreference = '{error_pref}'\n"
        + PS_PRELUDE
        + "\n".join(preamble)
        + "\n"
        + script
        + EPILOGO_ERRORES
    )
    encoded = base64.b64encode(full_script.encode("utf-16-le")).decode("ascii")

    try:
        result = subprocess.run(
            [
                "powershell.exe",
                "-NoProfile",
                "-NonInteractive",
                "-NoLogo",
                "-ExecutionPolicy", "Bypass",
                "-EncodedCommand", encoded,
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            env=env,
        )
    except subprocess.TimeoutExpired:
        return f"[ERROR] Timeout de {timeout}s."

    stdout = (result.stdout or "").strip()
    stderr = (result.stderr or "").strip()

    if result.returncode != 0:
        detalle = stderr or stdout or "el comando fallo sin devolver mensaje"
        return f"[ERROR] Codigo {result.returncode}: {detalle}"
    if stderr.startswith("PSERROR:") and not stdout:
        return f"[ERROR] {stderr}"
    if stderr and stdout:
        return f"{stdout}\n\n[AVISO] {stderr}"
    return stdout or "[OK] Sin salida."


# ------------------------------------------------------------------
# Las mismas tres funciones, ahora sin interpolacion
# ------------------------------------------------------------------

def get_user_info(username: str) -> str:
    """Consulta un usuario local."""
    return run_ps(
        "Get-LocalUser -Name $Usuario | Select-Object Name, Enabled | ConvertTo-Json",
        {"Usuario": username},
        strict=False,
    )


def list_directory(path: str) -> str:
    """Lista un directorio."""
    return run_ps(
        "Get-ChildItem -Path $Ruta | Select-Object -First 20 Name | ConvertTo-Json",
        {"Ruta": path},
        strict=False,
    )


def search_software(name_filter: str) -> str:
    """Busca software instalado.

    Ojo con el detalle: aqui el valor se usa dentro de -like, que necesita los
    comodines. Se construyen en PowerShell, no en Python.
    """
    script = r"""
$patron = "*$Filtro*"
Get-ItemProperty HKLM:\Software\Microsoft\Windows\CurrentVersion\Uninstall\* |
    Where-Object { $_.DisplayName -like $patron } |
    Select-Object -First 20 DisplayName | ConvertTo-Json
"""
    return run_ps(script, {"Filtro": name_filter}, strict=False)
