@echo off
title X Media Pro Saver - Khoi Chay
echo ========================================================
echo        X MEDIA PRO SAVER - TAI ANH & VIDEO X
echo ========================================================
echo Dang kiem tra moi truong Python...
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [LOI] Khong tim thay Python tren may cua ban!
    echo Vui long cai dat Python tai https://www.python.org/
    pause
    exit /b
)

echo Dang cai dat/kiem tra cac thu vien can thiet...
python -m pip install -r requirements.txt --quiet

echo.
echo Dang khoi chay ung dung va mo trinh duyet...
echo Truyen cap: http://127.0.0.1:5000
echo.
python app.py
pause
