# -*- coding: utf-8 -*-
"""
Capitulo 12: el servidor como administrador. Herramientas de inventario.

Todas de nivel read. Ninguna cambia nada en la maquina.

Incorpora las tres lecciones que salieron al verificar los comandos:

  1. Nada de $env:*. El proceso del servidor NO hereda el entorno de tu consola:
     $env:COMPUTERNAME viene vacio. Se usa CIM.
  2. Nada de ProductName del registro: en un Windows 11 sigue diciendo
     "Windows 10". El nombre sale de Win32_OperatingSystem.Caption.
  3. Las fechas se convierten a texto ANTES de serializar. ConvertTo-Json las
     escribe como /Date(1787697380711)/, que el modelo no puede leer.
"""

import sys

from mcp.server.fastmcp import FastMCP

# El ejecutor seguro del capitulo 8 y los limites del capitulo 10.
# En el repo del libro estos modulos viven en sus carpetas; aqui se asume
# que estan al lado.
from ejecutor import limitar, run_ps

mcp = FastMCP("PowerShell Inventario")


@mcp.tool()
def get_system_info() -> str:
    """Gets a full identity summary of this Windows machine: name, edition, version,
    build, architecture, RAM, domain membership, boot time and uptime.

    Use it as the first call when you know nothing about the machine.
    """
    script = r"""
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
    Dominio        = $cs.Domain
    UltimoArranque = $os.LastBootUpTime.ToString('yyyy-MM-dd HH:mm:ss')
    UptimeHoras    = [math]::Round(((Get-Date) - $os.LastBootUpTime).TotalHours, 1)
} | ConvertTo-Json -Depth 3
"""
    return run_ps(script)


@mcp.tool()
def get_disk_usage() -> str:
    """Lists every filesystem drive with used, free and total space in GB, plus the
    percentage free.

    Use it to check whether the machine is running out of disk space.
    """
    script = r"""
$discos = Get-PSDrive -PSProvider FileSystem | Where-Object { $_.Used -ne $null } | ForEach-Object {
    $total = $_.Used + $_.Free
    [PSCustomObject]@{
        Unidad          = $_.Name
        UsadoGB         = [math]::Round($_.Used / 1GB, 2)
        LibreGB         = [math]::Round($_.Free / 1GB, 2)
        TotalGB         = [math]::Round($total / 1GB, 2)
        PorcentajeLibre = if ($total -gt 0) { [math]::Round($_.Free / $total * 100, 1) } else { 0 }
    }
}
ConvertTo-Json -InputObject @($discos) -Depth 3
"""
    return run_ps(script, strict=False)


@mcp.tool()
def get_memory_usage() -> str:
    """Gets total, used and free physical memory in GB with the usage percentage."""
    script = r"""
$os = Get-CimInstance Win32_OperatingSystem
$totalKB = $os.TotalVisibleMemorySize
$libreKB = $os.FreePhysicalMemory
[PSCustomObject]@{
    TotalGB       = [math]::Round($totalKB / 1MB, 2)
    UsadaGB       = [math]::Round(($totalKB - $libreKB) / 1MB, 2)
    LibreGB       = [math]::Round($libreKB / 1MB, 2)
    PorcentajeUso = [math]::Round(100 - ($libreKB / $totalKB * 100), 1)
} | ConvertTo-Json
"""
    return run_ps(script)


@mcp.tool()
def get_top_processes(count: int = 10, sort_by: str = "Memory") -> str:
    """Lists the processes consuming the most Memory or CPU, with PID, owner and start
    time.

    Use it when the machine feels slow or the user asks what is consuming resources.
    sort_by must be 'Memory' or 'CPU'. Maximum 25 processes.
    """
    if sort_by not in ("Memory", "CPU"):
        return "[ERROR] sort_by debe ser 'Memory' o 'CPU'."

    script = r"""
$n = [int]$Cantidad
$propiedad = if ($Orden -eq 'CPU') { 'CPU' } else { 'WorkingSet64' }
$lista = Get-Process | Sort-Object $propiedad -Descending | Select-Object -First $n | ForEach-Object {
    [PSCustomObject]@{
        Nombre    = $_.Name
        PID       = $_.Id
        MemoriaMB = [math]::Round($_.WorkingSet64 / 1MB, 2)
        CPU_seg   = if ($null -ne $_.CPU) { [math]::Round($_.CPU, 1) } else { $null }
        Inicio    = try { $_.StartTime.ToString('yyyy-MM-dd HH:mm:ss') } catch { $null }
    }
}
ConvertTo-Json -InputObject @($lista) -Depth 3
"""
    return run_ps(script, {"Cantidad": limitar(count, 1, 25), "Orden": sort_by}, strict=False)


@mcp.tool()
def get_services(status: str = "All", name_filter: str = "", count: int = 40) -> str:
    """Lists Windows services with their status, start type and display name.

    status must be 'Running', 'Stopped' or 'All'. name_filter matches both the short
    name and the display name. Use it to find a service when you do not know its exact
    short name.
    """
    if status not in ("Running", "Stopped", "All"):
        return "[ERROR] status debe ser 'Running', 'Stopped' o 'All'."

    script = r"""
$items = Get-Service
if ($Estado -ne 'All') { $items = $items | Where-Object { $_.Status.ToString() -eq $Estado } }
if ($Filtro) { $items = $items | Where-Object { $_.Name -like "*$Filtro*" -or $_.DisplayName -like "*$Filtro*" } }
$lista = $items | Select-Object -First ([int]$Cantidad) | ForEach-Object {
    [PSCustomObject]@{
        Nombre    = $_.Name
        Display   = $_.DisplayName
        Estado    = $_.Status.ToString()
        Inicio    = $_.StartType.ToString()
    }
}
ConvertTo-Json -InputObject @($lista) -Depth 3
"""
    return run_ps(
        script,
        {"Estado": status, "Filtro": name_filter, "Cantidad": limitar(count, 1, 50)},
        strict=False,
    )


@mcp.tool()
def get_installed_software(name_filter: str = "", count: int = 40) -> str:
    """Lists installed software with version, publisher and install date, newest first.

    Reads the uninstall registry keys for both 64 and 32 bit programs and for the
    current user. Use it to check whether something is installed and which version.
    """
    script = r"""
$claves = @(
    'HKLM:\Software\Microsoft\Windows\CurrentVersion\Uninstall\*',
    'HKLM:\Software\Wow6432Node\Microsoft\Windows\CurrentVersion\Uninstall\*',
    'HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\*'
)
$items = Get-ItemProperty $claves -ErrorAction SilentlyContinue | Where-Object { $_.DisplayName }
if ($Filtro) { $items = $items | Where-Object { $_.DisplayName -like "*$Filtro*" } }
$lista = $items | Sort-Object InstallDate -Descending | Select-Object -First ([int]$Cantidad) | ForEach-Object {
    [PSCustomObject]@{
        Nombre    = $_.DisplayName
        Version   = $_.DisplayVersion
        Editor    = $_.Publisher
        Instalado = $_.InstallDate
    }
}
ConvertTo-Json -InputObject @($lista) -Depth 3
"""
    return run_ps(
        script,
        {"Filtro": name_filter, "Cantidad": limitar(count, 1, 50)},
        timeout=60,
        strict=False,
    )


@mcp.tool()
def get_network_config() -> str:
    """Gets the IPv4 configuration of every active adapter: address, gateway and DNS.

    Use it to diagnose connectivity problems or to find out which network the machine
    is on.
    """
    script = r"""
$lista = Get-NetIPConfiguration | Where-Object { $_.IPv4Address } | ForEach-Object {
    [PSCustomObject]@{
        Interfaz = $_.InterfaceAlias
        Estado   = $_.NetAdapter.Status
        IPv4     = ($_.IPv4Address.IPAddress -join ', ')
        Gateway  = ($_.IPv4DefaultGateway.NextHop -join ', ')
        DNS      = (($_.DNSServer | Where-Object AddressFamily -eq 2).ServerAddresses -join ', ')
    }
}
ConvertTo-Json -InputObject @($lista) -Depth 3
"""
    return run_ps(script, strict=False)


@mcp.tool()
def get_pending_updates_summary() -> str:
    """Gets the last installed Windows updates and whether a reboot is pending.

    Use it to check whether the machine is up to date.
    """
    script = r"""
$razones = @()
if (Test-Path 'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Component Based Servicing\RebootPending') { $razones += 'CBS' }
if (Test-Path 'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\WindowsUpdate\Auto Update\RebootRequired') { $razones += 'WindowsUpdate' }
if (Get-ItemProperty 'HKLM:\SYSTEM\CurrentControlSet\Control\Session Manager' -Name PendingFileRenameOperations -ErrorAction SilentlyContinue) { $razones += 'RenombradoPendiente' }

$ultimas = Get-HotFix | Sort-Object InstalledOn -Descending | Select-Object -First 5 | ForEach-Object {
    [PSCustomObject]@{
        Id        = $_.HotFixID
        Tipo      = $_.Description
        Instalado = if ($_.InstalledOn) { $_.InstalledOn.ToString('yyyy-MM-dd') } else { $null }
    }
}

[PSCustomObject]@{
    ReinicioPendiente = ($razones.Count -gt 0)
    Razones           = @($razones)
    UltimasCinco      = @($ultimas)
} | ConvertTo-Json -Depth 4
"""
    return run_ps(script, timeout=60, strict=False)


if __name__ == "__main__":
    print("Servidor de inventario arrancando...", file=sys.stderr)
    mcp.run()
