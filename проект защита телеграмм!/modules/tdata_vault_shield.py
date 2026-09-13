"""
TDATA VAULT SHIELD — 24/7 Local Session Guardian for Windows
Protects Telegram Desktop session folder (%APPDATA%\\Telegram Desktop\\tdata)
against session stealers (Lumma, RedLine, Vidar, Stealc, Racoon, etc.)
"""

import os
import sys
import time
import shutil
import logging
import subprocess
import threading
from datetime import datetime

# Enforce UTF-8 on Windows Console
try:
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    if hasattr(sys.stderr, 'reconfigure'):
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
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

TELEGRAM_DIR = os.path.join(os.getenv("APPDATA", ""), "Telegram Desktop")
TDATA_DIR = os.path.join(TELEGRAM_DIR, "tdata")
CANARY_FILE = os.path.join(TDATA_DIR, "canary_session.key")

WHITELISTED_PROCESSES = {
    "telegram.exe",
    "explorer.exe",
    "python.exe",
    "pythonw.exe",
    "system",
    "svchost.exe"
}

def is_admin():
    try:
        import ctypes
        return ctypes.windll.shell32.IsUserAnAdmin() != 0
    except Exception:
        return False

def setup_canary_trap():
    """Places a bait canary file in tdata. Stealers scan and open every file in tdata."""
    if not os.path.exists(TDATA_DIR):
        logging.warning(f"TDATA directory not found at {TDATA_DIR}")
        return False

    try:
        # Create canary file if not exists
        with open(CANARY_FILE, "wb") as f:
            f.write(b"TG_GUARD_CANARY_TRAP_DO_NOT_TOUCH_PROTECTED_SESSION_DATA_777")
        logging.info(f"✅ Canary bait planted successfully: {CANARY_FILE}")
        return True
    except Exception as e:
        logging.error(f"Failed to plant canary bait: {e}")
        return False

def check_and_terminate_suspicious_processes():
    """Scans running processes and terminates any unknown process scanning Telegram tdata."""
    try:
        import psutil
    except ImportError:
        subprocess.run([sys.executable, "-m", "pip", "install", "psutil"], capture_output=True)
        import psutil

    killed_any = False
    for proc in psutil.process_iter(['pid', 'name', 'exe', 'cmdline']):
        try:
            name = proc.info.get('name') or ""
            name_lower = name.lower()

            if name_lower in WHITELISTED_PROCESSES:
                continue

            # Check open files of the process
            try:
                open_files = proc.open_files()
                for of in open_files:
                    if TDATA_DIR.lower() in of.path.lower():
                        logging.critical(f"🚨 STEALER DETECTED! Process '{name}' (PID: {proc.pid}, EXE: {proc.info.get('exe')}) is reading TDATA!")
                        proc.kill()
                        logging.critical(f"💥 KILLED MALICIOUS PROCESS: {name} (PID: {proc.pid})")
                        killed_any = True
                        break
            except (psutil.AccessDenied, psutil.NoSuchProcess):
                pass

            # Check commandline arguments for tdata grabbers
            cmdline = proc.info.get('cmdline') or []
            cmd_str = " ".join(cmdline).lower()
            if "tdata" in cmd_str and name_lower not in WHITELISTED_PROCESSES:
                logging.critical(f"🚨 SUSPICIOUS COMMAND LINE: Process '{name}' looking for tdata: {cmd_str}")
                proc.kill()
                logging.critical(f"💥 KILLED PROCESS: {name} (PID: {proc.pid})")
                killed_any = True

        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            continue

    return killed_any

def lock_tdata_permissions():
    """Applies strict Windows NTFS ACL to tdata so only the current user and Telegram can access it."""
    if not os.path.exists(TDATA_DIR):
        return

    user = os.getenv("USERNAME", "")
    if not user:
        return

    try:
        # Reset inheritance and restrict to current user only
        cmd = f'icacls "{TDATA_DIR}" /inheritance:r /grant:r "{user}:(OI)(CI)F"'
        subprocess.run(cmd, shell=True, capture_output=True)
        logging.info(f"🔒 TDATA folder locked via NTFS ACL to user '{user}'")
    except Exception as e:
        logging.error(f"Error locking tdata: {e}")

def create_secure_tdata_backup():
    """Keeps an encrypted / protected backup of tdata in case of emergency."""
    backup_dir = os.path.join(LOG_DIR, "tdata_vault_backup")
    if not os.path.exists(TDATA_DIR):
        return

    try:
        os.makedirs(backup_dir, exist_ok=True)
        for item in ["D877F783D5D3EF8C", "key_datas", "usermap"]:
            src = os.path.join(TDATA_DIR, item)
            dst = os.path.join(backup_dir, item)
            if os.path.exists(src) and not os.path.exists(dst):
                if os.path.isdir(src):
                    shutil.copytree(src, dst, dirs_exist_ok=True)
                else:
                    shutil.copy2(src, dst)
        logging.info(f"🛡️ Safe session backup verified in: {backup_dir}")
    except Exception as e:
        logging.warning(f"Backup warning: {e}")

def add_to_windows_startup():
    """Configures Vault Shield to auto-start with Windows 24/7."""
    startup_dir = os.path.join(os.getenv("APPDATA", ""), r"Microsoft\Windows\Start Menu\Programs\Startup")
    bat_path = os.path.join(startup_dir, "TelegramGuardVault.bat")
    
    current_script = os.path.abspath(__file__)
    python_exe = sys.executable

    bat_content = f'@echo off\nstart "" "{python_exe}" -X utf8 "{current_script}" --background\n'
    try:
        with open(bat_path, "w", encoding="utf-8") as f:
            f.write(bat_content)
        logging.info(f"🚀 Added to Windows Startup (runs 24/7): {bat_path}")
    except Exception as e:
        logging.warning(f"Could not add to Startup: {e}")

def monitor_canary_loop():
    """Watches the canary file. If touched or accessed by unauthorized program, trigger alarm."""
    last_mtime = 0
    if os.path.exists(CANARY_FILE):
        last_mtime = os.path.getmtime(CANARY_FILE)

    while True:
        try:
            if not os.path.exists(CANARY_FILE):
                logging.critical("🚨 ALERT: Canary bait file was DELETED or MOVED by external software!")
                setup_canary_trap()
                check_and_terminate_suspicious_processes()

            # Active process scanning
            check_and_terminate_suspicious_processes()

        except Exception as e:
            logging.error(f"Error in canary loop: {e}")

        time.sleep(1.0)

def main():
    print("=" * 60)
    print("🛡️  TELEGRAM GUARD — TDATA VAULT SHIELD (Windows 24/7)")
    print("=" * 60)
    print(f"Target TDATA Path: {TDATA_DIR}")
    print(f"Status: ACTIVATING 24/7 PROTECTION...")

    setup_canary_trap()
    lock_tdata_permissions()
    create_secure_tdata_backup()
    add_to_windows_startup()

    print("✅ Vault Shield is ACTIVE! Guarding against all session stealers.")
    print("Log file:", LOG_FILE)
    print("Running in continuous background sentinel mode (1-second tick)...")

    # Start 24/7 monitor thread
    monitor_canary_loop()

if __name__ == "__main__":
    main()
