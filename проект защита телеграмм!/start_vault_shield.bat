@echo off
chcp 65001 >nul
title TELEGRAM GUARD — TDATA VAULT SHIELD 24/7
color 0b
echo ========================================================
echo   TELEGRAM GUARD — ЛОКАЛЬНЫЙ ЗАЩИТНИК TDATA 24/7
echo ========================================================
echo.
echo Запуск защиты папки Telegram Desktop против стиллеров...
python -X utf8 "modules\tdata_vault_shield.py"
pause
