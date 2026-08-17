"""Connection diagnostics. Classifies WHY the database is unreachable.

    python -m app.storage.doctor

TCP failure modes look alike in a traceback but have opposite causes:

    Connection refused    -> reached the host, nothing listening   (server down)
    Connection timed out  -> packets dropped in flight             (firewall/wrong host)

The second is the WSL classic: Postgres runs on Windows, code runs in WSL,
and Windows Defender silently drops traffic from the WSL virtual adapter.
"""
from __future__ import annotations

import os
import platform
import re
import socket
import subprocess
import sys
from pathlib import Path

CONNECT_TIMEOUT = 5


# ---------------------------------------------------------------- helpers
def _c(text: str, code: str) -> str:
    return text if os.environ.get("NO_COLOR") else f"\033[{code}{text}\033[0m"


ok = lambda t: _c("  OK   ", "32m") + t
bad = lambda t: _c(" FAIL  ", "31m") + t
warn = lambda t: _c(" WARN  ", "33m") + t
info = lambda t: _c(" INFO  ", "36m") + t


def is_wsl() -> bool:
    if platform.system() != "Linux":
        return False
    try:
        return "microsoft" in Path("/proc/version").read_text().lower()
    except OSError:
        return False


def windows_host_ip() -> str | None:
    """The Windows host as seen from WSL2 (default gateway)."""
    try:
        out = subprocess.run(["ip", "route", "show", "default"],
                             capture_output=True, text=True, timeout=5).stdout
        m = re.search(r"default via (\S+)", out)
        if m:
            return m.group(1)
    except (OSError, subprocess.SubprocessError):
        pass
    try:
        for line in Path("/etc/resolv.conf").read_text().splitlines():
            if line.startswith("nameserver"):
                return line.split()[1]
    except OSError:
        pass
    return None


def probe_tcp(host: str, port: int, timeout: int = CONNECT_TIMEOUT) -> tuple[str, str]:
    """Return (verdict, detail). verdict in open|refused|timeout|dns|error."""
    try:
        infos = socket.getaddrinfo(host, port, proto=socket.IPPROTO_TCP)
    except socket.gaierror as e:
        return "dns", f"cannot resolve {host!r}: {e}"
    fam, typ, proto, _, addr = infos[0]
    s = socket.socket(fam, typ, proto)
    s.settimeout(timeout)
    try:
        s.connect(addr)
        return "open", f"{addr[0]}:{addr[1]} accepted the connection"
    except socket.timeout:
        return "timeout", f"{addr[0]}:{addr[1]} did not answer in {timeout}s"
    except ConnectionRefusedError:
        return "refused", f"{addr[0]}:{addr[1]} refused the connection"
    except OSError as e:
        return "error", f"{addr[0]}:{addr[1]} {e}"
    finally:
        s.close()


def listening_locally(port: int) -> bool:
    for proc in ("/proc/net/tcp", "/proc/net/tcp6"):
        try:
            for line in Path(proc).read_text().splitlines()[1:]:
                f = line.split()
                if len(f) > 3 and f[3] == "0A" and int(f[1].split(":")[1], 16) == port:
                    return True
        except OSError:
            pass
    return False


def local_pg_running() -> bool:
    try:
        out = subprocess.run(["bash", "-lc", "ps -eo comm= | grep -c '^postgres$'"],
                             capture_output=True, text=True, timeout=5).stdout
        return int(out.strip() or 0) > 0
    except (OSError, ValueError, subprocess.SubprocessError):
        return False


# ---------------------------------------------------------------- report
def main() -> int:
    print("\n" + "=" * 68)
    print("  DATABASE CONNECTION DOCTOR")
    print("=" * 68 + "\n")

    try:
        from ..core.config import get_settings
    except Exception as e:                                   # pragma: no cover
        print(bad(f"cannot import settings: {e}"))
        print(info("run this from the backend/ directory"))
        return 2

    s = get_settings()
    host, port = s.postgis_host, s.postgis_port

    env_file = Path(".env")
    print(info(f"target        {s.database_url_safe}"))
    print(info(f"env file      {env_file.resolve() if env_file.exists() else 'not found (using defaults/exported vars)'}"))
    wsl = is_wsl()
    print(info(f"platform      {'WSL' if wsl else platform.system()}"))
    if s.postgis_password == "2415":
        print(warn("password is the hardcoded default '2415' - set POSTGIS_PASSWORD"))
    print()

    # ---- 1. TCP reachability
    print("-" * 68)
    print(" 1. TCP reachability")
    print("-" * 68)
    verdict, detail = probe_tcp(host, port)
    hint_target = None

    if verdict == "open":
        print(ok(detail))
    elif verdict == "dns":
        print(bad(detail))
    elif verdict == "refused":
        print(bad(detail))
        print(info("nothing is listening on that port - the server is down"))
    elif verdict == "timeout":
        print(bad(detail))
        print(info("packets are being DROPPED, not rejected"))
        print(info("a stopped local server refuses instantly; this is a firewall"))
        print(info("or the wrong host - the address you dialled is not this machine"))
    else:
        print(bad(detail))
    print()

    # ---- 2. Local server
    print("-" * 68)
    print(" 2. Local PostgreSQL")
    print("-" * 68)
    running = local_pg_running()
    listening = listening_locally(port)
    print((ok if running else warn)(
        f"postgres process in this Linux namespace: {'yes' if running else 'no'}"))
    print((ok if listening else warn)(
        f"something listening on port {port} here:    {'yes' if listening else 'no'}"))
    if not running and not listening:
        print(info("no local server - so 'localhost' must mean somewhere else"))
    if listening and verdict in ("timeout", "refused"):
        print()
        print(_c("  >>> CONTRADICTION.", "33;1m"),
              f"Port {port} IS open on this machine,")
        print(f"      but connecting to '{host}' {verdict}s. You are dialling")
        print("      a different machine than the one running Postgres.")
        print(info("try POSTGIS_HOST=127.0.0.1 (forces IPv4 loopback)"))
    print()

    # ---- 3. WSL cross-boundary probes
    if wsl and verdict != "open":
        print("-" * 68)
        print(" 3. WSL -> Windows host")
        print("-" * 68)
        gw = windows_host_ip()
        if gw:
            v2, d2 = probe_tcp(gw, port)
            print(info(f"Windows host appears to be {gw}"))
            if v2 == "open":
                print(ok(f"port {port} IS reachable at {gw}"))
                print()
                print(_c("  >>> FOUND IT.", "32;1m"),
                      "Postgres runs on Windows, not in WSL.")
                hint_target = gw
            elif v2 == "timeout":
                print(bad(f"{gw}:{port} also times out"))
                print(info("Windows Defender is dropping traffic from the WSL adapter"))
            else:
                print(warn(f"{gw}:{port} -> {v2}"))
        else:
            print(warn("could not determine the Windows host IP"))
        print()

    # ---- 4. Driver-level
    print("-" * 68)
    print(" 4. PostgreSQL handshake")
    print("-" * 68)
    if verdict != "open":
        print(info("skipped - TCP never established"))
    else:
        try:
            import psycopg2
            conn = psycopg2.connect(
                host=host, port=port, dbname=s.postgis_db, user=s.postgis_user,
                password=s.postgis_password, connect_timeout=CONNECT_TIMEOUT)
            with conn.cursor() as cur:
                cur.execute("SELECT version()")
                print(ok(cur.fetchone()[0].split(",")[0]))
                try:
                    cur.execute("SELECT postgis_version()")
                    print(ok(f"PostGIS {cur.fetchone()[0]}"))
                except Exception:
                    conn.rollback()
                    print(bad("PostGIS extension NOT installed in this database"))
                    print(info("fix: CREATE EXTENSION postgis;"))
            conn.close()
            print()
            print(_c("  Database is healthy.", "32;1m"),
                  "Next: python -m app.storage.bootstrap check")
            print()
            return 0
        except Exception as e:
            msg = str(e).strip().splitlines()[0]
            print(bad(msg))
            low = msg.lower()
            if "password" in low or "authentication" in low:
                print(info("TCP works, credentials do not - fix POSTGIS_PASSWORD in .env"))
            elif "does not exist" in low:
                print(info(f'fix: createdb {s.postgis_db}'))
    print()

    # ---- 5. Prescription
    print("=" * 68)
    print("  HOW TO FIX")
    print("=" * 68 + "\n")

    if hint_target:
        print(f"Postgres is on Windows at {hint_target}, but you dialled '{host}'.\n")
        print(f"  echo 'POSTGIS_HOST={hint_target}' >> .env\n")
        print("That gateway IP changes on reboot unless you are on WSL mirrored")
        print("networking. The durable fix is to run Postgres inside WSL:\n")
        print("  docker compose up -d db          # if you use the compose file")
        print("  # or")
        print("  sudo apt install postgresql postgresql-17-postgis-3")
        print("  sudo service postgresql start\n")
    elif verdict == "timeout":
        print("Packets are dropped. In order of likelihood:\n")
        print("1. Postgres is on Windows and the firewall blocks WSL.")
        print("   In an ADMIN PowerShell on Windows:\n")
        print('   New-NetFirewallRule -DisplayName "PostgreSQL WSL" -Direction Inbound `')
        print('     -LocalPort 5432 -Protocol TCP -Action Allow')
        print("   Also set in postgresql.conf:  listen_addresses = '*'")
        print("   and add to pg_hba.conf:       host all all 172.16.0.0/12 scram-sha-256\n")
        print("2. Simpler: run Postgres inside WSL so no firewall is involved.\n")
        print("   docker compose up -d db\n")
        print("3. A VPN is capturing the route. Disconnect and retry.\n")
    elif verdict == "refused":
        print("The port is closed. Start the server:\n")
        print("  sudo service postgresql start          # apt install")
        print("  docker compose up -d db                # docker\n")
        print("Then confirm:  pg_isready -h localhost -p %d\n" % port)
    elif verdict == "dns":
        print(f"The hostname '{host}' does not resolve. Use 'localhost' or an IP.\n")

    print("Re-run this doctor after each change:  python -m app.storage.doctor\n")
    return 1


if __name__ == "__main__":
    sys.exit(main())
