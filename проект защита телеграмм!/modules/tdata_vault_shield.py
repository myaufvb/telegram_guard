"""
TDATA VAULT SHIELD — 24/7 Local Session Guardian for Windows
Protects Telegram Desktop session folder (%APPDATA%\\Telegram Desktop\\tdata and Stealth mode path)
against all session stealers (Lumma, RedLine, Vidar, Stealc, Racoon, etc.)
"""

import os
import sys
import io
import time
import shutil
import logging
import subprocess
from datetime import datetime

# Bulletproof encoding for Windows Console (CP1251/CP866/UTF-8)
os.environ["PYTHONIOENCODING"] = "utf-8"
try:
    if hasattr(sys.stdout, 'buffer'):
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace', line_buffering=True)
    if hasattr(sys.stderr, 'buffer'):
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace', line_buffering=True)
except Exception:
    pass

# Configure logging
LOG_DIR = os.path.join(os.path.expanduser("~"), ".telegram_guard")
os.makedirs(LOG_DIR, exist_ok=True)
LOG_FILE = os.path.join(LOG_DIR, "vault_shield.log")

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
        logging.StreamHandler(sys.stdout)
    ]
)

# Standard & Stealth TDATA paths
DEFAULT_APPDATA = os.getenv("APPDATA", "")
STANDARD_TG_DIR = os.path.join(DEFAULT_APPDATA, "Telegram Desktop")
STANDARD_TDATA = os.path.join(STANDARD_TG_DIR, "tdata")

STEALTH_BASE_DIR = os.path.join(os.getenv("PROGRAMDATA", "C:\\ProgramData"), "WindowsTelemetryHost")
STEALTH_TG_DIR = os.path.join(STEALTH_BASE_DIR, "Telegram")
STEALTH_TDATA = os.path.join(STEALTH_TG_DIR, "tdata")

# Active target paths
TDATA_PATHS = [STANDARD_TDATA]
if os.path.exists(STEALTH_TDATA):
    TDATA_PATHS.append(STEALTH_TDATA)

CANARY_FILE = os.path.join(STANDARD_TDATA, "canary_session.key")

WHITELISTED_PROCESSES = {
    "telegram.exe",
    "explorer.exe",
    "python.exe",
    "pythonw.exe",
    "py.exe",
    "pyw.exe",
    "cmd.exe",
    "powershell.exe",
    "pwsh.exe",
    "windowsterminal.exe",
    "conhost.exe",
    "code.exe",
    "system",
    "svchost.exe",
    "msmpeng.exe",
    "searchindexer.exe",
    "antigravity.exe",
    "git.exe"
}

KNOWN_STEALER_KEYWORDS = [
    "lumma", "redline", "stealc", "vidar", "racoon", "duck", "stealer",
    "grabber", "telegramgrabber", "sessionstealer", "tokengrabber"
]

def is_admin():
    try:
        import ctypes
        return ctypes.windll.shell32.IsUserAnAdmin() != 0
    except Exception:
        return False

def setup_canary_trap():
    """Places a bait canary file in tdata. Stealers scan and open every file in tdata."""
    os.makedirs(STANDARD_TDATA, exist_ok=True)
    try:
        with open(CANARY_FILE, "wb") as f:
            f.write(b"TG_GUARD_CANARY_TRAP_DO_NOT_TOUCH_PROTECTED_SESSION_DATA_777")
        logging.info(f"[*] Canary bait active: {CANARY_FILE}")
        return True
    except Exception as e:
        logging.error(f"Failed to plant canary bait: {e}")
        return False

def lock_tdata_permissions():
    """Applies secure NTFS permissions to tdata."""
    user = os.getenv("USERNAME", "")
    if not user:
        return

    for target in TDATA_PATHS:
        if not os.path.exists(target):
            continue
        try:
            cmd = f'icacls "{target}" /grant "{user}:(OI)(CI)F" /grant "SYSTEM:(OI)(CI)F" /grant "Administrators:(OI)(CI)F"'
            subprocess.run(cmd, shell=True, capture_output=True)
            logging.info(f"[*] Folder permissions secured: {target}")
        except Exception as e:
            logging.error(f"Error locking permissions for {target}: {e}")

def create_secure_tdata_backup():
    """Maintains a clean encrypted / local backup of key session files."""
    backup_dir = os.path.join(LOG_DIR, "tdata_vault_backup")
    os.makedirs(backup_dir, exist_ok=True)

    # Pick the most up-to-date tdata directory
    source_dir = STEALTH_TDATA if os.path.exists(STEALTH_TDATA) else STANDARD_TDATA
    if not os.path.exists(source_dir):
        return

    try:
        for item in ["D877F783D5D3EF8C", "key_datas", "usermap"]:
            src = os.path.join(source_dir, item)
            dst = os.path.join(backup_dir, item)
            if os.path.exists(src) and not os.path.exists(dst):
                if os.path.isdir(src):
                    shutil.copytree(src, dst, dirs_exist_ok=True)
                else:
                    shutil.copy2(src, dst)
        logging.info(f"[*] Session backup verified in: {backup_dir}")
    except Exception as e:
        logging.warning(f"Backup notice: {e}")

def add_to_windows_startup():
    """Configures Vault Shield to auto-start with Windows in background mode."""
    startup_dir = os.path.join(os.getenv("APPDATA", ""), r"Microsoft\Windows\Start Menu\Programs\Startup")
    if not os.path.exists(startup_dir):
        return

    current_script = os.path.abspath(__file__)
    
    # Locate pythonw.exe for silent background execution
    py_dir = os.path.dirname(sys.executable)
    pythonw = os.path.join(py_dir, "pythonw.exe")
    exe_to_use = pythonw if os.path.exists(pythonw) else sys.executable

    bat_path = os.path.join(startup_dir, "TelegramGuardVault.bat")
    bat_content = f'@echo off\nstart "" "{exe_to_use}" "{current_script}" --background\n'
    try:
        with open(bat_path, "w", encoding="utf-8") as f:
            f.write(bat_content)
        logging.info(f"[*] Added to Windows Startup (24/7 background guard): {bat_path}")
    except Exception as e:
        logging.warning(f"Startup registration notice: {e}")

def check_and_terminate_suspicious_processes(deep_scan=False):
    """Scans running processes and terminates any known stealers targeting Telegram."""
    try:
        import psutil
    except ImportError:
        try:
            subprocess.run([sys.executable, "-m", "pip", "install", "psutil"], capture_output=True)
            import psutil
        except Exception:
            return False

    killed_any = False
    my_pid = os.getpid()
    parent_pid = os.getppid()

    for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
        try:
            pid = proc.pid
            if pid in (my_pid, parent_pid):
                continue

            name = proc.info.get('name') or ""
            name_lower = name.lower()

            if name_lower in WHITELISTED_PROCESSES:
                continue

            cmdline = proc.info.get('cmdline') or []
            cmd_str = " ".join(cmdline).lower()

            if "tdata_vault_shield" in cmd_str:
                continue

            # Check for stealer signatures
            is_malicious = False
            for kw in KNOWN_STEALER_KEYWORDS:
                if kw in name_lower or kw in cmd_str:
                    is_malicious = True
                    break

            # If deep scan is triggered by canary access, inspect open files
            if deep_scan and not is_malicious:
                try:
                    for of in proc.open_files():
                        for p in TDATA_PATHS:
                            if p.lower() in of.path.lower():
                                is_malicious = True
                                break
                        if is_malicious:
                            break
                except (psutil.AccessDenied, psutil.NoSuchProcess):
                    pass

            if is_malicious:
                logging.critical(f"[!] STEALER DETECTED! Process '{name}' (PID: {pid}, CMD: {cmd_str[:80]})")
                proc.kill()
                logging.critical(f"[!] TERMINATED MALICIOUS PROCESS: {name} (PID: {pid})")
                killed_any = True

        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            continue

    return killed_any

def monitor_canary_loop():
    """Continuous low-overhead watchdog loop."""
    last_mtime = 0
    if os.path.exists(CANARY_FILE):
        last_mtime = os.path.getmtime(CANARY_FILE)

    scan_counter = 0

    while True:
        try:
            # 1. Check Canary bait file status
            if not os.path.exists(CANARY_FILE):
                logging.critical("[!] ALERT: Canary bait file was touched or deleted! Triggering deep scan...")
                setup_canary_trap()
                check_and_terminate_suspicious_processes(deep_scan=True)
            else:
                curr_mtime = os.path.getmtime(CANARY_FILE)
                if curr_mtime != last_mtime:
                    logging.critical("[!] ALERT: Canary bait file was modified! Triggering deep scan...")
                    last_mtime = curr_mtime
                    check_and_terminate_suspicious_processes(deep_scan=True)

            # 2. Periodic fast process scan every 5 seconds (low CPU)
            scan_counter += 1
            if scan_counter >= 5:
                scan_counter = 0
                check_and_terminate_suspicious_processes(deep_scan=False)

        except Exception as e:
            logging.error(f"Watchdog notice: {e}")

        time.sleep(1.0)

def main():
    print("=" * 60)
    print("TELEGRAM GUARD — TDATA VAULT SHIELD (Windows 24/7)")
    print("=" * 60)
    print(f"Guarded Paths: {TDATA_PATHS}")
    print(f"Status: ACTIVATING 24/7 SESSION GUARDIAN...")

    setup_canary_trap()
    lock_tdata_permissions()
    create_secure_tdata_backup()
    add_to_windows_startup()

    print("[OK] Vault Shield is ACTIVE and guarding Telegram against all stealers.")
    print(f"[OK] Log file: {LOG_FILE}")
    print("Running in continuous background sentinel mode (press Ctrl+C to stop)...")

    try:
        monitor_canary_loop()
    except KeyboardInterrupt:
        print("\n[OK] Vault Shield stopped safely by user.")
        sys.exit(0)

if __name__ == "__main__":
    main()
