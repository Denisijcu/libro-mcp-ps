# -*- coding: utf-8 -*-
"""
Capitulo 9: control de autoridad para un servidor MCP.

Tres capas independientes, de mas general a mas concreta:

  1. GATE       - por nivel de dano: read / write / destructive.
                  Se controla con variables de entorno al arrancar.
  2. LISTAS     - objetivos que nunca se tocan, cueste lo que cueste.
  3. TOKEN      - confirmacion de un solo uso, atada a la accion Y al objetivo.

Este modulo no sabe nada de PowerShell. Es solo la logica de autoridad, para
que se pueda leer y probar por separado.

Probar:  python gates.py
"""

import functools
import inspect
import os
import secrets
import time
from typing import Any, Dict, Optional

# ------------------------------------------------------------------
# 1. CONFIGURACION DE ARRANQUE
# ------------------------------------------------------------------
# Por defecto todo cerrado. Abrir requiere una decision consciente al
# lanzar el servidor, no un cambio de codigo.


def _flag(nombre: str) -> bool:
    return os.getenv(nombre, "0").strip().lower() in ("1", "true", "yes", "si", "on")


PERMITIR_ESCRITURA = _flag("PSMCP_ALLOW_WRITE")
PERMITIR_DESTRUCTIVO = _flag("PSMCP_ALLOW_DESTRUCTIVE")

TTL_TOKEN = int(os.getenv("PSMCP_CONFIRM_TTL", "180"))  # segundos

# ------------------------------------------------------------------
# 2. LISTAS DE PROTECCION
# ------------------------------------------------------------------
# Cortas, estables y justificadas. Cada entrada tiene una razon concreta,
# no esta ahi "por si acaso".

# Matar cualquiera de estos tumba la sesion o provoca pantallazo azul.
PROCESOS_PROTEGIDOS = {
    "system", "registry", "smss", "csrss", "wininit", "winlogon",
    "services", "lsass", "lsaiso", "dwm", "fontdrvhost", "svchost",
}

# Pararlos deja la maquina ciega o indefensa. Son el primer objetivo
# de cualquier atacante que ya esta dentro.
SERVICIOS_PROTEGIDOS = {
    "windefend",   # Defender
    "wdnissvc",    # inspeccion de red de Defender
    "sense",       # Defender for Endpoint
    "mpssvc",      # firewall
    "bfe",         # motor de filtrado, debajo del firewall
    "eventlog",    # registro de eventos: sin el no hay forense
    "cryptsvc",    # servicios criptograficos
    "dcomlaunch",  # nucleo: pararlo reinicia la maquina
    "rpcss",       # nucleo
}


# ------------------------------------------------------------------
# 3. GATE POR NIVEL
# ------------------------------------------------------------------

def comprobar_gate(nivel: str) -> Optional[str]:
    """Devuelve un mensaje de bloqueo, o None si la operacion puede seguir."""
    if nivel == "read":
        return None

    if not PERMITIR_ESCRITURA:
        # Si la operacion es destructiva hacen falta las dos variables. Se dicen
        # las dos de una vez: descubrir el segundo bloqueo despues de arreglar
        # el primero es una perdida de tiempo evitable.
        if nivel == "destructive":
            return ("[BLOQUEADO] El servidor esta en modo SOLO LECTURA y ademas esta "
                    "operacion es destructiva. Requiere PSMCP_ALLOW_WRITE=1 y "
                    "PSMCP_ALLOW_DESTRUCTIVE=1 al arrancar el servidor.")
        return ("[BLOQUEADO] El servidor esta en modo SOLO LECTURA. "
                "Para permitir cambios, reinicia con PSMCP_ALLOW_WRITE=1.")

    if nivel == "destructive" and not PERMITIR_DESTRUCTIVO:
        return ("[BLOQUEADO] Operacion destructiva deshabilitada. "
                "Requiere PSMCP_ALLOW_DESTRUCTIVE=1 ademas de PSMCP_ALLOW_WRITE=1.")

    return None


# ------------------------------------------------------------------
# 4. TOKENS DE CONFIRMACION
# ------------------------------------------------------------------
# Un token vale para UNA accion sobre UN objetivo, una sola vez, durante
# un rato corto. Que este atado al objetivo es lo que impide reutilizar
# el permiso de borrar A para borrar B.

_TOKENS: Dict[str, tuple] = {}


def _emitir_token(clave_accion: str) -> str:
    token = secrets.token_hex(4).upper()
    _TOKENS[token] = (clave_accion, time.time())
    for viejo, (_, nacido) in list(_TOKENS.items()):
        if time.time() - nacido > TTL_TOKEN:
            _TOKENS.pop(viejo, None)
    return token


def _consumir_token(clave_accion: str, token: str) -> bool:
    entrada = _TOKENS.get(token.strip().upper())
    if not entrada:
        return False
    clave_guardada, nacido = entrada
    if clave_guardada != clave_accion:
        return False
    if time.time() - nacido > TTL_TOKEN:
        _TOKENS.pop(token.strip().upper(), None)
        return False
    _TOKENS.pop(token.strip().upper(), None)  # un solo uso
    return True


def pedir_confirmacion(clave_accion: str, impacto: str, token: str) -> Optional[str]:
    """None si el token es valido; si no, el mensaje que se devuelve al modelo."""
    if not token:
        nuevo = _emitir_token(clave_accion)
        return (
            "[CONFIRMACION REQUERIDA]\n"
            f"Accion  : {clave_accion}\n"
            f"Impacto : {impacto}\n"
            f"Token   : {nuevo}  (valido {TTL_TOKEN} segundos, un solo uso)\n\n"
            "Muestra este impacto al usuario, espera su aprobacion explicita y vuelve a "
            "llamar a la misma herramienta anadiendo confirm_token."
        )

    if not _consumir_token(clave_accion, token):
        return ("[ERROR] El confirm_token no es valido, ha expirado, ya se uso, o "
                "pertenece a otra accion u otro objetivo. Pide uno nuevo.")

    return None


# ------------------------------------------------------------------
# 5. EL DECORADOR
# ------------------------------------------------------------------

NIVELES_VALIDOS = ("read", "write", "destructive")


def guard(nivel: str = "read"):
    """Envuelve una herramienta y le aplica el gate de su nivel."""
    if nivel not in NIVELES_VALIDOS:
        raise ValueError(f"Nivel desconocido: {nivel}")

    def decorador(func):
        firma = inspect.signature(func)

        @functools.wraps(func)
        def envoltorio(*args, **kwargs):
            bloqueo = comprobar_gate(nivel)
            if bloqueo:
                return bloqueo
            try:
                return func(*args, **kwargs)
            except Exception as exc:
                return f"[ERROR] {type(exc).__name__}: {exc}"

        envoltorio.__signature__ = firma
        envoltorio._nivel_psmcp = nivel
        return envoltorio

    return decorador


# ------------------------------------------------------------------
# 6. AUTOPRUEBA
# ------------------------------------------------------------------

if __name__ == "__main__":
    print(f"Escritura permitida  : {PERMITIR_ESCRITURA}")
    print(f"Destructivo permitido: {PERMITIR_DESTRUCTIVO}\n")

    @guard("read")
    def leer_algo() -> str:
        return "[OK] datos leidos"

    @guard("write")
    def escribir_algo() -> str:
        return "[OK] algo escrito"

    @guard("destructive")
    def borrar_usuario(nombre: str, confirm_token: str = "") -> str:
        pendiente = pedir_confirmacion(
            f"borrar_usuario:{nombre.lower()}",
            f"Se eliminara la cuenta local '{nombre}'. No se puede deshacer.",
            confirm_token,
        )
        if pendiente:
            return pendiente
        return f"[OK] usuario {nombre} eliminado (simulado)"

    print("1. Lectura           ->", leer_algo())
    print("2. Escritura         ->", escribir_algo().split("\n")[0])
    print("3. Destructiva       ->", borrar_usuario("pruebas").split("\n")[0])

    if PERMITIR_ESCRITURA and PERMITIR_DESTRUCTIVO:
        print("\n--- flujo completo del token ---")
        primera = borrar_usuario("pruebas")
        print(primera)
        token = [l for l in primera.splitlines() if l.startswith("Token")][0].split()[2]

        print("\n4. Token de otro objetivo ->", borrar_usuario("otro", confirm_token=token))
        print("5. Token correcto         ->", borrar_usuario("pruebas", confirm_token=token))
        print("6. Reutilizar el token    ->", borrar_usuario("pruebas", confirm_token=token))
    else:
        print("\nPara ver el flujo del token, relanza asi:")
        print("  $env:PSMCP_ALLOW_WRITE=1; $env:PSMCP_ALLOW_DESTRUCTIVE=1; python gates.py")
