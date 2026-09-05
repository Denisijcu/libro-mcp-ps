# -*- coding: utf-8 -*-
"""
Capitulo 10: sandbox de rutas, auditoria y limites de salida.

Tres piezas que responden a tres preguntas distintas:

    sandbox   -> DONDE puede tocar el servidor
    auditoria -> QUE se hizo, aunque saliera bien
    limites   -> CUANTO texto puede devolver sin ahogar al modelo

Probar:  python test_sandbox.py
"""

import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

# ==================================================================
# 1. SANDBOX DE RUTAS
# ==================================================================

_INICIO = os.path.expanduser("~")

# Lista blanca: fuera de estas raices no se escribe. Configurable al arrancar.
RAICES_ESCRITURA = [
    p.strip()
    for p in os.getenv("PSMCP_FS_WRITE_ROOTS", _INICIO).split(";")
    if p.strip()
]

# Lista negra: prohibido aunque caiga dentro de una raiz permitida.
RUTAS_PROHIBIDAS = [
    r"c:\windows",
    r"c:\program files",
    r"c:\program files (x86)",
    r"c:\programdata\microsoft\windows",
    r"c:\$recycle.bin",
    r"c:\boot",
    r"c:\efi",
    r"c:\system volume information",
]

# Profundidad minima: C:\algo tiene 2 partes. Exigimos 3 para no permitir
# operar sobre carpetas de primer nivel del disco.
PARTES_MINIMAS = 3


def normalizar(ruta: str) -> str:
    """Convierte una ruta a su forma canonica para poder compararla.

    Hace cuatro cosas, y las cuatro hacen falta:
      - expande %VARIABLES% y ~
      - la vuelve absoluta
      - resuelve ..\\..\\ y los enlaces simbolicos (realpath, no abspath)
      - la pasa a minusculas, porque Windows no distingue mayusculas
    """
    expandida = os.path.expandvars(os.path.expanduser(ruta))
    return os.path.normcase(os.path.realpath(expandida))


def es_ruta_prohibida(ruta: str) -> bool:
    objetivo = normalizar(ruta)
    return any(objetivo.startswith(prefijo) for prefijo in RUTAS_PROHIBIDAS)


def comprobar_ruta_escritura(ruta: str) -> Optional[str]:
    """None si se puede escribir ahi. Si no, el motivo del bloqueo."""
    if not ruta or not ruta.strip():
        return "[BLOQUEADO] Ruta vacia."

    if any(comodin in ruta for comodin in ("*", "?")):
        return "[BLOQUEADO] No se aceptan comodines en operaciones de escritura."

    objetivo = normalizar(ruta)

    if len(Path(objetivo).parts) < PARTES_MINIMAS:
        return f"[BLOQUEADO] Ruta demasiado cerca de la raiz del disco: {objetivo}"

    if es_ruta_prohibida(objetivo):
        return f"[BLOQUEADO] Ruta protegida del sistema: {objetivo}"

    for raiz in RAICES_ESCRITURA:
        if objetivo.startswith(normalizar(raiz)):
            return None

    permitidas = "; ".join(RAICES_ESCRITURA)
    return f"[BLOQUEADO] Fuera del sandbox de escritura. Raices permitidas: {permitidas}"


# ==================================================================
# 2. AUDITORIA
# ==================================================================

RUTA_AUDITORIA = Path(
    os.getenv("PSMCP_AUDIT_LOG", str(Path(_INICIO) / ".psmcp" / "audit.jsonl"))
)

# Cualquier parametro cuyo nombre encaje aqui se sustituye antes de escribir.
CLAVES_SENSIBLES = re.compile(r"(pass|pwd|secret|token|cred|apikey|key)", re.IGNORECASE)

LIMITE_VALOR_AUDITADO = 300


def redactar(parametros: Dict[str, Any]) -> Dict[str, Any]:
    limpio: Dict[str, Any] = {}
    for clave, valor in parametros.items():
        if CLAVES_SENSIBLES.search(clave):
            limpio[clave] = "***REDACTADO***"
        elif isinstance(valor, str) and len(valor) > LIMITE_VALOR_AUDITADO:
            limpio[clave] = valor[:LIMITE_VALOR_AUDITADO] + "...[cortado]"
        else:
            limpio[clave] = valor
    return limpio


def auditar(herramienta: str, parametros: Dict[str, Any], estado: str,
            nivel: str, segundos: float) -> None:
    """Escribe una linea JSON. Nunca lanza excepciones: si falla, se calla."""
    registro = {
        "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "herramienta": herramienta,
        "nivel": nivel,
        "estado": estado,
        "segundos": round(segundos, 3),
        "parametros": redactar(parametros),
    }
    try:
        RUTA_AUDITORIA.parent.mkdir(parents=True, exist_ok=True)
        with RUTA_AUDITORIA.open("a", encoding="utf-8") as fichero:
            fichero.write(json.dumps(registro, ensure_ascii=False, default=str) + "\n")
    except Exception:
        pass  # la auditoria jamas puede tumbar el servidor


# ==================================================================
# 3. LIMITES DE SALIDA
# ==================================================================

MAX_CARACTERES = int(os.getenv("PSMCP_MAX_OUTPUT_CHARS", "40000"))
MAX_ELEMENTOS = int(os.getenv("PSMCP_MAX_ITEMS", "50"))


def truncar(texto: str) -> str:
    """Corta la salida y AVISA de que la corto."""
    if texto is None:
        return ""
    if len(texto) <= MAX_CARACTERES:
        return texto
    return (
        texto[:MAX_CARACTERES]
        + f"\n\n...[SALIDA CORTADA en {MAX_CARACTERES} caracteres de "
        + f"{len(texto)} totales. Afina el filtro o reduce el rango.]"
    )


def limitar(valor: int, minimo: int, maximo: int) -> int:
    """Encierra un numero en un rango. Para los parametros que da el modelo."""
    return max(minimo, min(int(valor), maximo))
