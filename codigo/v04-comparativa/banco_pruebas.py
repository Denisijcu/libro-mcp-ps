# -*- coding: utf-8 -*-
"""
Capitulo 4: banco de pruebas de seleccion de herramientas.

Mide una sola cosa, la que de verdad importa cuando cambias de modelo:
dado un catalogo de herramientas y una peticion en lenguaje natural,
?el modelo elige la herramienta correcta con los argumentos correctos?

No mide calidad de redaccion ni razonamiento. Mide acierto en tool calling.

COMO FUNCIONA
-------------
Habla con LM Studio por su API compatible con OpenAI (por defecto en
http://127.0.0.1:1234). No ejecuta ninguna herramienta de verdad: solo mira
que herramienta habria llamado el modelo y con que argumentos. Es un banco de
pruebas en seco, asi que se puede correr sin miedo.

REQUISITOS
----------
    pip install requests
    LM Studio abierto, con un modelo cargado y el servidor local activo.

USO
---
    python banco_pruebas.py                      # usa el primer modelo cargado
    python banco_pruebas.py --modelo gemma-4-12b
    python banco_pruebas.py --listar             # ve que modelos hay

Los resultados se guardan en resultados_<modelo>.json y se imprime una tabla.
"""

import argparse
import json
import os
import re
import sys
import time
from typing import Any, Dict, List, Optional
import os

try:
    import requests
except ImportError:
    print("Falta la libreria requests. Instala con: pip install requests", file=sys.stderr)
    sys.exit(1)

BASE_URL = "http://127.0.0.1:1234/v1"
CLAUDE_URL = "https://api.anthropic.com/v1/messages"
CLAUDE_MODELO = "claude-sonnet-5"
TIMEOUT = 300  # generoso: la primera llamada incluye cargar el modelo en VRAM

NOMBRES_HERRAMIENTAS = ("get_date", "get_disk_space", "get_service", "get_top_processes")


def detectar_llamada_en_texto(texto: str) -> Optional[Dict[str, Any]]:
    """Busca una llamada a herramienta escrita como TEXTO en vez de emitida
    por el campo tool_calls del protocolo.

    Es un fallo distinto de "no supo que herramienta usar": el modelo acerto
    el razonamiento y erro el canal. En un cliente MCP real esa llamada no
    ocurre nunca, pero la causa y el arreglo son otros.
    """
    if not texto:
        return None

    candidatos = re.findall(r"\{.*?\}", texto, re.DOTALL)
    for bruto in candidatos:
        try:
            datos = json.loads(bruto)
        except json.JSONDecodeError:
            continue
        nombre = datos.get("name") or datos.get("tool") or datos.get("function")
        if isinstance(nombre, str) and nombre in NOMBRES_HERRAMIENTAS:
            argumentos = datos.get("arguments") or datos.get("parameters") or {}
            return {"nombre": nombre, "args": argumentos if isinstance(argumentos, dict) else {}}

    # Ultimo recurso: menciona el nombre exacto de una herramienta en el texto
    for nombre in NOMBRES_HERRAMIENTAS:
        if nombre in texto:
            return {"nombre": nombre, "args": {}, "solo_mencion": True}
    return None

# ------------------------------------------------------------------
# El catalogo de herramientas: las mismas cuatro del capitulo 3,
# descritas en el formato que entiende la API de LM Studio.
# ------------------------------------------------------------------

HERRAMIENTAS = [
    {
        "type": "function",
        "function": {
            "name": "get_date",
            "description": "Gets the current date and time of the Windows machine.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_disk_space",
            "description": (
                "Lists every drive letter with its total, used and free space in GB. "
                "Use it to check whether the machine is running out of disk space."
            ),
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_service",
            "description": (
                "Gets the status, start type and display name of a single Windows service. "
                "Use it to check whether a specific service is running. The name is the short "
                "service name, not the display name: for example 'WinDefend', not "
                "'Microsoft Defender Antivirus Service'."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "service_name": {
                        "type": "string",
                        "description": "Short Windows service name, e.g. 'WinDefend' or 'Spooler'.",
                    }
                },
                "required": ["service_name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_top_processes",
            "description": (
                "Lists the processes using the most memory right now, with their PID and "
                "memory in MB. Use it when the machine feels slow or the user asks what is "
                "consuming resources. Maximum 20 processes."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "count": {
                        "type": "integer",
                        "description": "How many processes to return. Between 1 and 20.",
                    }
                },
            },
        },
    },
]

# ------------------------------------------------------------------
# Los casos de prueba.
#
# esperado = None significa que la respuesta correcta es NO llamar a
# ninguna herramienta. Esos casos son tan importantes como los otros:
# un modelo que llama a algo siempre no esta acertando, esta disparando.
# ------------------------------------------------------------------

CASOS: List[Dict[str, Any]] = [
    {
        "id": "directo-1",
        "prompt": "Que hora es en esta maquina?",
        "esperado": "get_date",
        "args_esperados": {},
        "nota": "Peticion directa, sin ambiguedad.",
    },
    {
        "id": "directo-2",
        "prompt": "Esta corriendo Windows Defender?",
        "esperado": "get_service",
        "args_esperados": {"service_name": "WinDefend"},
        "nota": "Requiere traducir el nombre comercial al nombre corto de servicio.",
    },
    {
        "id": "directo-3",
        "prompt": "Cuanto espacio libre me queda en los discos?",
        "esperado": "get_disk_space",
        "args_esperados": {},
        "nota": "Peticion directa.",
    },
    {
        "id": "indirecto-1",
        "prompt": "La maquina va lentisima, no se que le pasa.",
        "esperado": "get_top_processes",
        "args_esperados": {},
        "nota": "No nombra la herramienta. Hay que inferirla del sintoma.",
    },
    {
        "id": "indirecto-2",
        "prompt": "No me deja guardar archivos, dice que no hay sitio.",
        "esperado": "get_disk_space",
        "args_esperados": {},
        "nota": "Sintoma en vez de peticion.",
    },
    {
        "id": "args-1",
        "prompt": "Ensename los 3 procesos que mas memoria consumen.",
        "esperado": "get_top_processes",
        "args_esperados": {"count": 3},
        "nota": "Comprueba si extrae el numero del enunciado.",
    },
    {
        "id": "args-2",
        "prompt": "Mira si el servicio de la cola de impresion esta activo.",
        "esperado": "get_service",
        "args_esperados": {"service_name": "Spooler"},
        "nota": "Requiere conocimiento de Windows: cola de impresion = Spooler.",
    },
    {
        "id": "limite-1",
        "prompt": "Dame los 500 procesos que mas memoria consumen.",
        "esperado": "get_top_processes",
        "args_esperados": None,
        "nota": "El limite es 20. Se anota que argumento manda, no se juzga.",
    },
    {
        "id": "negativo-1",
        "prompt": "Explicame que es un servicio de Windows y para que sirve.",
        "esperado": None,
        "args_esperados": None,
        "nota": "Pregunta conceptual. No deberia llamar a nada.",
    },
    {
        "id": "negativo-2",
        "prompt": "Cual es la capital de Francia?",
        "esperado": None,
        "args_esperados": None,
        "nota": "Sin relacion. No deberia llamar a nada.",
    },
    {
        "id": "imposible-1",
        "prompt": "Desinstala Google Chrome de esta maquina.",
        "esperado": None,
        "args_esperados": None,
        "nota": "No existe herramienta para eso. Deberia decirlo, no forzar otra.",
    },
    {
        "id": "encadenado-1",
        "prompt": "Comprueba si Defender esta corriendo y dime tambien la hora.",
        "esperado": "get_service",
        "args_esperados": {"service_name": "WinDefend"},
        "nota": "Dos peticiones. Se anota cuantas llamadas emite en un solo turno.",
    },
]


def listar_modelos(base_url: str = BASE_URL, clave: str = "") -> List[str]:
    cabeceras = {"Authorization": f"Bearer {clave}"} if clave else {}
    respuesta = requests.get(f"{base_url}/models", headers=cabeceras, timeout=30)
    if respuesta.status_code >= 400:
        # Leer el cuerpo, no solo el codigo. Es la leccion de la seccion 4.3
        # aplicada a este mismo script.
        try:
            detalle = respuesta.json().get("error", {}).get("message", respuesta.text)
        except Exception:
            detalle = respuesta.text[:400]
        raise RuntimeError(f"HTTP {respuesta.status_code}: {detalle}")
    return [m["id"] for m in respuesta.json().get("data", [])]


SISTEMA = (
    "Eres un asistente de administracion de Windows. Usa las herramientas "
    "disponibles cuando hagan falta. Si ninguna sirve, responde con texto "
    "y no llames a ninguna."
)


def herramientas_anthropic() -> List[Dict[str, Any]]:
    """Traduce el catalogo al formato de la API de Anthropic.

    Mismo contenido, distinta envoltura: alli el esquema se llama input_schema
    y no hay nivel 'function'. Las descripciones son identicas a proposito,
    para que la comparacion mida el modelo y no dos redacciones distintas.
    """
    salida = []
    for h in HERRAMIENTAS:
        f = h["function"]
        salida.append({
            "name": f["name"],
            "description": f["description"],
            "input_schema": f["parameters"],
        })
    return salida


def preguntar_claude(prompt: str, modelo: str) -> Dict[str, Any]:
    """Mismo caso, contra la API de Anthropic. Requiere ANTHROPIC_API_KEY."""
    clave = os.getenv("ANTHROPIC_API_KEY", "").strip()
    if not clave:
        return {"error": "Falta la variable de entorno ANTHROPIC_API_KEY"}

    cuerpo = {
        "model": modelo,
        "max_tokens": 1024,
        "system": SISTEMA,
        "messages": [{"role": "user", "content": prompt}],
        "tools": herramientas_anthropic(),
    }

    inicio = time.time()
    try:
        respuesta = requests.post(
            CLAUDE_URL,
            json=cuerpo,
            headers={
                "x-api-key": clave,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            timeout=120,
        )
        if respuesta.status_code >= 400:
            try:
                detalle = respuesta.json().get("error", {}).get("message", respuesta.text)
            except Exception:
                detalle = respuesta.text[:400]
            return {"error": f"HTTP {respuesta.status_code}: {detalle}",
                    "segundos": round(time.time() - inicio, 1)}
        datos = respuesta.json()
    except Exception as exc:
        return {"error": f"{type(exc).__name__}: {exc}",
                "segundos": round(time.time() - inicio, 1)}

    llamadas = []
    textos = []
    for bloque in datos.get("content", []):
        if bloque.get("type") == "tool_use":
            llamadas.append({"nombre": bloque.get("name"),
                             "args": bloque.get("input") or {}})
        elif bloque.get("type") == "text":
            textos.append(bloque.get("text", ""))

    texto = "\n".join(textos).strip()
    return {
        "llamadas": llamadas,
        "en_texto": detectar_llamada_en_texto(texto) if not llamadas else None,
        "texto": texto[:400],
        "segundos": round(time.time() - inicio, 1),
    }


def preguntar(modelo: str, prompt: str, base_url: str = BASE_URL,
              clave: str = "") -> Dict[str, Any]:
    """Manda un caso a un endpoint compatible con OpenAI.

    Sirve igual para LM Studio en local y para cualquier proveedor en la nube
    que exponga esa misma API. Es lo que permite comparar EL MISMO modelo
    corriendo en dos sitios distintos.
    """
    cuerpo = {
        "model": modelo,
        "messages": [
            {"role": "system", "content": SISTEMA},
            {"role": "user", "content": prompt},
        ],
        "tools": HERRAMIENTAS,
        "temperature": 0,
    }

    inicio = time.time()
    cabeceras = {"Authorization": f"Bearer {clave}"} if clave else {}
    try:
        respuesta = requests.post(f"{base_url}/chat/completions", json=cuerpo,
                                  headers=cabeceras, timeout=TIMEOUT)
        if respuesta.status_code >= 400:
            # El cuerpo del error trae el motivo real. Sin esto, un modelo que
            # no cabe en la VRAM parece un modelo que elige mal.
            try:
                detalle = respuesta.json().get("error", {}).get("message", respuesta.text)
            except Exception:
                detalle = respuesta.text[:400]
            return {"error": f"HTTP {respuesta.status_code}: {detalle}",
                    "segundos": round(time.time() - inicio, 1)}
        datos = respuesta.json()
    except Exception as exc:
        return {"error": f"{type(exc).__name__}: {exc}",
                "segundos": round(time.time() - inicio, 1)}

    mensaje = datos["choices"][0]["message"]
    texto = (mensaje.get("content") or "").strip()

    llamadas = []
    for llamada in mensaje.get("tool_calls") or []:
        funcion = llamada.get("function", {})
        crudo = funcion.get("arguments") or "{}"
        try:
            argumentos = json.loads(crudo)
        except json.JSONDecodeError:
            argumentos = {"__json_invalido__": crudo}
        llamadas.append({"nombre": funcion.get("name"), "args": argumentos})

    return {
        "llamadas": llamadas,
        "en_texto": detectar_llamada_en_texto(texto) if not llamadas else None,
        "texto": texto[:400],
        "segundos": round(time.time() - inicio, 1),
    }


def evaluar(caso: Dict[str, Any], resultado: Dict[str, Any]) -> Dict[str, Any]:
    if "error" in resultado:
        return {"veredicto": "ERROR", "detalle": resultado["error"][:200]}

    llamadas = resultado["llamadas"]
    en_texto = resultado.get("en_texto")
    esperado = caso["esperado"]

    # Una simple MENCION del nombre de una herramienta en la prosa no es un
    # intento de llamada. Los modelos que narran su razonamiento escriben cosas
    # como "no tengo una herramienta para eso, solo get_date y get_service", y
    # tomar eso por una llamada convierte una respuesta correcta en un fallo.
    # Solo cuenta como intento un objeto JSON bien formado con nombre de
    # herramienta.
    mencion_suelta = bool(en_texto and en_texto.get("solo_mencion"))
    intento = None if mencion_suelta else en_texto

    if esperado is None:
        if not llamadas and not intento:
            detalle = "no llamo a ninguna, correcto"
            if mencion_suelta:
                detalle += f" (menciono {en_texto['nombre']} en su razonamiento)"
            return {"veredicto": "OK", "detalle": detalle}
        if intento:
            return {"veredicto": "FALLO",
                    "detalle": f"propuso {intento['nombre']} en texto sin motivo"}
        nombres = ", ".join(c["nombre"] or "?" for c in llamadas)
        return {"veredicto": "FALLO", "detalle": f"llamo a {nombres} sin motivo"}

    if not llamadas:
        # Distinguimos "no supo" de "supo pero lo escribio como texto".
        if intento and intento["nombre"] == esperado:
            return {"veredicto": "FORMATO",
                    "detalle": f"acerto {esperado} pero lo emitio como texto"}
        if intento:
            return {"veredicto": "FALLO",
                    "detalle": f"propuso {intento['nombre']} en texto, se esperaba {esperado}"}
        return {"veredicto": "FALLO", "detalle": "no llamo a ninguna herramienta"}

    primera = llamadas[0]
    if primera["nombre"] != esperado:
        return {"veredicto": "FALLO", "detalle": f"llamo a {primera['nombre']}, se esperaba {esperado}"}

    esperados = caso.get("args_esperados")
    if esperados:
        for clave, valor in esperados.items():
            recibido = primera["args"].get(clave)
            if isinstance(valor, str) and isinstance(recibido, str):
                if recibido.strip().lower() != valor.strip().lower():
                    return {"veredicto": "PARCIAL", "detalle": f"{clave}={recibido!r}, se esperaba {valor!r}"}
            elif recibido != valor:
                return {"veredicto": "PARCIAL", "detalle": f"{clave}={recibido!r}, se esperaba {valor!r}"}

    extra = f" (+{len(llamadas) - 1} llamada/s mas)" if len(llamadas) > 1 else ""
    return {"veredicto": "OK", "detalle": f"{primera['nombre']} {primera['args']}{extra}"}


def calentar(modelo: str) -> Optional[str]:
    """Primera llamada tonta, para que cargar el modelo en VRAM no cuente
    como un caso fallado por timeout."""
    print(f"Calentando {modelo} (puede tardar si hay que cargarlo en VRAM)...")
    inicio = time.time()
    try:
        respuesta = requests.post(
            f"{BASE_URL}/chat/completions",
            json={"model": modelo, "messages": [{"role": "user", "content": "hola"}],
                  "max_tokens": 5, "temperature": 0},
            timeout=TIMEOUT,
        )
        if respuesta.status_code >= 400:
            try:
                motivo = respuesta.json().get("error", {}).get("message", respuesta.text)
            except Exception:
                motivo = respuesta.text[:300]
            return f"HTTP {respuesta.status_code}: {motivo}"
    except Exception as exc:
        return f"{type(exc).__name__}: {exc}"
    print(f"Listo en {time.time() - inicio:.1f}s\n")
    return None


def main() -> int:
    parser = argparse.ArgumentParser(description="Banco de pruebas de seleccion de herramientas")
    parser.add_argument("--modelo", help="Identificador del modelo")
    parser.add_argument("--claude", action="store_true",
                        help="Ejecuta contra la API de Anthropic. Requiere ANTHROPIC_API_KEY")
    parser.add_argument("--api-base",
                        help="URL base de un endpoint compatible con OpenAI. "
                             "Sirve para probar EL MISMO modelo en la nube. "
                             "Ej: https://generativelanguage.googleapis.com/v1beta/openai")
    parser.add_argument("--api-key-env", default="CLOUD_API_KEY",
                        help="Nombre de la variable de entorno con la clave (por defecto CLOUD_API_KEY)")
    parser.add_argument("--etiqueta", help="Nombre del entorno para el archivo de resultados")
    parser.add_argument("--listar", action="store_true", help="Lista los modelos y sale")
    args = parser.parse_args()

    # --- Ruta 1: API de Anthropic ---
    if args.claude:
        modelo = args.modelo or CLAUDE_MODELO
        print(f"Modelo: {modelo} (API de Anthropic)")
        print(f"Casos : {len(CASOS)}\n")
        if not os.getenv("ANTHROPIC_API_KEY", "").strip():
            print("[ABORTADO] Falta ANTHROPIC_API_KEY.", file=sys.stderr)
            print('  $env:ANTHROPIC_API_KEY = "sk-ant-..."', file=sys.stderr)
            return 2
        return ejecutar(modelo, lambda p: preguntar_claude(p, modelo),
                        args.etiqueta or "claude")

    # --- Ruta 2: cualquier endpoint compatible con OpenAI ---
    base = args.api_base.rstrip("/") if args.api_base else BASE_URL
    en_la_nube = bool(args.api_base)
    clave = os.getenv(args.api_key_env, "").strip() if en_la_nube else ""

    if en_la_nube and not clave:
        print(f"[ABORTADO] Falta la variable {args.api_key_env}.", file=sys.stderr)
        print(f'  $env:{args.api_key_env} = "..."', file=sys.stderr)
        return 2

    # Solo se consulta /models si de verdad hace falta: para listar, o para
    # elegir uno por defecto cuando el usuario no dio --modelo. Varios
    # proveedores compatibles con OpenAI no exponen ese endpoint, y no tiene
    # sentido abortar por algo que no necesitamos.
    modelo = args.modelo

    if args.listar or not modelo:
        try:
            modelos = listar_modelos(base, clave)
        except Exception as exc:
            print(f"No se pudo listar modelos en {base}: {exc}", file=sys.stderr)
            if en_la_nube:
                print("\nEste proveedor puede no exponer /models en la ruta compatible.",
                      file=sys.stderr)
                print("Pasa el modelo a mano con --modelo y no hara falta listar.",
                      file=sys.stderr)
            else:
                print("Comprueba que LM Studio esta abierto y el servidor local activo.",
                      file=sys.stderr)
            return 1

        if args.listar:
            for m in modelos:
                print(m)
            return 0

        modelo = modelos[0] if modelos else None
        if not modelo:
            print("No hay modelos disponibles.", file=sys.stderr)
            return 1

    print(f"Modelo: {modelo} ({'nube' if en_la_nube else 'local'} - {base})")
    print(f"Casos : {len(CASOS)}\n")

    # Calentar solo tiene sentido en local: en la nube no hay que cargar nada
    # en VRAM, y una llamada extra es dinero tirado.
    if not en_la_nube:
        fallo = calentar(modelo)
        if fallo:
            print(f"[ABORTADO] El modelo no responde: {fallo}")
            print("\nEsto NO es un resultado del modelo: no llego a ejecutarse.")
            print("Causas tipicas: no cabe en la VRAM, o el runtime no lo soporta.")
            return 2

    etiqueta = args.etiqueta or ("nube" if en_la_nube else "local")
    return ejecutar(modelo, lambda p: preguntar(modelo, p, base, clave), etiqueta)


def ejecutar(modelo: str, consultar, etiqueta: str) -> int:
    resultados = []
    conteo = {"OK": 0, "FORMATO": 0, "PARCIAL": 0, "FALLO": 0, "ERROR": 0}

    for caso in CASOS:
        salida = consultar(caso["prompt"])
        veredicto = evaluar(caso, salida)
        conteo[veredicto["veredicto"]] += 1
        resultados.append({**caso, "resultado": salida, "evaluacion": veredicto})
        segundos = salida.get("segundos", 0)
        print(f"[{veredicto['veredicto']:<7}] {caso['id']:<13} {segundos:>6.1f}s  {veredicto['detalle']}")

    total = len(CASOS)
    print(f"\nOK {conteo['OK']}/{total} | FORMATO {conteo['FORMATO']} | "
          f"PARCIAL {conteo['PARCIAL']} | FALLO {conteo['FALLO']} | ERROR {conteo['ERROR']}")
    if conteo["FORMATO"]:
        print("\nFORMATO = el modelo acerto la herramienta pero la escribio como texto")
        print("en vez de emitirla por el protocolo. En un cliente MCP real esa")
        print("llamada no ocurre: el servidor no se entera de nada.")

    seguro = modelo.replace("/", "_").replace(":", "_")
    destino = f"resultados_{etiqueta}_{seguro}.json"
    with open(destino, "w", encoding="utf-8") as fichero:
        json.dump({"modelo": modelo, "entorno": etiqueta, "conteo": conteo, "casos": resultados},
                  fichero, ensure_ascii=False, indent=2)
    print(f"Detalle completo en {destino}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
