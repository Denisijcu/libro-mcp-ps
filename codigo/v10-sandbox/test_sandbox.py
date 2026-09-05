# -*- coding: utf-8 -*-
"""
Capitulo 10: pruebas del sandbox.

Se ejecuta solo y se autoevalua. No escribe ni borra nada real: solo comprueba
que la funcion de validacion decide bien.

    python test_sandbox.py

Sale con codigo 0 si todo pasa, 1 si algo falla.
"""

import os
import sys

# Fijamos el sandbox antes de importar, para que la prueba sea reproducible
# independientemente de donde este el perfil del usuario.
os.environ["PSMCP_FS_WRITE_ROOTS"] = r"C:\sandbox-libro;C:\Users\denis\Desktop"

import sandbox  # noqa: E402

# (descripcion, ruta, se_espera_bloqueo)
CASOS = [
    # --- deben pasar ---
    ("Archivo dentro de la raiz permitida",
     r"C:\sandbox-libro\notas.txt", False),
    ("Subcarpeta profunda dentro de la raiz",
     r"C:\sandbox-libro\pruebas\2026\salida.log", False),
    ("Segunda raiz permitida",
     r"C:\Users\denis\Desktop\reporte.txt", False),

    # --- deben bloquearse: fuera del sandbox ---
    ("Fuera de toda raiz permitida",
     r"D:\otra-cosa\archivo.txt", True),
    ("Perfil de otro usuario",
     r"C:\Users\otro\Desktop\archivo.txt", True),

    # --- deben bloquearse: rutas del sistema ---
    ("Carpeta de Windows",
     r"C:\Windows\System32\drivers\etc\hosts", True),
    ("Archivos de programa",
     r"C:\Program Files\algo\bin.exe", True),
    ("Mayusculas distintas, misma ruta prohibida",
     r"c:\WINDOWS\system32\kernel32.dll", True),

    # --- deben bloquearse: intentos de escape ---
    ("Escape con .. hacia Windows",
     r"C:\sandbox-libro\..\Windows\System32\algo.dll", True),
    ("Escape con .. hacia otro disco raiz",
     r"C:\sandbox-libro\..\..\archivo.txt", True),

    # --- deben bloquearse: reglas generales ---
    ("Raiz del disco",
     r"C:\", True),
    ("Carpeta de primer nivel",
     r"C:\algo", True),
    ("Comodin en la ruta",
     r"C:\sandbox-libro\*.txt", True),
    ("Ruta vacia",
     "", True),
]


def main() -> int:
    fallos = 0
    print(f"Raices permitidas: {sandbox.RAICES_ESCRITURA}\n")

    for descripcion, ruta, se_espera_bloqueo in CASOS:
        resultado = sandbox.comprobar_ruta_escritura(ruta)
        bloqueada = resultado is not None
        correcto = bloqueada == se_espera_bloqueo

        etiqueta = "PASA " if correcto else "FALLA"
        esperado = "bloquear" if se_espera_bloqueo else "permitir"
        obtenido = "bloqueo" if bloqueada else "permiso"

        print(f"[{etiqueta}] {descripcion}")
        print(f"         ruta     : {ruta!r}")
        print(f"         esperado : {esperado}  ->  obtenido: {obtenido}")
        if bloqueada:
            print(f"         motivo   : {resultado}")
        if not correcto:
            fallos += 1
        print()

    print("--- redaccion de la auditoria ---")
    ejemplo = {"username": "denis", "password": "secreto123", "ruta": "C:\\temp"}
    print(f"antes  : {ejemplo}")
    print(f"despues: {sandbox.redactar(ejemplo)}")
    if sandbox.redactar(ejemplo)["password"] == "secreto123":
        print("FALLA: la contrasena no se redacto")
        fallos += 1
    print()

    print("--- truncado de salida ---")
    largo = "x" * (sandbox.MAX_CARACTERES + 5000)
    cortado = sandbox.truncar(largo)
    print(f"entrada : {len(largo)} caracteres")
    print(f"salida  : {len(cortado)} caracteres")
    print(f"aviso   : {'SI' if 'SALIDA CORTADA' in cortado else 'NO'}")
    if "SALIDA CORTADA" not in cortado:
        print("FALLA: se corto sin avisar")
        fallos += 1
    print()

    print("--- limitar argumentos del modelo ---")
    for valor in (-5, 0, 3, 500):
        print(f"limitar({valor}, 1, 20) = {sandbox.limitar(valor, 1, 20)}")

    print(f"\n{'TODO CORRECTO' if fallos == 0 else str(fallos) + ' FALLO(S)'}")
    return 0 if fallos == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
