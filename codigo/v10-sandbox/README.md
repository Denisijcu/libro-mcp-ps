# Capítulo 10 — Código

| Archivo | Qué es |
|---|---|
| `sandbox.py` | Sandbox de rutas, auditoría con redacción y límites de salida. |
| `test_sandbox.py` | Catorce casos de ruta más las pruebas de redacción y truncado. |

## Probar

```powershell
python test_sandbox.py
```

**Se autoevalúa.** Imprime `PASA` o `FALLA` por caso y sale con código 0 si todo está
bien. No escribe ni borra nada real: solo comprueba que la función de validación decide
lo correcto.

Los casos que más importan son los cuatro de escape:

| Caso | Por qué importa |
|---|---|
| `C:\sandbox-libro\..\Windows\System32\algo.dll` | El `..` saca la ruta del sandbox. Si `normalizar()` no resolviera, pasaría el filtro. |
| `c:\WINDOWS\system32\kernel32.dll` | Mayúsculas distintas, misma ruta. Sin `normcase` no coincide con la lista negra. |
| `C:\` | Raíz del disco. |
| `C:\sandbox-libro\*.txt` | Comodín: una operación, muchos objetivos. |

## Nota sobre `realpath`

`normalizar()` usa `os.path.realpath`, no `abspath`. La diferencia importa: `abspath`
resuelve `..` pero **no** los enlaces simbólicos ni las uniones de directorio. Un enlace
dentro del sandbox que apunte a `C:\Windows` pasaría el filtro con `abspath` y se
bloquea con `realpath`.

## Estado de verificación

`[VERIFICAR: Denis]` — pendiente de ejecutar y pegar la salida en
`pruebas/cap10-sandbox.txt`.

Los casos están escritos con rutas fijas (`C:\sandbox-libro`, `C:\Users\denis\Desktop`) y
el script fija las raíces por variable de entorno antes de importar, así que el resultado
no depende de dónde se ejecute.
