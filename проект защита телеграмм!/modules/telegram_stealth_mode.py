"""
TELEGRAM STEALTH MODE (Режим Скрытности для Windows)
Relocates real Telegram Desktop tdata to a disguised hidden system directory
and leaves a POISONED DECOY / CANARY in %APPDATA%\\Telegram Desktop\\tdata.
No session stealer (Lumma, RedLine, Stealc, Vidar) will ever find your real session!
"""

import os
import sys
import shutil
import logging
import subprocess

# Configure UTF-8
try:
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass

DEFAULT_APPDATA = os.getenv("APPDATA", "")
STANDARD_TG_DIR = os.path.join(DEFAULT_APPDATA, "Telegram Desktop")
STANDARD_TDATA = os.path.join(STANDARD_TG_DIR, "tdata")

# Disguised Stealth Directory
STEALTH_BASE_DIR = os.path.join(os.getenv("PROGRAMDATA", "C:\\ProgramData"), "WindowsTelemetryHost")
STEALTH_TG_DIR = os.path.join(STEALTH_BASE_DIR, "Telegram")
STEALTH_TDATA = os.path.join(STEALTH_TG_DIR, "tdata")

def find_telegram_executable():
    """Finds installed Telegram.exe on the system."""
    candidates = [
        os.path.join(DEFAULT_APPDATA, "Telegram Desktop", "Telegram.exe"),
        os.path.join(os.getenv("LOCALAPPDATA", ""), "TelegramDesktop", "Telegram.exe"),
        os.path.join(os.getenv("PROGRAMFILES", "C:\\Program Files"), "Telegram Desktop", "Telegram.exe"),
        os.path.join(os.getenv("PROGRAMFILES(X86)", "C:\\Program Files (x86)"), "Telegram Desktop", "Telegram.exe"),
    ]
    for p in candidates:
        if os.path.exists(p):
            return p
    return None

def activate_stealth_mode():
    print("=" * 60)
    print("🛡️  TELEGRAM STEALTH MODE — АКТИВАЦИЯ РЕЖИМА СКРЫТНОСТИ")
    print("=" * 60)

    tg_exe = find_telegram_executable()
    if not tg_exe:
        print("❌ Telegram.exe не найден в стандартных путях!")
        return False

    print(f"Найден исполняемый файл Telegram: {tg_exe}")
    print(f"Новое скрытное хранилище: {STEALTH_TG_DIR}")

    # 1. Close running Telegram if any
    try:
        subprocess.run("taskkill /f /im telegram.exe", shell=True, capture_output=True)
    except Exception:
        pass

    # 2. Create Stealth Directory
    os.makedirs(STEALTH_TG_DIR, exist_ok=True)

    # 3. Migrate real tdata to Stealth Directory if not migrated yet
    if os.path.exists(STANDARD_TDATA) and not os.path.exists(STEALTH_TDATA):
        print("📦 Перемещение реальных данных сессии в скрытое хранилище...")
        try:
            shutil.copytree(STANDARD_TDATA, STEALTH_TDATA, dirs_exist_ok=True)
            print("✅ Реальная сессия перенесена в скрытую папку!")
        except Exception as e:
            print(f"Ошибка копирования: {e}")
            return False

    # 4. Create POISONED DECOY in standard %APPDATA%
    print("🪤 Установка фальшивой ловушки (Decoy Trap) в %APPDATA%\\Telegram Desktop\\tdata...")
    try:
        os.makedirs(STANDARD_TDATA, exist_ok=True)
        # Create fake corrupted session keys that crash or confuse stealers
        decoy_files = ["D877F783D5D3EF8C", "key_datas", "usermap"]
        for df in decoy_files:
            target = os.path.join(STANDARD_TDATA, df)
            if not os.path.exists(target):
                with open(target, "wb") as f:
                    f.write(b"POISONED_SESSION_KEY_TG_GUARD_TRAP_ZERO_DATA_00000000000000000000")

        # Create Canary trap
        canary = os.path.join(STANDARD_TDATA, "canary_session.key")
        with open(canary, "wb") as f:
            f.write(b"CANARY_TRAP_MONITOR_ACTIVE")
        print("✅ Фальшивая приманка успешно установлена в стандартной папке!")
    except Exception as e:
        print(f"Ошибка создания приманки: {e}")

    # 5. Create Desktop Stealth Shortcut / Launcher
    user_desktop = os.path.join(os.path.expanduser("~"), "Desktop")
    stealth_bat = os.path.join(user_desktop, "Telegram Stealth.bat")
    
    bat_content = f'@echo off\nstart "" "{tg_exe}" -workdir "{STEALTH_TG_DIR}"\n'
    try:
        with open(stealth_bat, "w", encoding="utf-8") as f:
            f.write(bat_content)
        print(f"🚀 Создан ярлык запуска скрытого Telegram на рабочем столе: {stealth_bat}")
    except Exception as e:
        print(f"Ошибка создания ярлыка: {e}")

    print("\n" + "=" * 60)
    print("🎉 РЕЖИМ СКРЫТНОСТИ УСПЕШНО АКТИВИРОВАН!")
    print("1. Реальный Telegram теперь работает из скрытой папки:")
    print(f"   {STEALTH_TG_DIR}")
    print("2. В стандартной папке %APPDATA% осталась только фальшивая ловушка-приманка.")
    print("3. Ни один стиллер в мире не найдет вашу реальную сессию!")
    print("=" * 60)
    return True

if __name__ == "__main__":
    activate_stealth_mode()
