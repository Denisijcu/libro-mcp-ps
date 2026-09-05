# -*- coding: utf-8 -*-
"""
Capitulo 16: comprobacion de salud del servidor.

Se ejecuta a mano, sin host y sin modelo, y responde a la pregunta que uno se
hace cuando algo no funciona: ?el problema es mio o del cliente?

    python diagnostico.py

Sale con codigo 0 si todo esta listo, 1 si algo falla.
"""

import importlib
import json
import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path

VERSION_SERVIDOR = "1.0.0"
PYTHON_MINIMO = (3, 10)


class Resultado:
    def __init__(self) -> None:
        self.fallos = 0
        self.avisos = 0

    def ok(self, titulo: str, detalle: str = "") -> None:
        print(f"  [OK   ] {titulo}" + (f"  {detalle}" if detalle else ""))

    def aviso(self, titulo: str, detalle: str) -> None:
        self.avisos += 1
        print(f"  [AVISO] {titulo}  {detalle}")

    def fallo(self, titulo: str, detalle: str) -> None:
        self.fallos += 1
        print(f"  [FALLO] {titulo}  {detalle}")


def comprobar_python(r: Resultado) -> None:
    print("\nPython")
    actual = sys.version_info[:2]
    if actual >= PYTHON_MINIMO:
        r.ok("Version", f"{platform.python_version()}")
    else:
        r.fallo("Version", f"{platform.python_version()}, se necesita "
                           f"{PYTHON_MINIMO[0]}.{PYTHON_MINIMO[1]} o superior")

    # Que el host use ESTE interprete y no otro es el fallo mas comun.
    r.ok("Interprete", sys.executable)
    en_venv = sys.prefix != sys.base_prefix
    if en_venv:
        r.ok("Entorno virtual", "activo")
    else:
        r.aviso("Entorno virtual", "no estas en un venv; el host debe apuntar a este mismo python.exe")


def comprobar_sdk(r: Resultado) -> None:
    print("\nSDK de MCP")
    try:
        import mcp  # noqa: F401
    except ImportError:
        r.fallo("Paquete mcp", "no instalado. pip install \"mcp[cli]>=1.10,<2\"")
        return

    version = getattr(mcp, "__version__", None)
    if version is None:
        try:
            from importlib.metadata import version as leer_version
            version = leer_version("mcp")
        except Exception:
            version = "desconocida"

    try:
        importlib.import_module("mcp.server.fastmcp")
        r.ok("API 1.x disponible", f"mcp {version}")
    except ModuleNotFoundError:
        r.fallo(
            "API 1.x no disponible",
            f"mcp {version} parece 2.x: FastMCP se renombro a MCPServer y "
            "mcp.server.fastmcp desaparecio. Reinstala con la restriccion <2",
        )


def comprobar_powershell(r: Resultado) -> None:
    print("\nPowerShell")
    ruta = shutil.which("powershell.exe")
    if not ruta:
        r.fallo("powershell.exe", "no esta en el PATH")
        return
    r.ok("Ejecutable", ruta)

    try:
        proceso = subprocess.run(
            ["powershell.exe", "-NoProfile", "-NonInteractive", "-NoLogo",
             "-Command", "$PSVersionTable.PSVersion.ToString()"],
            capture_output=True, text=True, encoding="utf-8", timeout=30,
        )
    except Exception as exc:
        r.fallo("Ejecucion", f"{type(exc).__name__}: {exc}")
        return

    if proceso.returncode != 0:
        r.fallo("Ejecucion", f"codigo {proceso.returncode}: {proceso.stderr.strip()[:120]}")
        return
    r.ok("Version", proceso.stdout.strip())

    # El canal de parametros del capitulo 8, comprobado de punta a punta.
    #
    # OJO con el diseno de la carga util: si el marcador aparece tal cual dentro
    # del valor, la prueba lo encuentra en la salida AUNQUE no se haya ejecutado
    # nada, y da un falso positivo. Por eso el marcador va partido en dos: solo
    # existe entero si PowerShell evalua la concatenacion, es decir, solo si la
    # inyeccion funciono.
    carga = "valor'; Write-Output ('INYEC' + 'TADO'); '"
    marcador = "INYEC" + "TADO"

    entorno = os.environ.copy()
    entorno["PSMCP_P_PRUEBA"] = carga
    try:
        proceso = subprocess.run(
            ["powershell.exe", "-NoProfile", "-NonInteractive", "-NoLogo",
             "-Command", "Write-Output $env:PSMCP_P_PRUEBA"],
            capture_output=True, text=True, encoding="utf-8", timeout=30, env=entorno,
        )
        salida = proceso.stdout.strip()

        if marcador in salida:
            r.fallo("Canal de parametros", "el valor se ejecuto como codigo")
        elif salida == carga:
            # La comprobacion fuerte: la salida es identica a la entrada, byte
            # a byte. Nada se evaluo, nada se transformo.
            r.ok("Canal de parametros", "el valor llega intacto y como texto")
        else:
            r.aviso("Canal de parametros",
                    f"no se ejecuto, pero la salida difiere de la entrada: {salida[:80]!r}")
    except Exception as exc:
        r.aviso("Canal de parametros", f"no se pudo comprobar: {exc}")


def comprobar_permisos(r: Resultado) -> None:
    print("\nPrivilegios")
    try:
        import ctypes
        elevado = bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        elevado = False

    if elevado:
        r.aviso(
            "Sesion elevada",
            "el servidor correria como administrador. Recomendado NO hacerlo: "
            "todo lo que expongas se ejecuta con esos permisos",
        )
    else:
        r.ok("Sesion normal", "sin elevacion, que es lo recomendado")
        print("         Nota: sin privilegios no se leen el log de seguridad ni")
        print("         algunas claves de maquina. Las herramientas deben decirlo.")


def comprobar_configuracion(r: Resultado) -> None:
    print("\nConfiguracion del servidor")
    banderas = {
        "PSMCP_ALLOW_WRITE": "permite modificar el sistema",
        "PSMCP_ALLOW_DESTRUCTIVE": "permite operaciones irreversibles",
        "PSMCP_ALLOW_DOMAIN": "habilita herramientas de Active Directory",
    }
    for nombre, significado in banderas.items():
        valor = os.getenv(nombre, "0")
        activa = valor.strip().lower() in ("1", "true", "yes", "si", "on")
        if activa:
            r.aviso(nombre, f"ACTIVADA - {significado}")
        else:
            r.ok(nombre, "cerrada")

    perfil = os.getenv("PSMCP_PROFILE", "full")
    r.ok("PSMCP_PROFILE", perfil)

    raices = os.getenv("PSMCP_FS_WRITE_ROOTS", os.path.expanduser("~"))
    r.ok("Sandbox de escritura", raices)


def comprobar_stdout(r: Resultado) -> None:
    print("\nHigiene del protocolo")
    # Un import que imprima en stdout rompe el transporte stdio en silencio.
    # Aqui solo se recuerda; detectarlo automaticamente exige reejecutar el
    # servidor y comparar, y eso pertenece a la suite de pruebas.
    r.ok("Recordatorio", "ningun print() a stdout en el servidor: solo stderr")


def main() -> int:
    print("=" * 62)
    print(f" Diagnostico del servidor MCP de PowerShell  v{VERSION_SERVIDOR}")
    print(f" {platform.platform()}")
    print("=" * 62)

    r = Resultado()
    comprobar_python(r)
    comprobar_sdk(r)
    comprobar_powershell(r)
    comprobar_permisos(r)
    comprobar_configuracion(r)
    comprobar_stdout(r)

    print("\n" + "=" * 62)
    if r.fallos:
        print(f" {r.fallos} FALLO(S) y {r.avisos} aviso(s). El servidor NO va a funcionar.")
    elif r.avisos:
        print(f" Listo, con {r.avisos} aviso(s). Revisalos antes de dejarlo suelto.")
    else:
        print(" Todo correcto. El servidor deberia arrancar sin problemas.")
    print("=" * 62)

    print("\nSi el diagnostico pasa y el host sigue sin ver el servidor, el")
    print("problema esta en la configuracion del cliente, no aqui. Comprueba:")
    print("  - ruta absoluta en el JSON, con las barras dobladas")
    print("  - que 'command' apunte a ESTE python:")
    print(f"      {sys.executable}")
    print("  - que la aplicacion se haya cerrado del todo y reabierto")

    return 1 if r.fallos else 0


if __name__ == "__main__":
    sys.exit(main())
