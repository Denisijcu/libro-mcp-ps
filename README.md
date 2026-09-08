# Código del libro *PowerShell con agentes*

Este repositorio contiene **el código** del libro *PowerShell con agentes: construye tu
propio MCP para administrar y defender Windows 11*, de Denis Sánchez Leyva.

No contiene el texto del libro, que está a la venta en Amazon. Aquí está todo lo que se
construye en sus páginas, listo para clonar y ejecutar.

**Video de presentación:** https://youtu.be/lXGKJB8ry2o

## Qué es esto

Un servidor MCP (Model Context Protocol) que le da a un modelo de lenguaje acceso
controlado a PowerShell, para administrar y auditar la seguridad de una máquina Windows.

Se construye por capas a lo largo del libro: empieza con una herramienta que devuelve la
fecha y termina con inventario, búsqueda de amenazas, triage automático y orquestación con
otros servidores MCP.

## Requisitos

| Requisito | Versión |
|---|---|
| Windows | 10 u 11 |
| PowerShell | 5.1 (viene instalado) |
| Python | 3.10 o superior |
| SDK `mcp` | `>=1.10,<2` |

```powershell
pip install "mcp[cli]>=1.10,<2"
```

**La restricción `<2` es obligatoria.** La versión 2.0 del SDK renombró `FastMCP` a
`MCPServer` y eliminó `mcp.server.fastmcp`. El código de este repositorio usa la API 1.x.

Para el banco de pruebas del capítulo 4 hacen falta además LM Studio con un modelo local y
una clave de API de Anthropic en `ANTHROPIC_API_KEY`. El servidor MCP **no** necesita
ninguna de las dos cosas: funciona sin conexión a internet.

## Aviso importante

> **El código de `codigo/v03-primer-servidor/` es vulnerable a propósito.**
>
> Contiene una inyección de comandos que se disecciona y se arregla en el capítulo 8. Está
> ahí porque es como se escribe naturalmente y como aparece en la mayoría de los ejemplos
> publicados por ahí.
>
> No lo uses como base para nada. Si quieres un punto de partida, usa
> `codigo/v12-inventario/ejecutor.py`, que ya lleva el arreglo.

Todo lo demás está pensado para ejecutarse sobre tu propia máquina. Las herramientas de
escritura y las destructivas vienen **cerradas por defecto** y hay que abrirlas
explícitamente con variables de entorno.

## Estructura

| Carpeta | Capítulo | Qué contiene |
|---|---|---|
| `v03-primer-servidor/` | 3 | El servidor mínimo y su versión corregida |
| `v04-comparativa/` | 4 | Banco de pruebas de selección de herramientas |
| `v06-catalogo/` | 6 | Medición del coste de un catálogo grande |
| `v08-inyeccion/` | 8 | Demostración de inyección de comandos y su arreglo |
| `v09-gates/` | 9 | Niveles de daño, listas de protección y tokens |
| `v10-sandbox/` | 10 | Sandbox de rutas, auditoría y límites |
| `v11-inyeccion-indirecta/` | 11 | Cebo de inyección indirecta y mitigaciones |
| `v12-inventario/` | 12 | Ejecutor común y servidor de inventario |
| `v13-hunting/` | 13 | Servidor de búsqueda de amenazas |
| `v14-triage/` | 14 | Motor de puntuación y semáforo |
| `v15-orquestacion/` | 15 | Correlación entre varios servidores MCP |
| `v16-empaquetado/` | 16 | Diagnóstico de salud del servidor |

En `pruebas/` están las salidas reales de las mediciones citadas en el libro, con la fecha
y la máquina donde se obtuvieron.

## Empezar

Si vienes del libro, ve a la carpeta del capítulo que estés leyendo.

Si has llegado aquí sin el libro y quieres ver si esto te sirve, empieza por dos cosas:

```powershell
cd codigo/v16-empaquetado
python diagnostico.py
```

Comprueba tu entorno y te dice qué falta, sin tocar nada.

```powershell
cd codigo/v08-inyeccion
python demo_inyeccion.py
```

Demuestra en veinte segundos por qué la mayoría de los servidores MCP de PowerShell que
hay publicados tienen un problema serio. La carga útil es inofensiva y se limpia sola.

## Configuración en el cliente

```json
{
  "mcpServers": {
    "powershell": {
      "command": "C:\\ruta\\a\\venv\\Scripts\\python.exe",
      "args": ["C:\\ruta\\al\\repo\\codigo\\v12-inventario\\servidor_inventario.py"],
      "env": {
        "PSMCP_ALLOW_WRITE": "0",
        "PSMCP_ALLOW_DESTRUCTIVE": "0"
      }
    }
  }
}
```

## A la pregunta: "Cuáles son las preguntas que te puedo hacer de la herramienta PowerShell Inventario que tienes instalada?"

Respuesta del modelo: (Gemma)

Como asistente, tengo acceso a una serie de herramientas específicas diseñadas para interactuar con el sistema operativo Windows y obtener información detallada. Aunque no tengo una herramienta llamada exactamente "powershell-inventario", el conjunto de herramientas que tengo a mi disposición cumple precisamente esa función de **inventario y diagnóstico del sistema**.

Aquí tienes todas las categorías de preguntas que puedes hacerme basadas en las capacidades de estas herramientas:

### 1. Información General del Sistema
Puedes preguntarme sobre la identidad y el estado actual de la máquina:
*   "¿Qué sistema operativo y versión tiene esta computadora?"
*   "¿Cuál es el nombre del equipo y la arquitectura (64 o 32 bits)?"
*   "¿Cuánto tiempo lleva encendida la computadora?"
*   "¿A qué dominio pertenece esta máquina?"

### 2. Recursos de Hardware (Memoria y Disco)
Puedes preguntarme sobre el rendimiento y el espacio disponible:
*   "¿Cuánta memoria RAM total tiene y cuánta está libre?"
*   "¿Qué porcentaje de la RAM está en uso?"
*   "¿Cuánto espacio libre hay en cada unidad de disco (C:, D:, etc.)?"
*   "¿Se está quedando sin espacio en el disco duro?"

### 3. Rendimiento y Procesos
Si sientes que la computadora está lenta, puedes preguntarme:
*   "¿Qué programas están consumiendo más memoria en este momento?"
*   "¿Qué procesos están usando más CPU?"
*   "¿Cuál es el PID y el usuario del proceso que está ralentizando el equipo?"

### 4. Software e Instalaciones
Puedes preguntarme sobre lo que tienes instalado:
*   "¿Qué programas tengo instalados en esta máquina?"
*   "¿Tengo instalada la versión más reciente de [nombre del programa]?"
*   "¿Quién es el editor de [nombre del programa] y cuándo se instaló?"
*   "Dame una lista de los últimos programas instalados."

### 5. Red y Conectividad
Para diagnosticar problemas de internet o red local:
*   "¿Cuál es mi dirección IP actual?"
*   "¿Cuál es la puerta de enlace (gateway) y los servidores DNS?"
*   "¿Qué adaptadores de red están activos?"

### 6. Servicios y Actualizaciones
Para mantenimiento técnico:
*   "¿Qué servicios de Windows están corriendo en este momento?"
*   "¿Está corriendo el servicio de [nombre del servicio]?"
*   "¿Cuáles fueron las últimas actualizaciones de Windows instaladas?"
*   "¿Hay algún reinicio pendiente por una actualización?"

---

**¿Cómo pedirme las cosas?**
Puedes ser directo. Por ejemplo:
*   *"Hazme un inventario rápido de hardware y memoria."*
*   *"Dime qué programas tengo instalados que tengan que ver con 'Adobe'."*
*   *"¿Por qué la PC está lenta? Muéstrame los procesos que más consumen."*
*   *"Dame los detalles de mi conexión de red."*


---

---
Como asistente con acceso a herramientas especializadas en ciberseguridad y análisis de sistemas, puedo ayudarte a realizar una investigación técnica profunda en una máquina Windows. 

Aquí tienes las categorías de preguntas y tareas que puedes pedirme, divididas por el tipo de análisis que necesites realizar:

### 1. Información del Sistema y Recursos
Puedes preguntarme sobre el estado general de la máquina:
*   **Identidad del equipo:** "¿Qué sistema operativo tiene esta máquina, qué arquitectura es y cuánto tiempo lleva encendida?"
*   **Rendimiento:** "¿Qué procesos están consumiendo más CPU o memoria en este momento?"
*   **Almacenamiento:** "¿Cuánto espacio libre queda en los discos duros?"
*   **Software:** "¿Qué programas están instalados en el equipo?" o "¿Qué versión de [software específico] tengo?"

### 2. Seguridad y Persistencia (Detección de Malware/Intrusos)
Estas preguntas son clave para saber si la máquina está comprometida:
*   **Ejecución automática:** "¿Qué programas se inician automáticamente al encender la PC?"
*   **Tareas programadas:** "¿Hay tareas programadas sospechosas que ejecuten scripts o comandos extraños?"
*   **Exclusiones de Antivirus:** "¿Hay alguna exclusión en Microsoft Defender que yo no haya configurado?" (Esto es común para ocultar malware).
*   **Procesos sospechosos:** "¿Hay algún proceso ejecutándose desde una carpeta de usuario o que no tenga firma digital válida?"
*   **Limpieza de logs:** "¿Se han borrado los registros de eventos del sistema recientemente?" (Un indicador crítico de actividad de un atacante).

### 3. Análisis de Red (Conectividad)
Para detectar comunicaciones con servidores externos o puertos abiertos:
*   **Conexiones activas:** "¿A qué direcciones IP se está conectando mi computadora en este momento?"
*   **Puertos abiertos:** "¿Qué puertos tengo abiertos y escuchando en mi red local?"
*   **Identificación de tráfico:** "Veo tráfico hacia la IP [X.X.X.X], ¿qué programa en mi PC es el responsable de esa conexión?"
*   **Configuración de red:** "¿Cuál es mi dirección IP, la puerta de enlace y los DNS que estoy usando?"

### 4. Análisis de Capturas de Tráfico (PCAP)
Si tienes archivos de captura de red, puedo ayudarte a interpretarlos:
*   **Búsqueda de archivos:** "¿Dónde están guardados los archivos de captura (.pcap) en este equipo?"
*   **Filtros de captura:** "Dime qué filtro debo usar en Wireshark para analizar el tráfico de esta máquina sin que se llene de ruido innecesario."

### 5. Generación de Reportes
*   **Reporte de Triaje:** "Genera un reporte completo de seguridad de esta máquina" (Esto crea un dashboard HTML con todos los hallazgos de las herramientas anteriores).
*   **Historial de reportes:** "¿Qué reportes de seguridad he generado anteriormente?"

---

**En resumen, puedes pedirme que:**
1.  **Investigue** si hay algo raro en el sistema.
2.  **Identifique** qué aplicaciones están haciendo qué cosas (red, archivos, procesos).
3.  **Explique** por qué ciertos comportamientos son sospechosos basándome en los datos técnicos.
4.  **Documente** todo en un reporte profesional o lo envíe por correo electrónico.

---

Ruta absoluta al intérprete concreto, no `"python"` a secas, y barras dobladas. El
capítulo 16 explica por qué eso se lleva la mitad de las horas perdidas de todo el mundo.

## Uso responsable

Todas las técnicas de este repositorio son **defensivas** y están pensadas para máquinas
propias o con autorización expresa. Usarlas contra sistemas ajenos es ilegal en la mayoría
de las jurisdicciones.

El código ejecuta comandos con los permisos de quien lanza el servidor. Puede modificar y
eliminar datos. Practica en una máquina que puedas permitirte romper.

## Licencia

Código: **MIT**. Úsalo, modifícalo y distribúyelo, incluso comercialmente, conservando el
aviso de copyright.

El texto del libro está sujeto a copyright y no se distribuye aquí.

## Si algo deja de funcionar

Este es un ecosistema en movimiento. Si un ejemplo falla con una versión nueva del SDK, de
PowerShell o de Windows, abre una *issue* indicando qué versión usas y qué error ves.

---

**Denis Sánchez Leyva** — Vertex Coders LLC, Miami, FL
