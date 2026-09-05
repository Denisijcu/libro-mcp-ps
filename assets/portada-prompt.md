# Portada — prompt e instrucciones

## Aviso previo

**No le pidas el texto al generador de imágenes.** Los modelos de imagen escriben mal, y
en una portada un carácter torcido se nota. Genera solo el fondo y pon el título encima en
un editor (GIMP, Photoshop, Canva, Figma).

Requisitos de KDP: **JPEG, 1600 × 2560 px**, ratio 1:1.6. Guardar como
`assets/portada.jpg` y el script `construir_epub.py` la incorpora sola.

---

## Prompt principal — recomendado

```
Vertical book cover background, 1600x2560, no text, no letters, no words.

A dark navy-to-black gradient background. In the centre, a stylised terminal
window rendered as clean flat vector geometry, its outline glowing in
electric cyan. Emerging from the terminal window, a network of thin luminous
lines branches outward like roots or circuitry, connecting to small
hexagonal nodes that fade into the darkness at the edges.

Style: minimal technical illustration, flat vector, sharp geometry, high
contrast. Limited palette: deep navy background, electric cyan and a single
warm amber accent on two or three nodes. Generous empty space in the upper
third and lower quarter of the image for typography to be added later.

No text, no letters, no numbers, no logos, no human figures, no keyboards,
no realistic hardware.
```

**Por qué así:** el terminal dice PowerShell sin escribir la palabra, la red de nodos dice
agentes y MCP, y el hueco arriba y abajo es donde va el título. El cian sobre azul oscuro
sobrevive en miniatura, que es como el 90% de los compradores van a verla.

---

## Alternativa A — más de seguridad

```
Vertical book cover background, 1600x2560, no text, no letters, no words.

A dark slate background. Centre composition: a geometric shield formed from
thin interlocking hexagons, drawn as a flat vector outline in electric cyan.
Behind the shield, faint horizontal lines suggest terminal output, blurred
and dim, never legible. A few hexagons of the shield glow warm amber, as if
recently triggered.

Style: minimal technical illustration, flat vector, high contrast, dark
background. Palette: slate, electric cyan, one amber accent. Large empty
areas top and bottom for typography.

No text, no letters, no numbers, no logos, no padlock clichés, no human
figures.
```

## Alternativa B — más abstracta

```
Vertical book cover background, 1600x2560, no text, no letters, no words.

Abstract vertical composition on near-black. A single luminous cyan line
enters from the top edge and descends, branching into a controlled tree
structure of thinner lines that spread across the lower two thirds, each
branch ending in a small square node. Two or three nodes glow amber. Thin
grid lines are faintly visible behind everything.

Style: minimal generative art, precise geometry, flat, high contrast, dark.
Palette: near-black, electric cyan, amber accent. Wide empty margin at the
top for a title.

No text, no letters, no numbers, no logos, no human figures.
```

---

## Texto a montar encima

| Elemento | Contenido | Notas |
|---|---|---|
| Título | POWERSHELL CON AGENTES | Lo más grande. Tiene que leerse en miniatura |
| Subtítulo | Construye tu propio MCP para administrar y defender Windows 11 | Bastante más pequeño |
| Autor | DENIS SÁNCHEZ LEYVA | Abajo |

**Tipografía**: una sans-serif de peso alto y ancho estrecho para el título (Inter, Barlow
Condensed, Archivo). Nada de fuentes con serifas finas ni "de hacker" con glifos raros:
desaparecen al reducir.

**Colocación**: título en el tercio superior, autor en el cuarto inferior. Que ninguna
línea del fondo cruce por detrás del texto.

## La prueba que decide

Reduce la portada terminada a **160 px de alto** y míralas así. Si a ese tamaño no se lee
"POWERSHELL", la portada no sirve, por bonita que sea grande. Es el tamaño real al que
aparece en los resultados de búsqueda de Amazon.
