@echo off
rem Menjalankan SIAGA ROB Semarang. Memakai Python FlyEnv 64-bit jika ada, selain itu python biasa.
chcp 65001 > nul
set PYTHONIOENCODING=utf-8
cd /d "%~dp0"
set PY=C:\Users\hadi\AppData\Local\Programs\FlyEnv-Data\env\python\python.exe
if not exist "%PY%" set PY=python
"%PY%" siaga_rob.py
pause
