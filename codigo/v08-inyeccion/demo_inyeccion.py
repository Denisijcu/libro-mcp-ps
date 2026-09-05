# -*- coding: utf-8 -*-
"""
Demostracion medible de la inyeccion de comandos - capitulo 8.

La carga util es deliberadamente inofensiva: escribe un archivo marcador en la
carpeta temporal del usuario. Si el archivo aparece, es que PowerShell ejecuto
codigo que el programador nunca escribio.

Uso:
    python demo_inyeccion.py

No requiere dependencias externas ni el SDK de MCP.
"""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import seguro
import vulnerable

MARCADOR = Path(os.environ.get("TEMP", ".")) / "PWNED_DEMO_CAP8.txt"

# Carga util: cierra la comilla que abrio el f-string, ejecuta su propio comando
# y vuelve a abrir una comilla para que el resto de la linea siga siendo valido.
PAYLOAD = (
    "denis'; Set-Content -Path $env:TEMP\\PWNED_DEMO_CAP8.txt "
    "-Value 'inyeccion ejecutada'; '"
)


def limpiar():
    if MARCADOR.exists():
        MARCADOR.unlink()


def probar(modulo, etiqueta: str) -> bool:
    limpiar()
    print(f"\n=== {etiqueta} ===")
    salida = modulo.get_user_info(PAYLOAD)
    print(f"Valor enviado : {PAYLOAD}")
    print(f"Salida        : {salida[:160]}")
    if MARCADOR.exists():
        contenido = MARCADOR.read_text(encoding="utf-8", errors="replace").strip()
        print(f"RESULTADO     : VULNERABLE. Se creo {MARCADOR}")
        print(f"                Contenido: {contenido}")
        limpiar()
        return True
    print(f"RESULTADO     : SEGURO. No se creo {MARCADOR}")
    return False


def probar_funcionalidad():
    """El arreglo no sirve de nada si rompe el uso normal. Se comprueba."""
    print("\n=== Comprobacion de que la version segura sigue funcionando ===")
    usuario = os.environ.get("USERNAME", "")
    print(f"get_user_info('{usuario}') -> {seguro.get_user_info(usuario)[:120]}")
    print(f"list_directory('C:\\\\')     -> {seguro.list_directory('C:\\')[:120]}")
    print(f"search_software('Python')  -> {seguro.search_software('Python')[:120]}")


if __name__ == "__main__":
    print("Demostracion de inyeccion de comandos en un servidor MCP de PowerShell")
    print("Carga util inofensiva: crear un archivo marcador en %TEMP%")

    vulnerado = probar(vulnerable, "VERSION VULNERABLE (f-string)")
    protegido = not probar(seguro, "VERSION SEGURA (variables de entorno)")

    probar_funcionalidad()

    print("\n--- VEREDICTO ---")
    print(f"La version con f-string ejecuto codigo ajeno : {vulnerado}")
    print(f"La version con env vars resistio             : {protegido}")
    sys.exit(0 if (vulnerado and protegido) else 1)
