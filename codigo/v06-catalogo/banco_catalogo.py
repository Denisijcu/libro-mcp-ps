# -*- coding: utf-8 -*-
"""
Capitulo 6: cuanto cuesta un catalogo grande.

Mide dos cosas distintas, y solo la segunda necesita un modelo:

  1. EL COSTE FIJO (instantaneo, sin modelo)
     Cuantos caracteres y tokens aproximados ocupan las descripciones de tus
     herramientas. Ese texto viaja en CADA llamada y vive en el contexto, o
     sea, en la VRAM.

  2. EL COSTE DE ACIERTO (necesita modelo)
     Si el modelo sigue eligiendo bien cuando la herramienta correcta esta
     enterrada entre decenas de distractores plausibles.

Uso:
    python banco_catalogo.py                       # solo el coste fijo
    python banco_catalogo.py --modelo <id>         # tambien el de acierto
    python banco_catalogo.py --modelo <id> --tamanos 4,20,60
"""

import argparse
import json
import os
import sys
import time
from typing import Any, Dict, List

try:
    import requests
except ImportError:
    print("Falta requests. pip install requests", file=sys.stderr)
    sys.exit(1)

BASE_URL = os.getenv("PSMCP_LMSTUDIO_URL", "http://127.0.0.1:1234/v1")
TIMEOUT = 300

# ------------------------------------------------------------------
# Las cuatro herramientas reales del capitulo 3
# ------------------------------------------------------------------

REALES = [
    ("get_date",
     "Gets the current date and time of the Windows machine.", {}),
    ("get_disk_space",
     "Lists every drive letter with its total, used and free space in GB. "
     "Use it to check whether the machine is running out of disk space.", {}),
    ("get_service",
     "Gets the status, start type and display name of a single Windows service. "
     "Use it to check whether a specific service is running. The name is the short "
     "service name, not the display name: for example 'WinDefend', not "
     "'Microsoft Defender Antivirus Service'.",
     {"service_name": ("string", "Short Windows service name, e.g. 'WinDefend'.")}),
    ("get_top_processes",
     "Lists the processes using the most memory right now, with their PID and "
     "memory in MB. Use it when the machine feels slow or the user asks what is "
     "consuming resources. Maximum 20 processes.",
     {"count": ("integer", "How many processes to return. Between 1 and 20.")}),
]

# ------------------------------------------------------------------
# Distractores: nombres REALES del servidor final del libro.
#
# No son relleno aleatorio a proposito. Son herramientas plausibles del
# mismo dominio, que es el caso dificil: el modelo tiene que distinguir
# get_service de get_service_details y de find_suspicious_services.
# Un catalogo de distractores absurdos no mediria nada.
# ------------------------------------------------------------------

DISTRACTORES = [
    ("get_system_info", "Gets a full identity summary of this Windows machine."),
    ("get_memory_usage", "Gets total, used and free physical memory in GB."),
    ("get_uptime", "Gets the Windows system uptime since last boot."),
    ("get_hardware_info", "Gets CPU, motherboard, BIOS and TPM information."),
    ("get_environment_variables", "Lists environment variables of the machine."),
    ("get_installed_updates", "Lists recently installed Windows updates."),
    ("get_pending_reboot", "Checks whether the system has a pending reboot."),
    ("get_process_details", "Gets deep detail of a process: path, hash, signature, parent."),
    ("get_process_tree", "Lists all processes with their parent process."),
    ("get_process_modules", "Lists DLLs loaded by a process."),
    ("find_suspicious_processes", "Finds unsigned processes or ones in user folders."),
    ("get_services", "Lists Windows services filtered by status and name."),
    ("get_service_details", "Gets detail of a service: binary path, account, signature."),
    ("find_suspicious_services", "Finds services with unquoted paths or unsigned binaries."),
    ("start_service", "Starts a Windows service."),
    ("restart_service", "Restarts a Windows service."),
    ("get_ip_config", "Gets IPv4 configuration and DNS servers of all adapters."),
    ("get_network_adapters", "Lists network adapters with MAC, speed and status."),
    ("get_active_connections", "Lists established TCP connections with owning process."),
    ("get_listening_ports", "Lists listening TCP ports with the owning process."),
    ("get_udp_endpoints", "Lists UDP endpoints with the owning process."),
    ("get_arp_table", "Gets the ARP neighbor table."),
    ("get_dns_cache", "Gets the local DNS client cache."),
    ("get_hosts_file", "Reads the hosts file and flags non-default entries."),
    ("get_routes", "Gets the IPv4 routing table."),
    ("get_network_profiles", "Gets network profiles and whether each is Public or Private."),
    ("get_smb_shares", "Lists SMB shares published by this machine."),
    ("get_smb_sessions", "Lists active inbound SMB sessions and open files."),
    ("get_wifi_profiles", "Lists saved Wi-Fi profile names."),
    ("test_connection", "Pings a host and returns response times."),
    ("resolve_dns", "Resolves a DNS name."),
    ("test_port", "Tests whether a TCP port is reachable on a host."),
    ("get_firewall_status", "Gets the state of the three firewall profiles."),
    ("get_firewall_rules", "Lists enabled firewall rules."),
    ("find_risky_firewall_rules", "Finds inbound Allow rules open to any address."),
    ("get_run_keys", "Reads all Run and RunOnce registry keys."),
    ("get_startup_folder", "Lists shortcuts in the Startup folders."),
    ("get_winlogon_config", "Checks Winlogon Shell, Userinit and AppInit_DLLs."),
    ("get_ifeo_hijacks", "Lists Image File Execution Options debuggers."),
    ("get_wmi_persistence", "Lists WMI event subscriptions."),
    ("get_com_hijacks", "Looks for COM hijacking under HKCU CLSID."),
    ("get_bits_jobs", "Lists BITS transfer jobs."),
    ("get_autoruns", "Full autoruns sweep across every automatic start point."),
    ("get_scheduled_tasks", "Lists scheduled tasks filtered by path and state."),
    ("find_suspicious_scheduled_tasks", "Finds tasks that invoke script interpreters."),
    ("find_recent_executables", "Finds executables recently created in user folders."),
    ("get_powershell_history", "Reads the PSReadLine console history file."),
    ("get_shadow_copies", "Lists volume shadow copies."),
    ("get_untrusted_root_certificates", "Lists root CA certificates from unknown vendors."),
    ("get_installed_drivers", "Lists kernel drivers, optionally only unsigned ones."),
    ("get_defender_status", "Gets Microsoft Defender protection status."),
    ("get_defender_exclusions", "Lists Defender exclusions."),
    ("get_defender_threats", "Lists threats detected by Defender."),
    ("get_uac_status", "Gets User Account Control configuration."),
    ("get_bitlocker_status", "Gets BitLocker protection status for all volumes."),
    ("get_credential_protection_status", "Checks LSASS protection and Credential Guard."),
    ("get_rdp_status", "Gets Remote Desktop configuration."),
    ("get_smb1_status", "Checks whether SMBv1 is enabled."),
    ("get_powershell_logging_config", "Checks PowerShell script block logging."),
    ("get_audit_policy", "Displays the local audit policy."),
    ("get_security_posture", "Full security posture summary of the machine."),
    ("get_event_log", "Reads recent events from any Windows log."),
    ("get_failed_logons", "Event 4625: failed logon attempts."),
    ("get_successful_logons", "Event 4624: successful logons."),
    ("get_privilege_escalation_events", "Events 4672, 4673 and 4648."),
    ("get_account_change_events", "Events about account creation and group changes."),
    ("get_process_creation_events", "Event 4688: process creation with command line."),
    ("get_service_install_events", "Event 7045: a new service was installed."),
    ("get_log_clearing_events", "Events 1102 and 104: a log was cleared."),
    ("get_powershell_scriptblock_events", "Event 4104: executed PowerShell script blocks."),
    ("get_defender_events", "Defender operational events."),
    ("list_local_users", "Lists local Windows users."),
    ("get_local_admins", "Lists members of the local Administrators group."),
    ("list_local_groups", "Lists local Windows groups."),
    ("get_group_members", "Lists the members of a local group."),
    ("get_logged_on_users", "Shows currently active user sessions."),
    ("list_directory", "Lists files and folders in a directory."),
    ("read_text_file", "Reads a text file, capped in size."),
    ("search_in_file", "Searches a text file for a regex pattern."),
    ("get_file_info", "Gets size, timestamps, hash, signature and Mark-of-the-Web."),
    ("get_file_hash", "Computes the hash of a file."),
    ("verify_signature", "Verifies the Authenticode signature of a file."),
    ("search_files", "Searches for files by name pattern under a root."),
    ("get_acl", "Gets NTFS owner and permissions of a path."),
    ("get_installed_software", "Lists installed software from the registry."),
    ("get_appx_packages", "Lists installed Microsoft Store packages."),
    ("get_connection_map", "Maps established connections to owning processes."),
    ("explain_remote_endpoint", "Given an IP, finds which processes talk to it."),
    ("suggest_capture_filter", "Builds a tshark display filter."),
    ("find_capture_files", "Lists packet capture files under a folder."),
    ("get_server_config", "Shows this server's security configuration."),
    ("get_audit_trail", "Reads the last entries of the audit log."),
]


def construir_catalogo(total: int) -> List[Dict[str, Any]]:
    """Las 4 reales primero, y despues distractores hasta llegar a 'total'."""
    catalogo = []
    for nombre, descripcion, params in REALES:
        propiedades = {
            k: {"type": t, "description": d} for k, (t, d) in params.items()
        }
        catalogo.append({
            "type": "function",
            "function": {
                "name": nombre,
                "description": descripcion,
                "parameters": {"type": "object", "properties": propiedades},
            },
        })

    for nombre, descripcion in DISTRACTORES[: max(0, total - len(REALES))]:
        catalogo.append({
            "type": "function",
            "function": {
                "name": nombre,
                "description": descripcion,
                "parameters": {"type": "object", "properties": {}},
            },
        })
    return catalogo


def coste_fijo(catalogo: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Cuanto ocupa el catalogo antes de que nadie pregunte nada.

    La estimacion de tokens es deliberadamente burda (4 caracteres por token,
    la regla del pulgar para ingles). No hace falta precision: el orden de
    magnitud es el argumento.
    """
    serializado = json.dumps(catalogo, ensure_ascii=False)
    caracteres = len(serializado)
    return {
        "herramientas": len(catalogo),
        "caracteres": caracteres,
        "tokens_aprox": caracteres // 4,
    }


# Seis casos, elegidos porque cada uno se puede confundir con un distractor
# concreto del catalogo grande.
CASOS = [
    # (id, prompt, esperada, aceptables)
    #
    # 'aceptables' existe por lo que se midio en el capitulo: al ampliar el
    # catalogo aparecen herramientas MEJORES que la esperada. Sin esta lista,
    # el banco mide mi capacidad de anticipar respuestas, no la del modelo de
    # elegir bien.
    ("hora", "Que hora es en esta maquina?", "get_date", set()),
    ("defender", "Esta corriendo Windows Defender?", "get_service",
     {"get_defender_status"}),
    ("disco", "Cuanto espacio libre me queda en los discos?", "get_disk_space",
     {"get_disk_usage"}),
    ("lenta", "La maquina va lentisima, no se que le pasa.", "get_top_processes",
     {"get_memory_usage"}),
    ("spooler", "Mira si el servicio de la cola de impresion esta activo.", "get_service",
     {"get_service_details"}),
    ("sin-sitio", "No me deja guardar archivos, dice que no hay sitio.", "get_disk_space",
     {"get_disk_usage"}),
]

SISTEMA = ("Eres un asistente de administracion de Windows. Usa las herramientas "
           "disponibles cuando hagan falta.")


def preguntar(modelo: str, prompt: str, catalogo: List[Dict[str, Any]]) -> Dict[str, Any]:
    cuerpo = {
        "model": modelo,
        "messages": [{"role": "system", "content": SISTEMA},
                     {"role": "user", "content": prompt}],
        "tools": catalogo,
        "temperature": 0,
    }
    inicio = time.time()
    try:
        r = requests.post(f"{BASE_URL}/chat/completions", json=cuerpo, timeout=TIMEOUT)
        if r.status_code >= 400:
            try:
                detalle = r.json().get("error", {}).get("message", r.text)
            except Exception:
                detalle = r.text[:200]
            return {"error": f"HTTP {r.status_code}: {detalle}",
                    "segundos": round(time.time() - inicio, 1)}
        mensaje = r.json()["choices"][0]["message"]
    except Exception as exc:
        return {"error": f"{type(exc).__name__}: {exc}",
                "segundos": round(time.time() - inicio, 1)}

    llamadas = [c.get("function", {}).get("name") for c in (mensaje.get("tool_calls") or [])]
    return {"llamadas": llamadas, "segundos": round(time.time() - inicio, 1)}


def main() -> int:
    parser = argparse.ArgumentParser(description="Coste de un catalogo grande")
    parser.add_argument("--modelo", help="Modelo en LM Studio. Sin esto solo mide el coste fijo")
    parser.add_argument("--tamanos", default="4,20,60,96",
                        help="Tamanos de catalogo a probar, separados por comas")
    args = parser.parse_args()

    tamanos = [int(t) for t in args.tamanos.split(",") if t.strip()]
    maximo = len(REALES) + len(DISTRACTORES)
    tamanos = [min(t, maximo) for t in tamanos]

    print("=" * 66)
    print(" COSTE FIJO DEL CATALOGO (sin modelo, instantaneo)")
    print("=" * 66)
    print(f"{'Herramientas':>13} {'Caracteres':>12} {'Tokens aprox':>14}   Factor")
    base = None
    for t in tamanos:
        medida = coste_fijo(construir_catalogo(t))
        if base is None:
            base = medida["tokens_aprox"]
        factor = medida["tokens_aprox"] / base if base else 1
        print(f"{medida['herramientas']:>13} {medida['caracteres']:>12} "
              f"{medida['tokens_aprox']:>14}   {factor:.1f}x")

    print("\nEse texto viaja en CADA llamada y ocupa contexto, o sea VRAM.")

    if not args.modelo:
        print("\nPara medir tambien el acierto, vuelve a ejecutar con --modelo <id>.")
        return 0

    print("\n" + "=" * 66)
    print(f" ACIERTO SEGUN EL TAMANO DEL CATALOGO - {args.modelo}")
    print("=" * 66)

    resumen = []
    for t in tamanos:
        catalogo = construir_catalogo(t)
        aciertos = 0
        alternativas = 0
        segundos = 0.0
        print(f"\n--- catalogo de {t} herramientas ---")
        for ident, prompt, esperado, aceptables in CASOS:
            salida = preguntar(args.modelo, prompt, catalogo)
            if "error" in salida:
                print(f"  [ERROR] {ident:<10} {salida['error'][:70]}")
                continue
            llamadas = salida["llamadas"]
            segundos += salida["segundos"]
            visto = llamadas[0] if llamadas else "ninguna"

            if visto == esperado:
                marca, nota = "OK   ", ""
                aciertos += 1
            elif visto in aceptables:
                # Eligio otra herramienta razonable, no se equivoco.
                marca, nota = "ALTERN", "  (alternativa valida)"
                aciertos += 1
                alternativas += 1
            else:
                marca, nota = "FALLO", ""

            print(f"  [{marca}] {ident:<10} {salida['segundos']:>6.1f}s  {visto}{nota}")
        resumen.append((t, aciertos, alternativas, len(CASOS), round(segundos, 1)))

    print("\n" + "=" * 66)
    print(f"{'Herramientas':>13} {'Acierto':>10} {'Alternativas':>14} {'Tiempo total':>14}")
    for t, aciertos, alternativas, total, segundos in resumen:
        print(f"{t:>13} {aciertos:>7}/{total} {alternativas:>13} {segundos:>13.1f}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
