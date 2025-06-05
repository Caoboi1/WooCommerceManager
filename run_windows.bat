
@echo off
echo 🚀 WooCommerce Product Manager - Windows Launcher
echo.

:menu
echo Chọn chế độ chạy:
echo 1. Chế độ bình thường (run_windows_safe.py)
echo 2. Chế độ siêu an toàn (main_windows_ultra_safe.py)
echo 3. Chế độ tối thiểu (main_windows_simple.py)
echo 4. Thoát
echo.

set /p choice="Nhập lựa chọn (1-4): "

if "%choice%"=="1" goto normal
if "%choice%"=="2" goto ultra_safe
if "%choice%"=="3" goto simple
if "%choice%"=="4" goto end
goto menu

:normal
echo.
echo 🔄 Chạy chế độ bình thường...
python run_windows_safe.py
pause
goto menu

:ultra_safe
echo.
echo 🛡️  Chạy chế độ siêu an toàn...
python main_windows_ultra_safe.py
pause
goto menu

:simple
echo.
echo ⚡ Chạy chế độ tối thiểu...
python main_windows_simple.py
pause
goto menu

:end
echo 👋 Tạm biệt!
pause
