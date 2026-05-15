@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo ================================
echo   pcauto Windows Rust 打包
echo ================================

:: 建立預設 config.json（不打包進去）
if not exist "config.json" (
    echo 建立預設 config.json...
    copy config.json.example config.json >nul
)

echo [1/2] cargo build --release ...
cargo build --release
if %errorlevel% neq 0 (
    echo 打包失敗！
    pause
    exit /b 1
)

echo [2/2] 完成！
echo.
echo ================================
echo   打包完成！
echo   程式：target\release\pcauto.exe
echo   設定：config.json  (首次使用請填寫後端 URL 和 API Key)
echo ================================
echo.
echo 按任意鍵打開輸出目錄...
pause >nul
explorer target\release
