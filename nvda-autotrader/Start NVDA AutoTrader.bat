@echo off
title NVDA AutoTrader
rem Double-click this file to start the NVDA AutoTrader dashboard.
rem Keep it in the same folder as build_dashboard.py.
cd /d "%~dp0"

rem Find Python ("py" is the launcher python.org installs; fall back to "python")
set "PY="
where py >nul 2>nul && set "PY=py -3"
if not defined PY where python >nul 2>nul && set "PY=python"
if not defined PY (
    echo.
    echo  Python is not installed.
    echo  1. Go to https://www.python.org/downloads/ and install Python 3.
    echo  2. On the first installer screen, tick "Add python.exe to PATH".
    echo  3. Then double-click this file again.
    echo.
    pause
    exit /b 1
)

rem First run only: install the libraries the bot needs
%PY% -c "import alpaca_trade_api, yfinance, pandas, numpy, requests, tzlocal" >nul 2>nul
if errorlevel 1 (
    echo Installing required libraries - first run only, takes a minute...
    %PY% -m pip install alpaca-trade-api yfinance pandas numpy requests tzlocal
    if errorlevel 1 (
        echo.
        echo  Library install failed - see the messages above.
        pause
        exit /b 1
    )
)

echo.
echo  Starting NVDA AutoTrader... your browser will open http://127.0.0.1:8080
echo  Keep this window open while you use the dashboard. Close it to quit.
echo.
%PY% build_dashboard.py %*
pause
