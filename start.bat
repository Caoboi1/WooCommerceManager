
@echo off
echo 🚀 WooCommerce Product Manager
echo.
echo Đang khởi động ứng dụng...
python main.py
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo ❌ Lỗi khởi động. Đang thử cài đặt dependencies...
    pip install PyQt6 requests pandas
    python main.py
)
pause
