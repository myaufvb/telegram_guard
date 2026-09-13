@echo off
chcp 65001 >nul
title TELEGRAM GUARD — РЕЖИМ СКРЫТНОСТИ (STEALTH MODE)
color 0a
echo ========================================================
echo   TELEGRAM GUARD — АКТИВАЦИЯ РЕЖИМА СКРЫТНОСТИ
echo ========================================================
echo.
py -3 -X utf8 "modules\telegram_stealth_mode.py"
echo.
pause
