# -*- coding: utf-8 -*-
"""
Capitulo 17: generacion del informe.

El modelo NO escribe este HTML. Lo escribe Python, aqui, de forma
determinista. El modelo decide QUE incluir y despues INTERPRETA el
resultado, que es lo que sabe hacer bien.

Tres decisiones de diseno, cada una con su motivo:

  1. SIN INTERNET. Nada de Google Charts ni de ninguna libreria por CDN.
     Los graficos son SVG dibujado a mano. Una herramienta de diagnostico
     tiene que funcionar durante el incidente, cuando quiza ya cortaste
     la red (capitulo 7).

  2. UN SOLO ARCHIVO. HTML con el CSS y los graficos dentro. Se adjunta a
     un ticket, se manda por correo, se abre en cualquier maquina dentro
     de dos anos.

  3. DETERMINISTA. Los mismos datos producen exactamente el mismo informe.
     Se puede comparar el de hoy con el de la semana pasada.
"""

import html
import json
import math
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from mcp.server.fastmcp import FastMCP

from ejecutor import limitar, run_ps

mcp = FastMCP("PowerShell Informe")

CARPETA_INFORMES = Path.home() / ".psmcp" / "informes"

# Paleta sobria. Un informe de seguridad no es una infografia.
COLOR_FONDO = "#f7f8fa"
COLOR_TEXTO = "#1c2330"
COLOR_SUAVE = "#6b7684"
COLOR_LINEA = "#d8dde5"
VERDE = "#1f9d55"
AMARILLO = "#d99a00"
ROJO = "#c0392b"
AZUL = "#2f6fb0"

SEMAFORO = {"VERDE": VERDE, "AMARILLO": AMARILLO, "ROJO": ROJO}


# ==================================================================
# GRAFICOS EN SVG, DIBUJADOS A MANO
# ==================================================================

def _arco(cx: float, cy: float, radio: float, desde: float, hasta: float) -> str:
    """Calcula el trazado de un sector de circunferencia."""
    x1 = cx + radio * math.cos(math.radians(desde - 90))
    y1 = cy + radio * math.sin(math.radians(desde - 90))
    x2 = cx + radio * math.cos(math.radians(hasta - 90))
    y2 = cy + radio * math.sin(math.radians(hasta - 90))
    grande = 1 if (hasta - desde) > 180 else 0
    return f"M {cx} {cy} L {x1} {y1} A {radio} {radio} 0 {grande} 1 {x2} {y2} Z"


def dona(datos: List[Tuple[str, float]], titulo: str,
         colores: Optional[List[str]] = None) -> str:
    """Grafico de dona en SVG puro. Sin JavaScript, sin dependencias."""
    total = sum(v for _, v in datos)
    if total <= 0:
        return f'<p class="vacio">{html.escape(titulo)}: sin datos</p>'

    paleta = colores or [AZUL, VERDE, AMARILLO, ROJO, "#7b5ea7", "#4c8c8c", COLOR_SUAVE]
    cx, cy, radio = 110, 110, 95

    sectores, leyenda = [], []
    angulo = 0.0
    for i, (etiqueta, valor) in enumerate(datos):
        if valor <= 0:
            continue
        porcion = valor / total * 360
        color = paleta[i % len(paleta)]
        sectores.append(
            f'<path d="{_arco(cx, cy, radio, angulo, angulo + porcion)}" '
            f'fill="{color}" stroke="#fff" stroke-width="2"/>'
        )
        leyenda.append(
            f'<li><span class="punto" style="background:{color}"></span>'
            f'{html.escape(str(etiqueta))} '
            f'<b>{valor:g}</b> <span class="pct">{valor / total * 100:.0f}%</span></li>'
        )
        angulo += porcion

    return (
        f'<div class="grafico">\n'
        f'  <h3>{html.escape(titulo)}</h3>\n'
        f'  <div class="dona-fila">\n'
        f'    <svg viewBox="0 0 220 220" width="200" height="200" role="img">\n'
        f'      {"".join(sectores)}\n'
        f'      <circle cx="{cx}" cy="{cy}" r="52" fill="{COLOR_FONDO}"/>\n'
        f'      <text x="{cx}" y="{cy + 6}" text-anchor="middle" '
        f'font-size="26" fill="{COLOR_TEXTO}">{total:g}</text>\n'
        f'    </svg>\n'
        f'    <ul class="leyenda">{"".join(leyenda)}</ul>\n'
        f'  </div>\n'
        f'</div>'
    )


def barras(datos: List[Tuple[str, float]], titulo: str, unidad: str = "") -> str:
    """Barras horizontales. Se leen mejor que las verticales con etiquetas largas."""
    if not datos:
        return f'<p class="vacio">{html.escape(titulo)}: sin datos</p>'

    maximo = max(v for _, v in datos) or 1
    filas = []
    for etiqueta, valor in datos:
        ancho = valor / maximo * 100
        filas.append(
            f'<div class="barra-fila">'
            f'<span class="barra-etq">{html.escape(str(etiqueta))}</span>'
            f'<span class="barra-pista"><span class="barra-relleno" '
            f'style="width:{ancho:.1f}%"></span></span>'
            f'<span class="barra-val">{valor:g}{html.escape(unidad)}</span>'
            f'</div>'
        )
    return (f'<div class="grafico"><h3>{html.escape(titulo)}</h3>'
            f'{"".join(filas)}</div>')


def medidor(porcentaje: float, titulo: str, invertir: bool = False) -> str:
    """Barra de ocupacion con color segun el umbral.

    invertir=True cuando lo alto es bueno (por ejemplo, espacio libre).
    """
    p = max(0.0, min(100.0, porcentaje))
    critico = (100 - p) if invertir else p
    color = VERDE if critico < 70 else (AMARILLO if critico < 90 else ROJO)
    return (
        f'<div class="medidor">'
        f'<div class="medidor-cab"><span>{html.escape(titulo)}</span>'
        f'<b style="color:{color}">{p:.0f}%</b></div>'
        f'<div class="barra-pista"><span class="barra-relleno" '
        f'style="width:{p:.1f}%;background:{color}"></span></div>'
        f'</div>'
    )


# ==================================================================
# RECOGIDA DE DATOS
# ==================================================================

def _json_ps(script: str, timeout: int = 60) -> Any:
    crudo = run_ps(script, timeout=timeout, strict=False)
    try:
        return json.loads(crudo)
    except Exception:
        return None


def recoger() -> Dict[str, Any]:
    """Reune todo lo que el informe necesita, en el minimo de llamadas."""
    datos: Dict[str, Any] = {"errores": []}

    datos["sistema"] = _json_ps(r"""
$os  = Get-CimInstance Win32_OperatingSystem
$cs  = Get-CimInstance Win32_ComputerSystem
$reg = Get-ItemProperty 'HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion'
[PSCustomObject]@{
    Equipo         = $cs.Name
    SO             = $os.Caption
    Version        = $reg.DisplayVersion
    Build          = "$($reg.CurrentBuild).$($reg.UBR)"
    Arquitectura   = $os.OSArchitecture
    RAM_GB         = [math]::Round($cs.TotalPhysicalMemory / 1GB, 1)
    Fabricante     = $cs.Manufacturer
    Modelo         = $cs.Model
    EnDominio      = $cs.PartOfDomain
    UltimoArranque = $os.LastBootUpTime.ToString('yyyy-MM-dd HH:mm:ss')
    UptimeHoras    = [math]::Round(((Get-Date) - $os.LastBootUpTime).TotalHours, 1)
} | ConvertTo-Json -Depth 3
""")

    datos["memoria"] = _json_ps(r"""
$os = Get-CimInstance Win32_OperatingSystem
$t = $os.TotalVisibleMemorySize; $l = $os.FreePhysicalMemory
[PSCustomObject]@{
    TotalGB = [math]::Round($t / 1MB, 2)
    UsadaGB = [math]::Round(($t - $l) / 1MB, 2)
    LibreGB = [math]::Round($l / 1MB, 2)
    PorcentajeUso = [math]::Round(100 - ($l / $t * 100), 1)
} | ConvertTo-Json
""")

    datos["discos"] = _json_ps(r"""
$d = Get-PSDrive -PSProvider FileSystem | Where-Object { $_.Used -ne $null } | ForEach-Object {
    $tot = $_.Used + $_.Free
    [PSCustomObject]@{
        Unidad = $_.Name
        UsadoGB = [math]::Round($_.Used / 1GB, 1)
        LibreGB = [math]::Round($_.Free / 1GB, 1)
        PorcentajeUso = if ($tot -gt 0) { [math]::Round($_.Used / $tot * 100, 1) } else { 0 }
    }
}
ConvertTo-Json -InputObject @($d) -Depth 3
""")

    datos["procesos"] = _json_ps(r"""
$p = Get-Process | Sort-Object WorkingSet64 -Descending | Select-Object -First 8 | ForEach-Object {
    [PSCustomObject]@{ Nombre = $_.Name; MemoriaMB = [math]::Round($_.WorkingSet64 / 1MB, 0) }
}
ConvertTo-Json -InputObject @($p) -Depth 3
""")

    datos["seguridad"] = _json_ps(r"""
$mp   = try { Get-MpComputerStatus } catch { $null }
$pref = try { Get-MpPreference } catch { $null }
$fw   = try { @(Get-NetFirewallProfile | Where-Object Enabled -eq $true).Count } catch { 0 }
$uac  = Get-ItemProperty 'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Policies\System' -ErrorAction SilentlyContinue
[PSCustomObject]@{
    TiempoReal     = if ($mp) { [bool]$mp.RealTimeProtectionEnabled } else { $null }
    TamperProt     = if ($mp) { [bool]$mp.IsTamperProtected } else { $null }
    EdadFirmasDias = if ($mp) { [int]$mp.AntivirusSignatureAge } else { $null }
    Exclusiones    = if ($pref) { @($pref.ExclusionPath).Count + @($pref.ExclusionProcess).Count } else { 0 }
    PerfilesFwOn   = $fw
    UAC            = ($uac.EnableLUA -eq 1)
} | ConvertTo-Json
""", timeout=90)

    datos["red"] = _json_ps(r"""
$est = @(Get-NetTCPConnection -State Established -ErrorAction SilentlyContinue)
$esc = @(Get-NetTCPConnection -State Listen -ErrorAction SilentlyContinue)
$exp = @($esc | Where-Object { $_.LocalAddress -eq '0.0.0.0' -or $_.LocalAddress -eq '::' })
$priv = @($est | Where-Object { $_.RemoteAddress -match '^(10\.|192\.168\.|172\.(1[6-9]|2[0-9]|3[01])\.|127\.|::1)' })
[PSCustomObject]@{
    Establecidas = $est.Count
    Escuchando   = $esc.Count
    ExpuestosRed = ($exp | Select-Object -ExpandProperty LocalPort -Unique).Count
    HaciaPrivada = $priv.Count
    HaciaPublica = ($est.Count - $priv.Count)
} | ConvertTo-Json
""", timeout=90)

    datos["arranque"] = _json_ps(r"""
$claves = @(
 'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Run',
 'HKCU:\SOFTWARE\Microsoft\Windows\CurrentVersion\Run')
$n = 0
foreach ($k in $claves) {
    if (Test-Path $k) {
        $p = Get-ItemProperty $k
        foreach ($x in $p.PSObject.Properties) { if ($x.Name -notlike 'PS*') { $n++ } }
    }
}
$tareas = @(Get-ScheduledTask -ErrorAction SilentlyContinue |
    Where-Object { $_.TaskPath -notlike '\Microsoft\*' -and $_.State -ne 'Disabled' }).Count
$svc = @(Get-Service | Where-Object { $_.Status -eq 'Running' }).Count
[PSCustomObject]@{ RunKeys = $n; TareasNoMicrosoft = $tareas; ServiciosActivos = $svc } | ConvertTo-Json
""", timeout=90)

    for clave, valor in datos.items():
        if clave != "errores" and valor is None:
            datos["errores"].append(clave)

    return datos


# ==================================================================
# COMPOSICION DEL INFORME
# ==================================================================

def _tarjeta(etiqueta: str, valor: Any, nota: str = "", color: str = "") -> str:
    estilo = f' style="color:{color}"' if color else ""
    return (f'<div class="tarjeta"><div class="tarjeta-etq">{html.escape(etiqueta)}</div>'
            f'<div class="tarjeta-val"{estilo}>{html.escape(str(valor))}</div>'
            + (f'<div class="tarjeta-nota">{html.escape(nota)}</div>' if nota else "")
            + '</div>')


def componer(datos: Dict[str, Any], semaforo: str = "VERDE",
             puntuacion: int = 0, hallazgos: Optional[List[str]] = None) -> str:
    sis = datos.get("sistema") or {}
    mem = datos.get("memoria") or {}
    seg = datos.get("seguridad") or {}
    red = datos.get("red") or {}
    arr = datos.get("arranque") or {}
    discos = datos.get("discos") or []
    procesos = datos.get("procesos") or []

    ahora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    color_sem = SEMAFORO.get(semaforo, COLOR_SUAVE)

    # --- cabecera y veredicto ---
    partes = [
        f'<header><h1>Informe de estado</h1>'
        f'<p class="sub">{html.escape(str(sis.get("Equipo", "equipo desconocido")))} '
        f'&middot; {html.escape(ahora)}</p></header>',
        f'<section class="veredicto" style="border-color:{color_sem}">'
        f'<div class="sem" style="background:{color_sem}"></div>'
        f'<div><div class="sem-txt" style="color:{color_sem}">{semaforo}</div>'
        f'<div class="sem-pts">Puntuacion de riesgo: {puntuacion}</div></div></section>',
    ]

    if hallazgos:
        filas = "".join(f"<li>{html.escape(h)}</li>" for h in hallazgos)
        partes.append(f'<section><h2>Hallazgos</h2><ul class="hallazgos">{filas}</ul></section>')

    if datos.get("errores"):
        faltan = ", ".join(datos["errores"])
        partes.append(
            f'<section class="aviso"><b>Comprobaciones no realizadas:</b> '
            f'{html.escape(faltan)}. Este informe es parcial: la ausencia de '
            f'hallazgos en esas areas no significa que no los haya.</section>'
        )

    # --- identidad ---
    partes.append(
        '<section><h2>Sistema</h2><div class="tarjetas">'
        + _tarjeta("Sistema operativo", f'{sis.get("SO", "?")} {sis.get("Version", "")}')
        + _tarjeta("Compilacion", sis.get("Build", "?"))
        + _tarjeta("Equipo", f'{sis.get("Fabricante", "")} {sis.get("Modelo", "")}'.strip() or "?")
        + _tarjeta("Memoria fisica", f'{sis.get("RAM_GB", "?")} GB')
        + _tarjeta("En dominio", "Si" if sis.get("EnDominio") else "No")
        + _tarjeta("Tiempo encendido", f'{sis.get("UptimeHoras", "?")} h',
                   f'desde {sis.get("UltimoArranque", "?")}')
        + '</div></section>'
    )

    # --- recursos ---
    medidores = []
    if mem.get("PorcentajeUso") is not None:
        medidores.append(medidor(float(mem["PorcentajeUso"]),
                                 f'Memoria  ({mem.get("UsadaGB")} de {mem.get("TotalGB")} GB)'))
    for d in discos:
        medidores.append(medidor(float(d.get("PorcentajeUso", 0)),
                                 f'Disco {d.get("Unidad")}:  ({d.get("LibreGB")} GB libres)'))

    grafico_procesos = barras(
        [(p.get("Nombre", "?"), float(p.get("MemoriaMB", 0))) for p in procesos][:8],
        "Procesos por memoria", " MB")

    partes.append(
        '<section><h2>Recursos</h2>'
        f'<div class="dos-columnas"><div>{"".join(medidores)}</div>'
        f'<div>{grafico_procesos}</div></div></section>'
    )

    # --- seguridad ---
    def si_no(v, bueno=True):
        if v is None:
            return "?", COLOR_SUAVE
        ok = bool(v) == bueno
        return ("Si" if v else "No"), (VERDE if ok else ROJO)

    tr, c_tr = si_no(seg.get("TiempoReal"))
    tp, c_tp = si_no(seg.get("TamperProt"))
    ua, c_ua = si_no(seg.get("UAC"))
    exc = seg.get("Exclusiones", 0)
    fw = seg.get("PerfilesFwOn", 0)

    partes.append(
        '<section><h2>Postura de seguridad</h2><div class="tarjetas">'
        + _tarjeta("Proteccion en tiempo real", tr, color=c_tr)
        + _tarjeta("Proteccion antimanipulacion", tp, color=c_tp)
        + _tarjeta("Control de cuentas (UAC)", ua, color=c_ua)
        + _tarjeta("Perfiles de firewall activos", f"{fw} de 3",
                   color=VERDE if fw == 3 else ROJO)
        + _tarjeta("Exclusiones del antivirus", exc,
                   "revisar una por una" if exc else "ninguna",
                   color=AMARILLO if exc else VERDE)
        + _tarjeta("Antiguedad de las firmas", f'{seg.get("EdadFirmasDias", "?")} dias',
                   color=VERDE if (seg.get("EdadFirmasDias") or 99) <= 3 else AMARILLO)
        + '</div></section>'
    )

    # --- red y arranque ---
    graf_red = dona([
        ("A red privada", float(red.get("HaciaPrivada", 0))),
        ("A red publica", float(red.get("HaciaPublica", 0))),
    ], "Conexiones establecidas", [AZUL, AMARILLO])

    graf_arr = barras([
        ("Claves de arranque", float(arr.get("RunKeys", 0))),
        ("Tareas no-Microsoft", float(arr.get("TareasNoMicrosoft", 0))),
        ("Servicios activos", float(arr.get("ServiciosActivos", 0))),
    ], "Superficie de arranque")

    partes.append(
        '<section><h2>Red y arranque automatico</h2>'
        f'<div class="dos-columnas"><div>{graf_red}'
        + _tarjeta("Puertos expuestos a la red", red.get("ExpuestosRed", "?"),
                   "escuchando en 0.0.0.0",
                   color=AMARILLO if (red.get("ExpuestosRed") or 0) else VERDE)
        + f'</div><div>{graf_arr}</div></div></section>'
    )

    partes.append(
        '<footer>Generado por el servidor MCP de PowerShell. '
        'Los datos proceden de una sola lectura del sistema en la fecha indicada. '
        'Este informe no sustituye a un analisis forense.</footer>'
    )

    return PLANTILLA_HTML.format(
        titulo=html.escape(f'Informe {sis.get("Equipo", "")} {ahora}'),
        css=CSS_INFORME,
        cuerpo="\n".join(partes),
    )


PLANTILLA_HTML = """<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>{titulo}</title>
<style>{css}</style>
</head>
<body>
<main>
{cuerpo}
</main>
</body>
</html>
"""

CSS_INFORME = f"""
* {{ box-sizing: border-box; }}
body {{ margin:0; background:{COLOR_FONDO}; color:{COLOR_TEXTO};
  font-family: "Segoe UI", system-ui, sans-serif; line-height:1.5; }}
main {{ max-width: 980px; margin: 0 auto; padding: 32px 20px 60px; }}
header h1 {{ margin:0; font-size:1.9rem; letter-spacing:-.01em; }}
.sub {{ margin:.25rem 0 0; color:{COLOR_SUAVE}; }}
h2 {{ font-size:1.05rem; text-transform:uppercase; letter-spacing:.06em;
  color:{COLOR_SUAVE}; margin:2.2rem 0 .8rem; }}
h3 {{ font-size:.95rem; margin:0 0 .6rem; }}
section.veredicto {{ display:flex; align-items:center; gap:16px; margin-top:20px;
  padding:16px 20px; background:#fff; border-left:6px solid; border-radius:6px; }}
.sem {{ width:34px; height:34px; border-radius:50%; flex:none; }}
.sem-txt {{ font-size:1.4rem; font-weight:700; line-height:1; }}
.sem-pts {{ color:{COLOR_SUAVE}; font-size:.9rem; }}
.tarjetas {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(190px,1fr)); gap:12px; }}
.tarjeta {{ background:#fff; border:1px solid {COLOR_LINEA}; border-radius:6px; padding:12px 14px; }}
.tarjeta-etq {{ font-size:.75rem; text-transform:uppercase; letter-spacing:.05em;
  color:{COLOR_SUAVE}; }}
.tarjeta-val {{ font-size:1.25rem; font-weight:600; margin-top:2px; }}
.tarjeta-nota {{ font-size:.8rem; color:{COLOR_SUAVE}; }}
.dos-columnas {{ display:grid; grid-template-columns:1fr 1fr; gap:20px; }}
@media (max-width:720px) {{ .dos-columnas {{ grid-template-columns:1fr; }} }}
.grafico {{ background:#fff; border:1px solid {COLOR_LINEA}; border-radius:6px; padding:14px 16px; }}
.dona-fila {{ display:flex; align-items:center; gap:16px; flex-wrap:wrap; }}
.leyenda {{ list-style:none; margin:0; padding:0; font-size:.9rem; }}
.leyenda li {{ margin:.25rem 0; }}
.punto {{ display:inline-block; width:10px; height:10px; border-radius:2px; margin-right:6px; }}
.pct {{ color:{COLOR_SUAVE}; }}
.medidor {{ background:#fff; border:1px solid {COLOR_LINEA}; border-radius:6px;
  padding:12px 14px; margin-bottom:10px; }}
.medidor-cab {{ display:flex; justify-content:space-between; font-size:.9rem; margin-bottom:6px; }}
.barra-pista {{ display:block; background:#e9edf3; border-radius:4px; height:9px; overflow:hidden; }}
.barra-relleno {{ display:block; height:100%; background:{AZUL}; }}
.barra-fila {{ display:grid; grid-template-columns:130px 1fr 70px; align-items:center;
  gap:8px; font-size:.85rem; margin:.35rem 0; }}
.barra-etq {{ overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }}
.barra-val {{ text-align:right; color:{COLOR_SUAVE}; }}
.hallazgos {{ margin:0; padding-left:1.1rem; }}
.hallazgos li {{ margin:.3rem 0; }}
.aviso {{ background:#fff8e1; border:1px solid {AMARILLO}; border-radius:6px;
  padding:12px 16px; margin-top:16px; font-size:.9rem; }}
.vacio {{ color:{COLOR_SUAVE}; font-style:italic; }}
footer {{ margin-top:3rem; padding-top:1rem; border-top:1px solid {COLOR_LINEA};
  color:{COLOR_SUAVE}; font-size:.8rem; }}
@media print {{ body {{ background:#fff; }} section {{ break-inside: avoid; }} }}
"""


# ==================================================================
# HERRAMIENTA MCP
# ==================================================================

@mcp.tool()
def generate_report(semaforo: str = "VERDE", puntuacion: int = 0,
                    hallazgos: str = "") -> str:
    """Generates a complete HTML dashboard report of this machine and saves it to disk.

    Collects system identity, memory and disk usage, top processes, security posture,
    network connections and automatic start points, and renders them as charts in a
    single self-contained HTML file that works offline.

    Call the triage tools FIRST, then pass their verdict here: semaforo must be VERDE,
    AMARILLO or ROJO, puntuacion is the risk score, and hallazgos is a list of findings
    separated by ' | '. The report shows whatever you pass; it does not decide the
    verdict itself.

    Returns the path of the generated file. Tell the user where it is and summarise the
    three most important things it contains.
    """
    if semaforo not in SEMAFORO:
        return "[ERROR] semaforo debe ser VERDE, AMARILLO o ROJO."

    datos = recoger()
    lista = [h.strip() for h in hallazgos.split("|") if h.strip()]

    documento = componer(datos, semaforo, limitar(puntuacion, 0, 999), lista)

    CARPETA_INFORMES.mkdir(parents=True, exist_ok=True)
    equipo = (datos.get("sistema") or {}).get("Equipo", "equipo")
    marca = datetime.now().strftime("%Y%m%d_%H%M%S")
    destino = CARPETA_INFORMES / f"informe_{equipo}_{marca}.html"
    destino.write_text(documento, encoding="utf-8")

    return json.dumps({
        "archivo": str(destino),
        "tamano_kb": round(destino.stat().st_size / 1024, 1),
        "semaforo": semaforo,
        "secciones": ["Sistema", "Recursos", "Postura de seguridad", "Red y arranque"],
        "comprobaciones_fallidas": datos.get("errores", []),
        "nota": "Archivo autocontenido: se abre sin conexion a internet.",
    }, ensure_ascii=False, indent=2)


@mcp.tool()
def list_reports(count: int = 10) -> str:
    """Lists previously generated reports, newest first, so they can be compared."""
    if not CARPETA_INFORMES.exists():
        return "[INFO] Todavia no se ha generado ningun informe."
    archivos = sorted(CARPETA_INFORMES.glob("informe_*.html"),
                      key=lambda p: p.stat().st_mtime, reverse=True)
    return json.dumps([
        {"archivo": str(a),
         "fecha": datetime.fromtimestamp(a.stat().st_mtime).strftime("%Y-%m-%d %H:%M:%S"),
         "tamano_kb": round(a.stat().st_size / 1024, 1)}
        for a in archivos[:limitar(count, 1, 50)]
    ], ensure_ascii=False, indent=2)


if __name__ == "__main__":
    print("Servidor de informes arrancando...", file=sys.stderr)
    mcp.run()
