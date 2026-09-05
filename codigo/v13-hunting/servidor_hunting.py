# -*- coding: utf-8 -*-
"""
Capitulo 13: herramientas de hunting. Todas de nivel read.

Buscan indicadores, no verdades. Cada una devuelve hallazgos con su motivo, y
es el analista (o el modelo, con el usuario delante) quien decide si un hallazgo
es un problema o un falso positivo.

Regla que atraviesa el capitulo: una herramienta de hunting NUNCA puede
devolver "no hay nada" cuando lo que ocurrio es "no pude mirar". Por eso cada
funcion informa de donde busco, no solo de lo que encontro.
"""

import sys

from mcp.server.fastmcp import FastMCP

from ejecutor import limitar, run_ps

mcp = FastMCP("PowerShell Hunting")

# Rutas donde un ejecutable legitimo rara vez vive. Se resuelven con .NET,
# NUNCA con $env: (capitulo 12, trampa 1).
RUTAS_USUARIO_PS = r"""
$dirs = @(
    [Environment]::GetFolderPath('LocalApplicationData') + '\Temp',
    [Environment]::GetFolderPath('ApplicationData'),
    [Environment]::GetFolderPath('UserProfile') + '\Downloads',
    'C:\Users\Public',
    'C:\ProgramData',
    'C:\PerfLogs',
    $env:SystemRoot + '\Temp'
) | Where-Object { $_ -and (Test-Path $_) } | Select-Object -Unique
"""


@mcp.tool()
def find_suspicious_processes() -> str:
    """Finds running processes that are unsigned, run from user-writable folders, or
    have suspicious command lines (encoded commands, download cradles, hidden windows).

    Returns findings with the reason each one was flagged, plus how many processes were
    examined and how many could not be checked. A clean machine WILL produce findings:
    unsigned does not mean malicious. Compare against what the user knows they installed.
    """
    script = RUTAS_USUARIO_PS + r"""
$patron = '(?i)(-enc\s|-encodedcommand|frombase64string|invoke-expression|\biex\b|' +
          'downloadstring|downloadfile|-w\s+hidden|-windowstyle\s+hidden|' +
          'certutil\s+-urlcache|bitsadmin\s+/transfer)'

$cacheFirma = @{}
$hallazgos = @()
$examinados = 0
$sinRuta = 0

foreach ($p in Get-CimInstance Win32_Process) {
    $examinados++
    $ruta = $p.ExecutablePath
    $marcas = @()

    if (-not $ruta) {
        # Procesos protegidos del sistema y similares: no es un hallazgo,
        # es una limitacion. Se cuenta aparte para no ocultarla.
        $sinRuta++
    } else {
        foreach ($d in $dirs) {
            if ($ruta.ToLower().StartsWith($d.ToLower())) { $marcas += "RutaUsuario[$d]" }
        }
        if (-not $cacheFirma.ContainsKey($ruta)) {
            $cacheFirma[$ruta] = Get-AuthenticodeSignature $ruta
        }
        $sig = $cacheFirma[$ruta]
        if ($sig.Status -ne 'Valid') { $marcas += "Firma[$($sig.Status)]" }
    }

    if ($p.CommandLine -and $p.CommandLine -match $patron) { $marcas += 'CommandLineSospechosa' }

    if ($marcas.Count -gt 0) {
        $firmante = $null
        if ($ruta -and $cacheFirma[$ruta].SignerCertificate) {
            $firmante = $cacheFirma[$ruta].SignerCertificate.Subject
        }
        $hallazgos += [PSCustomObject]@{
            Nombre      = $p.Name
            PID         = $p.ProcessId
            Ruta        = $ruta
            PID_Padre   = $p.ParentProcessId
            Firmante    = $firmante
            Inicio      = if ($p.CreationDate) { $p.CreationDate.ToString('yyyy-MM-dd HH:mm:ss') } else { $null }
            CommandLine = $p.CommandLine
            Hallazgos   = ($marcas -join ' | ')
        }
    }
}

[PSCustomObject]@{
    Examinados        = $examinados
    SinRutaAccesible  = $sinRuta
    ConHallazgos      = $hallazgos.Count
    Hallazgos         = @($hallazgos)
    Nota              = 'Sin firma no significa malicioso. Herramientas de desarrollo, bases de datos y binarios compilados en local suelen aparecer aqui.'
} | ConvertTo-Json -Depth 4
"""
    return run_ps(script, timeout=180, strict=False)


@mcp.tool()
def get_autoruns() -> str:
    """Lists every automatic start point: Run and RunOnce registry keys (machine and
    user, 32 and 64 bit), startup folders, Winlogon Shell and Userinit, and Image File
    Execution Options debuggers.

    Flags entries whose value invokes a script interpreter or points to a user-writable
    folder. Reports which locations were checked, so an empty result can be told apart
    from a failed read.
    """
    script = r"""
$patron = '(?i)(powershell|pwsh|cmd\.exe|wscript|cscript|mshta|rundll32|regsvr32|' +
          'certutil|bitsadmin|curl\s|-enc\b|frombase64|\\temp\\|\\appdata\\|\\public\\|' +
          '\.vbs|\.bat|\.ps1|\.js\b|\.hta)'

$claves = @(
    'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Run',
    'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\RunOnce',
    'HKLM:\SOFTWARE\Wow6432Node\Microsoft\Windows\CurrentVersion\Run',
    'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Policies\Explorer\Run',
    'HKCU:\SOFTWARE\Microsoft\Windows\CurrentVersion\Run',
    'HKCU:\SOFTWARE\Microsoft\Windows\CurrentVersion\RunOnce',
    'HKCU:\SOFTWARE\Microsoft\Windows\CurrentVersion\Policies\Explorer\Run'
)

$entradas = @()
$revisadas = @()
$inaccesibles = @()

foreach ($k in $claves) {
    if (-not (Test-Path $k)) { continue }
    try {
        $props = Get-ItemProperty -Path $k -ErrorAction Stop
        $revisadas += $k
        foreach ($x in $props.PSObject.Properties) {
            if ($x.Name -like 'PS*') { continue }
            $valor = [string]$x.Value
            $entradas += [PSCustomObject]@{
                Origen     = 'RunKey'
                Ubicacion  = $k
                Nombre     = $x.Name
                Valor      = $valor
                Sospechoso = ($valor -match $patron)
            }
        }
    } catch {
        $inaccesibles += $k
    }
}

# Carpetas de inicio: se resuelven con .NET, no con $env: (capitulo 12).
$carpetas = @(
    [Environment]::GetFolderPath('Startup'),
    [Environment]::GetFolderPath('CommonStartup')
) | Where-Object { $_ }

foreach ($c in $carpetas) {
    if (-not (Test-Path $c)) { $inaccesibles += $c; continue }
    $revisadas += $c
    foreach ($f in Get-ChildItem -Path $c -File -ErrorAction SilentlyContinue) {
        $entradas += [PSCustomObject]@{
            Origen     = 'CarpetaInicio'
            Ubicacion  = $c
            Nombre     = $f.Name
            Valor      = $f.FullName
            Sospechoso = ($f.FullName -match $patron)
        }
    }
}

# Winlogon: Shell deberia ser explorer.exe y Userinit el de system32.
$wl = Get-ItemProperty 'HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Winlogon' -ErrorAction SilentlyContinue
if ($wl) {
    $revisadas += 'Winlogon'
    $entradas += [PSCustomObject]@{
        Origen = 'Winlogon'; Ubicacion = 'HKLM:\...\Winlogon'; Nombre = 'Shell'
        Valor = $wl.Shell; Sospechoso = ($wl.Shell -ne 'explorer.exe')
    }
    $entradas += [PSCustomObject]@{
        Origen = 'Winlogon'; Ubicacion = 'HKLM:\...\Winlogon'; Nombre = 'Userinit'
        Valor = $wl.Userinit
        Sospechoso = ($wl.Userinit -notmatch '(?i)^C:\\Windows\\system32\\userinit\.exe,?$')
    }
}

# IFEO: un Debugger aqui secuestra la ejecucion de un programa.
$ifeo = 'HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Image File Execution Options'
if (Test-Path $ifeo) {
    $revisadas += $ifeo
    foreach ($k in Get-ChildItem $ifeo -ErrorAction SilentlyContinue) {
        $d = (Get-ItemProperty $k.PSPath -ErrorAction SilentlyContinue).Debugger
        if ($d) {
            $entradas += [PSCustomObject]@{
                Origen = 'IFEO'; Ubicacion = $ifeo; Nombre = $k.PSChildName
                Valor = $d; Sospechoso = $true
            }
        }
    }
}

[PSCustomObject]@{
    UbicacionesRevisadas = @($revisadas)
    UbicacionesFallidas  = @($inaccesibles)
    Total                = $entradas.Count
    Sospechosas          = @($entradas | Where-Object Sospechoso).Count
    Entradas             = @($entradas)
} | ConvertTo-Json -Depth 4
"""
    return run_ps(script, timeout=120, strict=False)


@mcp.tool()
def get_active_connections(only_suspicious: bool = False, count: int = 40) -> str:
    """Lists established TCP connections with the owning process name and path.

    Flags connections to ports commonly used by remote access tools and C2 frameworks.
    Set only_suspicious to hide ordinary web traffic. Private-network destinations are
    marked, because a connection to 192.168.x.x is a very different finding from one to
    a public address.
    """
    script = r"""
$alto  = @(4444,4445,1337,31337,5555,6666,6667,7777,9001,9050,9051,1080,2222,3333,53413)
$medio = @(8080,8443,8888,4443,9000,9999,5900,5901,23,21,3389)

$procesos = @{}
foreach ($p in Get-CimInstance Win32_Process) { $procesos[[int]$p.ProcessId] = $p }

$soloSospechosas = ($SoloSospechosas -eq '1')
$lista = @()
$total = 0

foreach ($c in Get-NetTCPConnection -State Established -ErrorAction SilentlyContinue) {
    $total++
    $nivel = 'INFO'
    if ($medio -contains $c.RemotePort) { $nivel = 'MEDIO' }
    if ($alto  -contains $c.RemotePort) { $nivel = 'ALTO' }
    if ($soloSospechosas -and $nivel -eq 'INFO') { continue }

    $proc = $procesos[[int]$c.OwningProcess]
    $privada = $c.RemoteAddress -match '^(10\.|192\.168\.|172\.(1[6-9]|2[0-9]|3[01])\.|127\.|::1|fe80)'

    $lista += [PSCustomObject]@{
        Remoto       = "$($c.RemoteAddress):$($c.RemotePort)"
        PuertoRemoto = $c.RemotePort
        Nivel        = $nivel
        RedPrivada   = [bool]$privada
        PID          = $c.OwningProcess
        Proceso      = if ($proc) { $proc.Name } else { $null }
        Ruta         = if ($proc) { $proc.ExecutablePath } else { $null }
    }
}

$orden = $lista | Sort-Object @{E={ switch ($_.Nivel) { 'ALTO' {0} 'MEDIO' {1} default {2} } }}, PuertoRemoto

[PSCustomObject]@{
    TotalEstablecidas = $total
    Devueltas         = [Math]::Min($orden.Count, [int]$Cantidad)
    Conexiones        = @($orden | Select-Object -First ([int]$Cantidad))
    Nota              = 'Los puertos 8080 y 8443 son habituales en desarrollo local. Un ALTO hacia una IP publica es lo que merece atencion.'
} | ConvertTo-Json -Depth 4
"""
    return run_ps(
        script,
        {"SoloSospechosas": only_suspicious, "Cantidad": limitar(count, 1, 100)},
        timeout=90,
        strict=False,
    )


@mcp.tool()
def get_listening_ports(count: int = 40) -> str:
    """Lists listening TCP ports with the owning process, marking which ones are bound to
    all interfaces (0.0.0.0) and therefore reachable from the network.

    Use it to find services accidentally exposed to the local network.
    """
    script = r"""
$procesos = @{}
foreach ($p in Get-CimInstance Win32_Process) { $procesos[[int]$p.ProcessId] = $p }

$lista = Get-NetTCPConnection -State Listen -ErrorAction SilentlyContinue |
    Sort-Object LocalPort | Select-Object -First ([int]$Cantidad) | ForEach-Object {
        $proc = $procesos[[int]$_.OwningProcess]
        [PSCustomObject]@{
            Puerto            = $_.LocalPort
            Direccion         = $_.LocalAddress
            ExpuestoALaRed    = ($_.LocalAddress -eq '0.0.0.0' -or $_.LocalAddress -eq '::')
            PID               = $_.OwningProcess
            Proceso           = if ($proc) { $proc.Name } else { $null }
            Ruta              = if ($proc) { $proc.ExecutablePath } else { $null }
        }
    }
ConvertTo-Json -InputObject @($lista) -Depth 3
"""
    return run_ps(script, {"Cantidad": limitar(count, 1, 100)}, timeout=90, strict=False)


@mcp.tool()
def find_suspicious_scheduled_tasks() -> str:
    """Finds non-Microsoft scheduled tasks whose action invokes a script interpreter, a
    living-off-the-land binary, an encoded command, or something in a user-writable
    folder.

    Includes when each task last ran and when it runs next.
    """
    script = r"""
$patron = '(?i)(powershell|pwsh|cmd\.exe|wscript|cscript|mshta|rundll32|regsvr32|' +
          'certutil|bitsadmin|curl\s|-enc\b|frombase64|\\temp\\|\\appdata\\|\\public\\|' +
          '\.vbs|\.ps1|\.bat|\.js\b|\.hta)'

$hallazgos = @()
$revisadas = 0

foreach ($t in Get-ScheduledTask -ErrorAction SilentlyContinue) {
    if ($t.TaskPath -like '\Microsoft\*') { continue }
    $revisadas++
    foreach ($a in $t.Actions) {
        $linea = "$($a.Execute) $($a.Arguments)".Trim()
        if ($linea -match $patron) {
            $info = try { Get-ScheduledTaskInfo -TaskName $t.TaskName -TaskPath $t.TaskPath -ErrorAction Stop } catch { $null }
            $hallazgos += [PSCustomObject]@{
                Tarea            = $t.TaskName
                Ruta             = $t.TaskPath
                Estado           = $t.State.ToString()
                Autor            = $t.Author
                Usuario          = $t.Principal.UserId
                NivelEjecucion   = $t.Principal.RunLevel.ToString()
                Accion           = $linea
                UltimaEjecucion  = if ($info -and $info.LastRunTime) { $info.LastRunTime.ToString('yyyy-MM-dd HH:mm:ss') } else { $null }
                ProximaEjecucion = if ($info -and $info.NextRunTime) { $info.NextRunTime.ToString('yyyy-MM-dd HH:mm:ss') } else { $null }
            }
        }
    }
}

[PSCustomObject]@{
    TareasNoMicrosoftRevisadas = $revisadas
    ConHallazgos               = $hallazgos.Count
    Tareas                     = @($hallazgos)
} | ConvertTo-Json -Depth 4
"""
    return run_ps(script, timeout=120, strict=False)


@mcp.tool()
def get_defender_exclusions() -> str:
    """Lists Microsoft Defender exclusions and whether real-time protection is disabled.

    Attackers add exclusions to hide their payloads, so any exclusion the user did not
    create themselves is a strong indicator. This tool only reads: the server has no
    tool to create exclusions or to disable Defender.
    """
    script = r"""
$p = Get-MpPreference
$s = Get-MpComputerStatus
[PSCustomObject]@{
    RutasExcluidas       = @($p.ExclusionPath)
    ProcesosExcluidos    = @($p.ExclusionProcess)
    ExtensionesExcluidas = @($p.ExclusionExtension)
    TotalExclusiones     = (@($p.ExclusionPath).Count + @($p.ExclusionProcess).Count + @($p.ExclusionExtension).Count)
    TiempoRealActivo     = $s.RealTimeProtectionEnabled
    TamperProtection     = $s.IsTamperProtected
    EdadFirmasDias       = $s.AntivirusSignatureAge
    Nota                 = 'Cualquier exclusion que el usuario no reconozca, y sobre todo C:\ o %TEMP% o powershell.exe, es indicador fuerte de compromiso.'
} | ConvertTo-Json -Depth 3
"""
    return run_ps(script, timeout=60, strict=False)


@mcp.tool()
def get_log_clearing_events(days: int = 30) -> str:
    """Looks for events 1102 (Security log cleared) and 104 (other log cleared).

    Any result here is a red flag: clearing logs is almost never routine maintenance.
    """
    script = r"""
$dias = [int]$Dias
$inicio = (Get-Date).AddDays(-$dias)
$eventos = @()
$revisados = @()
$fallidos = @()

foreach ($cfg in @(@{L='Security';I=1102}, @{L='System';I=104})) {
    try {
        $ev = Get-WinEvent -FilterHashtable @{ LogName=$cfg.L; Id=$cfg.I; StartTime=$inicio } -MaxEvents 20 -ErrorAction Stop
        $revisados += $cfg.L
        foreach ($e in $ev) {
            $eventos += [PSCustomObject]@{
                Log  = $cfg.L
                Id   = $e.Id
                Hora = $e.TimeCreated.ToString('yyyy-MM-dd HH:mm:ss')
                Mensaje = ($e.Message -replace '\s+', ' ')
            }
        }
    } catch [Exception] {
        # "No events were found" tambien cae aqui: hay que distinguirlo de
        # "no tengo permiso para leer este log".
        if ($_.Exception.Message -match 'No events were found') {
            $revisados += $cfg.L
        } else {
            $fallidos += "$($cfg.L): $($_.Exception.Message)"
        }
    }
}

[PSCustomObject]@{
    VentanaDias    = $dias
    LogsRevisados  = @($revisados)
    LogsFallidos   = @($fallidos)
    Total          = $eventos.Count
    Eventos        = @($eventos)
    Nota           = 'Si LogsFallidos no esta vacio, el resultado NO significa que no haya nada: significa que no se pudo mirar. El log de seguridad requiere privilegios de administrador.'
} | ConvertTo-Json -Depth 4
"""
    return run_ps(script, {"Dias": limitar(days, 1, 365)}, timeout=120, strict=False)


if __name__ == "__main__":
    print("Servidor de hunting arrancando...", file=sys.stderr)
    mcp.run()
