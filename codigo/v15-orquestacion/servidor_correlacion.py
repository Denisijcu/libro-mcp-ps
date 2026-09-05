# -*- coding: utf-8 -*-
"""
Capitulo 15: herramientas de correlacion entre servidores MCP.

Este servidor NO analiza trafico. Analizar pcap es trabajo del MCP de
Wireshark, y duplicarlo seria un error de diseno.

Lo que hace es la pieza que ningun servidor por separado puede hacer: cruzar
lo que ve PowerShell (procesos, puertos, dueno de cada conexion) con lo que ve
la captura (paquetes, IPs, volumenes). Ese cruce es el valor de tener dos
servidores, y necesita un traductor entre los dos.

El flujo tipico:
  1. get_connection_map()        -> este servidor: IP -> proceso -> ruta
  2. suggest_capture_filter()    -> este servidor: genera el filtro
  3. el MCP de Wireshark analiza la captura con ese filtro
  4. explain_remote_endpoint()   -> este servidor: quien hablaba con esa IP
"""

import sys

from mcp.server.fastmcp import FastMCP

from ejecutor import limitar, run_ps

mcp = FastMCP("PowerShell Correlacion")


@mcp.tool()
def get_connection_map(count: int = 60) -> str:
    """Builds a map of every established TCP connection to the process that owns it,
    with the process path and signature status.

    This is the missing link between a packet capture and the machine: a capture shows
    IP addresses talking, but not WHICH PROGRAM was talking. Run this before or right
    after taking a capture, and keep the result to interpret the traffic.
    """
    script = r"""
$procesos = @{}
foreach ($p in Get-CimInstance Win32_Process) { $procesos[[int]$p.ProcessId] = $p }

$mapa = @{}
foreach ($c in Get-NetTCPConnection -State Established -ErrorAction SilentlyContinue) {
    $proc = $procesos[[int]$c.OwningProcess]
    $clave = $c.RemoteAddress
    if (-not $mapa.ContainsKey($clave)) {
        $mapa[$clave] = [PSCustomObject]@{
            IP           = $c.RemoteAddress
            RedPrivada   = [bool]($c.RemoteAddress -match '^(10\.|192\.168\.|172\.(1[6-9]|2[0-9]|3[01])\.|127\.|::1|fe80)')
            Puertos      = New-Object System.Collections.ArrayList
            Procesos     = New-Object System.Collections.ArrayList
            Conexiones   = 0
        }
    }
    $e = $mapa[$clave]
    $e.Conexiones++
    if (-not $e.Puertos.Contains($c.RemotePort)) { [void]$e.Puertos.Add($c.RemotePort) }
    if ($proc) {
        $etiqueta = "$($proc.Name) (PID $($proc.ProcessId))"
        if (-not $e.Procesos.Contains($etiqueta)) { [void]$e.Procesos.Add($etiqueta) }
    }
}

$lista = $mapa.Values | Sort-Object -Property @{E={$_.RedPrivada}}, @{E={$_.Conexiones};Descending=$true} |
    Select-Object -First ([int]$Cantidad) | ForEach-Object {
        [PSCustomObject]@{
            IP         = $_.IP
            RedPrivada = $_.RedPrivada
            Puertos    = @($_.Puertos)
            Procesos   = @($_.Procesos)
            Conexiones = $_.Conexiones
        }
    }

[PSCustomObject]@{
    TomadoEn  = (Get-Date).ToString('yyyy-MM-dd HH:mm:ss')
    Endpoints = @($lista)
    Nota      = 'Esta foto vale para el momento en que se tomo. Una conexion que aparece en la captura y no aqui puede haberse cerrado antes.'
} | ConvertTo-Json -Depth 4
"""
    return run_ps(script, {"Cantidad": limitar(count, 1, 200)}, timeout=90, strict=False)


@mcp.tool()
def explain_remote_endpoint(ip_address: str) -> str:
    """Given an IP address seen in a packet capture, finds which local processes are or
    were talking to it, on which ports, plus the process path and signature.

    Use it after the packet analysis flags an address: this answers 'and what program on
    my machine was that?'.
    """
    script = r"""
$procesos = @{}
foreach ($p in Get-CimInstance Win32_Process) { $procesos[[int]$p.ProcessId] = $p }

$cacheFirma = @{}
$coincidencias = @()

foreach ($c in Get-NetTCPConnection -ErrorAction SilentlyContinue) {
    if ($c.RemoteAddress -ne $IP) { continue }
    $proc = $procesos[[int]$c.OwningProcess]
    $ruta = if ($proc) { $proc.ExecutablePath } else { $null }
    $firma = 'SinRuta'
    if ($ruta) {
        if (-not $cacheFirma.ContainsKey($ruta)) {
            $cacheFirma[$ruta] = (Get-AuthenticodeSignature $ruta).Status.ToString()
        }
        $firma = $cacheFirma[$ruta]
    }
    $coincidencias += [PSCustomObject]@{
        Estado       = $c.State.ToString()
        PuertoLocal  = $c.LocalPort
        PuertoRemoto = $c.RemotePort
        PID          = $c.OwningProcess
        Proceso      = if ($proc) { $proc.Name } else { $null }
        Ruta         = $ruta
        Firma        = $firma
        CommandLine  = if ($proc) { $proc.CommandLine } else { $null }
    }
}

# La cache DNS puede recordar el nombre aunque la conexion ya no exista.
$dns = @(Get-DnsClientCache -ErrorAction SilentlyContinue |
    Where-Object { $_.Data -eq $IP } | Select-Object -ExpandProperty Entry -Unique)

[PSCustomObject]@{
    IP              = $IP
    ConexionesVivas = $coincidencias.Count
    Conexiones      = @($coincidencias)
    NombresDNS      = $dns
    Nota            = if ($coincidencias.Count -eq 0) {
        'Ninguna conexion viva ahora mismo hacia esa IP. Si aparecia en la captura, el proceso ya cerro la conexion o termino. Prueba con los eventos de creacion de proceso.'
    } else { $null }
} | ConvertTo-Json -Depth 4
"""
    return run_ps(script, {"IP": ip_address}, timeout=90, strict=False)


@mcp.tool()
def suggest_capture_filter(exclude_web: bool = True, focus_ip: str = "") -> str:
    """Builds a tshark display filter for analysing a capture of this machine, based on
    what is actually running on it right now.

    Excludes the ports used by the machine's own known services so the capture analysis
    is not drowned in normal traffic. Pass the filter to the packet-analysis server.
    """
    script = r"""
$excluirWeb = ($ExcluirWeb -eq '1')

# Puertos remotos con los que la maquina habla ahora mismo, para saber que es rutina.
$puertos = @(Get-NetTCPConnection -State Established -ErrorAction SilentlyContinue |
    Select-Object -ExpandProperty RemotePort -Unique | Sort-Object)

$partes = @('tcp')
if ($excluirWeb) {
    # Sintaxis de tshark: la lista va con comas, NO con espacios.
    $partes += '!(tcp.dstport in {80,443,8080,8443})'
}
if ($IP) { $partes += "ip.addr == $IP" }

$filtro = $partes -join ' && '

[PSCustomObject]@{
    Filtro            = $filtro
    PuertosRemotosEnUso = @($puertos)
    Explicacion       = if ($excluirWeb) {
        'Se excluye el trafico web habitual (80, 443, 8080, 8443) para que no tape lo demas. Si buscas exfiltracion por HTTPS, vuelve a llamar con exclude_web en falso.'
    } else {
        'Sin exclusiones: veras todo el trafico TCP, incluido el web normal.'
    }
    Aviso             = 'En tshark la lista de puertos va separada por COMAS. Con espacios el filtro se acepta pero no filtra lo que crees.'
} | ConvertTo-Json -Depth 3
"""
    return run_ps(script, {"ExcluirWeb": exclude_web, "IP": focus_ip}, timeout=60, strict=False)


@mcp.tool()
def find_capture_files(folder: str = "", count: int = 20) -> str:
    """Lists packet capture files (.pcap, .pcapng) under a folder, newest first, with
    their size and modification time.

    Use it to find which capture to analyse before handing the path to the packet
    analysis server.
    """
    script = r"""
$raiz = if ($Carpeta) { $Carpeta } else { [Environment]::GetFolderPath('UserProfile') }
if (-not (Test-Path $raiz)) { "La carpeta no existe: $raiz"; return }

$lista = Get-ChildItem -Path $raiz -Recurse -File -Include *.pcap, *.pcapng -ErrorAction SilentlyContinue |
    Sort-Object LastWriteTime -Descending | Select-Object -First ([int]$Cantidad) | ForEach-Object {
        [PSCustomObject]@{
            Ruta         = $_.FullName
            TamanoMB     = [math]::Round($_.Length / 1MB, 2)
            Modificado   = $_.LastWriteTime.ToString('yyyy-MM-dd HH:mm:ss')
        }
    }

[PSCustomObject]@{
    RaizBuscada = $raiz
    Encontradas = @($lista).Count
    Capturas    = @($lista)
} | ConvertTo-Json -Depth 3
"""
    return run_ps(
        script,
        {"Carpeta": folder, "Cantidad": limitar(count, 1, 50)},
        timeout=120,
        strict=False,
    )


if __name__ == "__main__":
    print("Servidor de correlacion arrancando...", file=sys.stderr)
    mcp.run()
