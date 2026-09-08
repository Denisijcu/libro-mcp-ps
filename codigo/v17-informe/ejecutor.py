# -*- coding: utf-8 -*-
"""
El ejecutor del libro, acumulado hasta el capitulo 12.

Junta lo que se fue construyendo:
  - Capitulo 3 : manejo de errores y prefijos [ERROR]/[AVISO]
  - Capitulo 8 : parametros por variables de entorno + -EncodedCommand
  - Capitulo 8 : epilogo que recupera $Error para que no haya errores mudos
  - Capitulo 10: truncado de salida con aviso y limitado de argumentos

A partir de aqui, todos los servidores del libro importan de este modulo.
"""

import base64
import os
import re
import subprocess
from typing import Any, Dict, Optional

PARAM_NAME_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")

MAX_CARACTERES = int(os.getenv("PSMCP_MAX_OUTPUT_CHARS", "40000"))
TIMEOUT_POR_DEFECTO = int(os.getenv("PSMCP_TIMEOUT", "30"))

PS_PRELUDIO = r"""
$ProgressPreference = 'SilentlyContinue'
try { [Console]::OutputEncoding = [System.Text.Encoding]::UTF8 } catch {}
"""

# Con ErrorActionPreference en SilentlyContinue, PowerShell devuelve codigo
# distinto de cero y no escribe nada en stderr. $Error se rellena igual.
PS_EPILOGO = r"""
if ($Error.Count -gt 0) {
    [Console]::Error.WriteLine('PSERROR: ' + $Error[0].Exception.Message)
}
"""


def limitar(valor: int, minimo: int, maximo: int) -> int:
    """Encierra un numero en un rango. Para los argumentos que manda el modelo."""
    return max(minimo, min(int(valor), maximo))


def truncar(texto: str) -> str:
    """Corta la salida y avisa de que la corto."""
    if not texto:
        return ""
    if len(texto) <= MAX_CARACTERES:
        return texto
    return (
        texto[:MAX_CARACTERES]
        + f"\n\n...[SALIDA CORTADA en {MAX_CARACTERES} caracteres de "
        + f"{len(texto)} totales. Afina el filtro o reduce el rango.]"
    )


def run_ps(
    script: str,
    params: Optional[Dict[str, Any]] = None,
    timeout: int = TIMEOUT_POR_DEFECTO,
    strict: bool = True,
) -> str:
    """Ejecuta PowerShell sin interpolar ningun valor en el codigo del script."""
    env = os.environ.copy()
    preambulo = []

    for nombre, valor in (params or {}).items():
        if not PARAM_NAME_RE.match(nombre):
            return f"[ERROR] Nombre de parametro invalido: {nombre}"
        clave = "PSMCP_P_" + nombre.upper()
        env[clave] = "" if valor is None else str(valor)
        preambulo.append(f"${nombre} = $env:{clave}")

    preferencia = "Stop" if strict else "SilentlyContinue"
    completo = (
        f"$ErrorActionPreference = '{preferencia}'\n"
        + PS_PRELUDIO
        + "\n".join(preambulo)
        + "\n"
        + script
        + PS_EPILOGO
    )
    codificado = base64.b64encode(completo.encode("utf-16-le")).decode("ascii")

    try:
        resultado = subprocess.run(
            [
                "powershell.exe",
                "-NoProfile", "-NonInteractive", "-NoLogo",
                "-ExecutionPolicy", "Bypass",
                "-EncodedCommand", codificado,
            ],
            capture_output=True, text=True, encoding="utf-8",
            errors="replace", timeout=timeout, env=env,
        )
    except subprocess.TimeoutExpired:
        return f"[ERROR] El comando excedio el timeout de {timeout} segundos."
    except FileNotFoundError:
        return "[ERROR] No se encontro powershell.exe en este sistema."

    salida = (resultado.stdout or "").strip()
    error = (resultado.stderr or "").strip()

    if resultado.returncode != 0:
        detalle = error or salida or "el comando fallo sin devolver mensaje"
        return f"[ERROR] Codigo {resultado.returncode}: {detalle}"
    if error.startswith("PSERROR:") and not salida:
        return f"[ERROR] {error}"
    if error and salida:
        return truncar(f"{salida}\n\n[AVISO] {error}")
    return truncar(salida) or "[OK] El comando se ejecuto pero no devolvio nada."
