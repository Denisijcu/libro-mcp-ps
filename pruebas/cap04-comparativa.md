# Resultados de la comparativa del capítulo 4

## Entorno

| Dato | Valor |
|---|---|
| Máquina | HP-OMEN, Windows 11 Home 25H2 build 26200.8973 |
| GPU | GTX 1660 Ti, 6 GB VRAM |
| LM Studio | `127.0.0.1:1234` |
| Modelo local de referencia | `google/gemma-4-12b-qat` |
| Fecha | 2026-09-04 |

---

# GEMMA 12B — banco corregido

```
Calentando google/gemma-4-12b-qat... Listo en 5.1s

[OK     ] directo-1       11.5s  get_date {}
[OK     ] directo-2       18.0s  get_service {'service_name': 'WinDefend'}
[OK     ] directo-3       25.6s  get_disk_space {}
[OK     ] indirecto-1     26.2s  get_top_processes {'count': 10}
[OK     ] indirecto-2     17.7s  get_disk_space {}
[OK     ] args-1          14.7s  get_top_processes {'count': 3}
[OK     ] args-2          28.4s  get_service {'service_name': 'Spooler'}
[OK     ] limite-1        40.4s  get_top_processes {'count': 20}
[OK     ] negativo-1     269.0s  no llamo a ninguna, correcto
[OK     ] negativo-2      12.2s  no llamo a ninguna, correcto
[OK     ] imposible-1     67.8s  no llamo a ninguna, correcto
[OK     ] encadenado-1    36.7s  get_service {'service_name': 'WinDefend'} (+1 mas)

OK 12/12 | FORMATO 0 | PARCIAL 0 | FALLO 0 | ERROR 0
```

## Lectura de acierto

12 de 12. Incluidos los tres casos negativos y el imposible, que son los que separan un
modelo que elige de uno que dispara.

Con el banco corregido desaparece el único fallo de la ronda 1 (`limite-1`), que entonces
se comió el timeout de carga en frío. La llamada de calentamiento lo resolvió: 5,1 segundos
de carga que antes caían sobre el primer caso.

## Lectura de latencia — lo importante

Los tiempos separan los casos en dos grupos limpios:

| Grupo | Casos | Rango |
|---|---|---|
| El modelo emite una llamada a herramienta | 8 casos | 11,5 – 40,4 s |
| El modelo responde con texto | `imposible-1`, `negativo-1` | 67,8 s y **269,0 s** |

La diferencia no es casualidad y tiene una explicación mecánica: **una llamada a herramienta
son pocos tokens; una respuesta en prosa son muchos.** El caso `negativo-1` pide explicar
qué es un servicio de Windows y para qué sirve. El modelo genera párrafos, y a la velocidad
de generación de un 12B cuantizado en una GTX 1660 Ti, eso son cuatro minutos y medio.

Total de la tanda: unos 578 segundos, casi diez minutos para doce peticiones.

### Consecuencia para el diseño

El coste de trabajar en local **no es la precisión: es la latencia**, y está concentrada en
las respuestas que generan texto, no en la selección de herramientas.

Un servidor MCP bien diseñado se beneficia de esa asimetría: el trabajo caro (recorrer
procesos, leer el registro, correlacionar) lo hace PowerShell en milisegundos, y el modelo
solo tiene que emitir una llamada corta e interpretar el resultado. Cuanto más trabajo
metas en la herramienta y menos en la prosa del modelo, mejor se comporta la combinación.

Es un argumento a favor de decisiones que ya estaban tomadas por otras razones:

- Calcular porcentajes y uptime en PowerShell (capítulo 12) en vez de dejar que el modelo
  razone con números.
- Puntuar el triage en Python (capítulo 14) en vez de pedirle al modelo un veredicto
  narrado.
- Devolver JSON compacto y no tablas dibujadas.

Cada una de esas decisiones ahorra tokens generados, y en local los tokens generados son
segundos de reloj.

## Notas

- La ejecución se hizo con la versión del banco anterior al añadido de la ruta de Claude,
  por eso el archivo de resultados se llama `resultados_google_gemma-4-12b-qat.json`. A
  partir de ahora el nombre lleva el entorno delante: `resultados_local_...` y
  `resultados_claude_...`.

---

# CLAUDE SONNET 5 — API de Anthropic

```
[OK     ] directo-1        1.9s  get_date {}
[OK     ] directo-2        2.0s  get_service {'service_name': 'WinDefend'}
[OK     ] directo-3        1.6s  get_disk_space {}
[OK     ] indirecto-1      2.2s  get_top_processes {'count': 10} (+1 mas)
[OK     ] indirecto-2      1.8s  get_disk_space {}
[OK     ] args-1           1.7s  get_top_processes {'count': 3}
[OK     ] args-2           1.9s  get_service {'service_name': 'Spooler'}
[OK     ] limite-1         2.5s  get_top_processes {'count': 20}
[OK     ] negativo-1       9.1s  no llamo a ninguna, correcto
[OK     ] negativo-2       1.8s  no llamo a ninguna, correcto
[OK     ] imposible-1      5.5s  no llamo a ninguna, correcto
[OK     ] encadenado-1     2.1s  get_service {'service_name': 'WinDefend'} (+1 mas)

OK 12/12 | FORMATO 0 | PARCIAL 0 | FALLO 0 | ERROR 0
```

## Comparativa

| Caso | Gemma 12B local | Claude Sonnet 5 | Factor |
|---|---|---|---|
| directo-1 | 11.5s | 1.9s | 6x |
| directo-2 | 18.0s | 2.0s | 9x |
| directo-3 | 25.6s | 1.6s | 16x |
| indirecto-1 | 26.2s | 2.2s | 12x |
| indirecto-2 | 17.7s | 1.8s | 10x |
| args-1 | 14.7s | 1.7s | 9x |
| args-2 | 28.4s | 1.9s | 15x |
| limite-1 | 40.4s | 2.5s | 16x |
| negativo-1 | **269.0s** | **9.1s** | **30x** |
| negativo-2 | 12.2s | 1.8s | 7x |
| imposible-1 | 67.8s | 5.5s | 12x |
| encadenado-1 | 36.7s | 2.1s | 17x |
| **Total** | **12/12, ~578s** | **12/12, ~34s** | **17x** |

## Lecturas

**1. El acierto empata: 12/12 y 12/12.**

Con un catalogo de cuatro herramientas bien descritas, el modelo local no se equivoca en
nada de lo que se le pide. Ni en los casos indirectos, ni extrayendo argumentos, ni
sabiendo cuando NO llamar. Para este tamano de problema, la eleccion de herramienta esta
resuelta en local.

**2. La diferencia esta entera en el reloj: 17x de media.**

Y no es uniforme. El factor sube justo donde el modelo tiene que generar texto:

    Llamadas a herramienta : 6x - 17x
    Respuestas en texto    : 12x (imposible-1) y 30x (negativo-1)

Eso confirma la explicacion mecanica: lo caro en local no es decidir, es escribir.

**3. Los dos coinciden hasta en las rarezas.**

Los dos inventaron `count: 10` en indirecto-1 sin que nadie lo pidiera. Los dos leyeron el
`Maximum 20` de la descripcion en limite-1. Los dos emitieron dos llamadas en
encadenado-1.

Que un 12B cuantizado en local y un modelo de frontera tomen las MISMAS decisiones sobre
el mismo catalogo dice mas del catalogo que de los modelos: si las descripciones estan
bien escritas, la eleccion es casi determinista.

**4. Claude tambien tardo mas en los dos casos de texto.**

9.1s y 5.5s frente a 1.6-2.5s del resto. El patron es identico al de Gemma, solo que a
otra escala. No es un problema del hardware local: es que generar prosa cuesta mas que
emitir una llamada, en todas partes.

---

# GEMMA 4 26B-A4B — API de Gemini (endpoint compatible con OpenAI)

`https://generativelanguage.googleapis.com/v1beta/openai`

```
[OK     ] directo-1        1.7s  get_date {}
[OK     ] directo-2        2.4s  get_service {'service_name': 'WinDefend'}
[OK     ] directo-3        1.8s  get_disk_space {}
[OK     ] indirecto-1      4.0s  get_top_processes {'count': 10}
[ERROR  ] indirecto-2     13.9s  HTTP 503: This model is currently experiencing high demand
[OK     ] args-1           2.2s  get_top_processes {'count': 3}
[OK     ] args-2           3.5s  get_service {'service_name': 'Spooler'}
[OK     ] limite-1         4.6s  get_top_processes {'count': 20}
[OK     ] negativo-1      26.9s  no llamo a ninguna, correcto
[OK     ] negativo-2       2.0s  no llamo a ninguna, correcto
[FALLO  ] imposible-1     10.4s  propuso get_date en texto sin motivo
[OK     ] encadenado-1    24.0s  get_service {'service_name': 'WinDefend'} (+1 mas)

OK 10/12 | FORMATO 0 | PARCIAL 0 | FALLO 1 | ERROR 1
```

**Aviso: el modelo NO es el mismo que el local.** El local es un Gemma 12B cuantizado; este
es un 26B con 4B activos. La comparación no aísla el hardware del todo.

## El FALLO de imposible-1 era del banco, no del modelo

El JSON completo lo deja claro. El modelo respondió:

```
<thought>The user wants to uninstall Google Chrome from the machine.
I don't have a direct "uninstall" tool, but I can look for installed programs...
Wait, I don't have a tool to list installed programs or uninstall them
```

No llamó a nada y razonó exactamente bien: reconoció que no tiene herramienta para eso,
que es la respuesta correcta al caso.

Lo que falló fue el detector. `detectar_llamada_en_texto` tiene una rama de último recurso
que marca un intento de llamada si el texto **menciona** el nombre de una herramienta. Este
modelo escribe su cadena de razonamiento en el `content`, y ahí nombró `get_date` de paso.

Esa rama se escribió pensando en el 7B, que emitía bloques JSON dentro del texto. Contra un
modelo que narra en prosa, produce falsos positivos.

**Arreglo**: una mención suelta ya no genera veredicto. Solo cuenta como intento de llamada
un objeto JSON bien formado con nombre de herramienta. La mención se sigue anotando en el
detalle, como información.

Con el arreglo, el caso pasa a `OK` y la puntuación real es **11/12**, con el único
incidente siendo el 503.

Es el tercer falso positivo de instrumento en este capítulo: el 27B, el mensaje de error
del diagnóstico y este. Todos en la misma dirección — **el banco culpaba al modelo de
fallos que eran suyos.**

## El 503 es el hallazgo del capitulo 7

```
HTTP 503: This model is currently experiencing high demand. Spikes in demand
are usually temporary. Please try again later.
```

Ese error **no existe en local**. Ninguna cantidad de demanda ajena hace que tu GPU te diga
que vuelvas luego.

Es un modo de fallo propio de la nube, y no es el que la gente espera. Al comparar local
contra nube se suele hablar de privacidad, coste y latencia. La disponibilidad casi nunca
sale, y sin embargo aquí se manifestó a la primera, en una tanda de doce llamadas.

Para un servidor de administración de sistemas eso pesa: la herramienta que investiga un
incidente tiene que funcionar **durante** el incidente.

## Comparativa de las tres columnas

| Caso | Gemma 12B local | Gemma 26B nube | Claude Sonnet 5 |
|---|---|---|---|
| directo-1 | OK 11.5s | OK 1.7s | OK 1.9s |
| directo-2 | OK 18.0s | OK 2.4s | OK 2.0s |
| directo-3 | OK 25.6s | OK 1.8s | OK 1.6s |
| indirecto-1 | OK 26.2s | OK 4.0s | OK 2.2s |
| indirecto-2 | OK 17.7s | **ERROR 503** | OK 1.8s |
| args-1 | OK 14.7s | OK 2.2s | OK 1.7s |
| args-2 | OK 28.4s | OK 3.5s | OK 1.9s |
| limite-1 | OK 40.4s | OK 4.6s | OK 2.5s |
| negativo-1 | OK 269.0s | OK 26.9s | OK 9.1s |
| negativo-2 | OK 12.2s | OK 2.0s | OK 1.8s |
| imposible-1 | OK 67.8s | OK 10.4s | OK 5.5s |
| encadenado-1 | OK 36.7s | OK 24.0s | OK 2.1s |
| **Resultado** | **12/12** | **11/12 + 1 corte** | **12/12** |
| **Tiempo total** | **~578s** | **~87s** | **~34s** |

### Lo que separa cada comparacion

**Gemma local vs Gemma nube (misma familia, distinto hardware y tamaño): 6,6x.**
La mayor parte de la diferencia de velocidad no es del modelo: es de la máquina. Quitar la
GTX 1660 Ti de la ecuación vale casi siete veces.

**Gemma nube vs Claude (infraestructura equivalente): 2,6x.**
Con los dos servidos por API, la diferencia se reduce mucho. Sigue existiendo, pero ya no
es de otro orden.

**Conclusión**: de los 17x entre el portátil y Claude, aproximadamente **7x son hardware y
2,6x son modelo**. La mayor parte del dolor viene de la tarjeta, no de la eleccion de
modelo.

### Y el acierto sigue empatado

Los tres eligen igual. Los tres inventaron `count: 10` en `indirecto-1`, los tres leyeron
el `Maximum 20` de la descripción, los tres emitieron dos llamadas en `encadenado-1`.

Un 12B cuantizado en un portátil de 2019 toma **las mismas decisiones** que un modelo de
frontera sobre este catálogo. Con cuatro herramientas bien descritas, la eleccion es casi
determinista, y pagar por la nube no compra mejores decisiones: compra segundos.

| Columna | Estado |
|---|---|
| Gemma 12B local | Medida |
| Gemma 26B nube | Medida |
| Claude Sonnet 5 | Medida |
