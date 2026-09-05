# -*- coding: utf-8 -*-
"""
Capitulo 14: triage. Convierte hallazgos sueltos en un veredicto.

Diseno deliberado: la puntuacion se calcula en PYTHON, no en el modelo, y las
reglas estan escritas en un solo sitio para poder discutirlas. Un numero que
sale de un algoritmo legible se puede corregir; un numero que sale del criterio
de un modelo, no.

El semaforo que devuelve es SUGERIDO. La decision final es del analista, y la
herramienta esta escrita para ayudarle a decidir rapido, no para decidir por el.

Probar el motor de puntuacion sin tocar la maquina:
    python triage.py --autoprueba
"""

import argparse
import json
import sys
from typing import Any, Dict, List, Optional

# ==================================================================
# LAS REGLAS
# ------------------------------------------------------------------
# Un solo sitio. Si el semaforo se equivoca, se discute esta tabla, no
# el codigo. Cada regla lleva por que pesa lo que pesa.
# ==================================================================

REGLAS = {
    "log_borrado": {
        "puntos": 40,
        "tope": 40,
        "razon": "Borrar el registro de seguridad no es mantenimiento rutinario.",
    },
    "defender_desactivado": {
        "puntos": 35,
        "tope": 35,
        "razon": "La proteccion en tiempo real apagada sin que el usuario lo sepa.",
    },
    "exclusion_defender": {
        "puntos": 12,
        "tope": 36,
        "razon": "Exclusion en el antivirus: discreta, persistente y casi nadie la revisa.",
    },
    "persistencia_sospechosa": {
        "puntos": 15,
        "tope": 45,
        "razon": "Entrada de arranque que invoca un interprete o apunta a carpeta de usuario.",
    },
    "tarea_sospechosa": {
        "puntos": 12,
        "tope": 36,
        "razon": "Tarea programada no-Microsoft que lanza scripts o LOLBins.",
    },
    "conexion_alta": {
        "puntos": 20,
        "tope": 40,
        "razon": "Conexion establecida a un puerto tipico de acceso remoto o C2.",
    },
    "combinacion": {
        "puntos": 20,
        "tope": 40,
        "razon": (
            "Un MISMO artefacto que dispara varios indicadores debiles a la vez. "
            "Un binario sin firmar es ruido. Un binario sin firmar, en AppData y con "
            "base64 en la linea de comandos es otra cosa. La coincidencia vale mas "
            "que la suma de sus partes."
        ),
    },
    "proceso_ruta_usuario": {
        "puntos": 3,
        "tope": 12,
        "razon": (
            "Ejecutable corriendo desde TEMP o AppData. Pesa poco porque es normal: "
            "Discord, Slack, VS Code, Teams y casi toda aplicacion Electron viven "
            "ahi. Solo importa combinado con otra cosa."
        ),
    },
    "cmdline_sospechosa": {
        "puntos": 15,
        "tope": 30,
        "razon": "Linea de comandos con codificacion base64, descarga o ventana oculta.",
    },
    "proceso_sin_firma": {
        "puntos": 1,
        "tope": 5,
        "razon": (
            "Pesa muy poco a proposito: en una maquina de desarrollo normal hay "
            "decenas de binarios legitimos sin firmar (PostgreSQL, Apache, "
            "compilados en local)."
        ),
    },
    "puerto_expuesto": {
        "puntos": 1,
        "tope": 4,
        "razon": (
            "Servicio escuchando en 0.0.0.0: superficie de ataque, no compromiso. "
            "Una maquina de desarrollo tiene varios de forma rutinaria."
        ),
    },
}

UMBRAL_AMARILLO = 15
UMBRAL_ROJO = 45


class Triage:
    """Acumula hallazgos y calcula un semaforo sugerido."""

    def __init__(self) -> None:
        self.hallazgos: List[Dict[str, Any]] = []
        self.huecos: List[str] = []

    def anotar(self, regla: str, detalle: str, cantidad: int = 1) -> None:
        if regla not in REGLAS:
            raise KeyError(f"Regla desconocida: {regla}")
        self.hallazgos.append({"regla": regla, "detalle": detalle, "cantidad": cantidad})

    def hueco(self, descripcion: str) -> None:
        """Registra algo que NO se pudo comprobar.

        Un hueco no suma puntos: rebaja la confianza del veredicto. No es lo
        mismo un verde sobre diez comprobaciones que un verde sobre seis.
        """
        self.huecos.append(descripcion)

    def calcular(self) -> Dict[str, Any]:
        por_regla: Dict[str, int] = {}
        for h in self.hallazgos:
            por_regla[h["regla"]] = por_regla.get(h["regla"], 0) + h["cantidad"]

        desglose = []
        total = 0
        for regla, veces in por_regla.items():
            cfg = REGLAS[regla]
            crudo = cfg["puntos"] * veces
            aplicado = min(crudo, cfg["tope"])
            total += aplicado
            desglose.append({
                "regla": regla,
                "veces": veces,
                "puntos_por_vez": cfg["puntos"],
                "puntos_crudos": crudo,
                "puntos_aplicados": aplicado,
                "topado": crudo > aplicado,
                "razon": cfg["razon"],
            })

        desglose.sort(key=lambda d: d["puntos_aplicados"], reverse=True)

        if total >= UMBRAL_ROJO:
            semaforo = "ROJO"
            lectura = "Indicadores fuertes. Contener antes de seguir investigando."
        elif total >= UMBRAL_AMARILLO:
            semaforo = "AMARILLO"
            lectura = "Hay elementos que hay que revisar uno a uno antes de descartarlos."
        else:
            semaforo = "VERDE"
            lectura = "Sin indicadores relevantes en las comprobaciones realizadas."

        confianza = "alta"
        if self.huecos:
            confianza = "media" if len(self.huecos) <= 2 else "baja"
            if semaforo == "VERDE":
                lectura += (
                    f" Ojo: {len(self.huecos)} comprobacion(es) no se pudieron hacer, "
                    "asi que este verde es parcial."
                )

        return {
            "semaforo_sugerido": semaforo,
            "puntuacion": total,
            "umbrales": {"amarillo": UMBRAL_AMARILLO, "rojo": UMBRAL_ROJO},
            "confianza": confianza,
            "lectura": lectura,
            "desglose": desglose,
            "hallazgos": self.hallazgos,
            "comprobaciones_no_realizadas": self.huecos,
            "aviso": (
                "Semaforo SUGERIDO, calculado con reglas fijas. No sustituye al criterio "
                "del analista. Contrasta cada hallazgo con lo que el usuario sabe que "
                "instalo antes de dar un veredicto."
            ),
        }


# ==================================================================
# AUTOPRUEBA
# ==================================================================

ESCENARIOS = {
    "maquina-limpia-desarrollo": {
        "descripcion": "La maquina de referencia del libro: 15 binarios sin firmar "
                       "(PostgreSQL, Apache), un ejecutable en AppData, dos puertos "
                       "locales expuestos. Nada coincide en el mismo artefacto.",
        "esperado": "VERDE",
        "hallazgos": [
            ("proceso_sin_firma", "postgres.exe x10, httpd.exe x2, otros x3", 15),
            ("proceso_ruta_usuario", "una aplicacion Electron en AppData", 1),
            ("puerto_expuesto", "dos servicios en 0.0.0.0", 2),
        ],
        "huecos": [],
    },
    "indicadores-que-coinciden": {
        "descripcion": "Los mismos indicadores debiles de arriba, pero todos sobre EL "
                       "MISMO proceso: sin firmar, en AppData y con base64 en la linea "
                       "de comandos.",
        "esperado": "AMARILLO",
        "hallazgos": [
            ("proceso_sin_firma", "updater.exe", 1),
            ("proceso_ruta_usuario", "updater.exe en AppData\\Local\\Temp", 1),
            ("cmdline_sospechosa", "updater.exe con FromBase64String", 1),
            ("combinacion", "updater.exe dispara 3 indicadores a la vez", 1),
        ],
        "huecos": [],
    },
    "sospechoso-un-indicio": {
        "descripcion": "Una tarea programada que lanza PowerShell codificado. "
                       "Puede ser un instalador mal hecho o puede no serlo.",
        "esperado": "AMARILLO",
        "hallazgos": [
            ("tarea_sospechosa", "Updater lanza powershell -enc", 1),
            ("proceso_sin_firma", "varios binarios de desarrollo", 8),
        ],
        "huecos": [],
    },
    "comprometido": {
        "descripcion": "Persistencia en el registro, conexion a 4444 y una exclusion "
                       "en Defender que el usuario no puso.",
        "esperado": "ROJO",
        "hallazgos": [
            ("persistencia_sospechosa", "HKCU Run -> powershell -w hidden -enc", 1),
            ("conexion_alta", "45.x.x.x:4444 desde updater.exe", 1),
            ("exclusion_defender", "C:\\Users\\Public excluido", 1),
            ("cmdline_sospechosa", "updater.exe con FromBase64String", 1),
        ],
        "huecos": [],
    },
    "verde-poco-fiable": {
        "descripcion": "Nada encontrado, pero el servidor corre sin privilegios y no "
                       "pudo leer el log de seguridad ni las tareas del sistema.",
        "esperado": "VERDE",
        "hallazgos": [
            ("proceso_sin_firma", "binarios de desarrollo", 4),
        ],
        "huecos": [
            "Log de seguridad: acceso denegado (hace falta administrador)",
            "Claves Run de HKLM: acceso denegado",
            "Exclusiones de Defender: Get-MpPreference no disponible",
        ],
    },
}


def autoprueba() -> int:
    fallos = 0
    for nombre, esc in ESCENARIOS.items():
        t = Triage()
        for regla, detalle, cantidad in esc["hallazgos"]:
            t.anotar(regla, detalle, cantidad)
        for h in esc["huecos"]:
            t.hueco(h)

        r = t.calcular()
        correcto = r["semaforo_sugerido"] == esc["esperado"]
        if not correcto:
            fallos += 1

        print(f"[{'PASA ' if correcto else 'FALLA'}] {nombre}")
        print(f"         {esc['descripcion']}")
        print(f"         esperado {esc['esperado']}, obtenido {r['semaforo_sugerido']} "
              f"({r['puntuacion']} puntos, confianza {r['confianza']})")
        for d in r["desglose"]:
            tope = "  [TOPADO]" if d["topado"] else ""
            print(f"           {d['puntos_aplicados']:>3} pts  {d['regla']} x{d['veces']}{tope}")
        if r["comprobaciones_no_realizadas"]:
            print(f"         huecos: {len(r['comprobaciones_no_realizadas'])}")
        print(f"         lectura: {r['lectura']}")
        print()

    print("TODO CORRECTO" if fallos == 0 else f"{fallos} FALLO(S)")
    return 0 if fallos == 0 else 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Motor de triage del capitulo 14")
    parser.add_argument("--autoprueba", action="store_true",
                        help="Ejecuta los cuatro escenarios de prueba")
    parser.add_argument("--reglas", action="store_true",
                        help="Imprime la tabla de reglas y sale")
    args = parser.parse_args()

    if args.reglas:
        print(json.dumps(REGLAS, ensure_ascii=False, indent=2))
        sys.exit(0)
    if args.autoprueba:
        sys.exit(autoprueba())

    parser.print_help()
