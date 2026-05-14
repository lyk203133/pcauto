@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo ================================
echo   pcauto Windows 打包
echo ================================

:: 1. 檢查環境
echo [1/4] 檢查環境...
python --version
pip show pyinstaller >nul 2>&1
if %errorlevel% neq 0 (
    echo   安裝 PyInstaller...
    pip install pyinstaller -q
)

:: 2. 安裝依賴
echo [2/4] 安裝依賴...
pip install -r requirements.txt -q

:: 3. 建立預設 config.json（不打包進去）
if not exist "config.json" (
    echo   建立預設 config.json...
    (
        echo {
        echo   "server_url": "http://localhost:8088",
        echo   "api_key": "",
        echo   "hmac_secret": "",
        echo   "poll_interval": 5
        echo }
    ) > config.json
)

:: 4. 打包（使用統一的 pcauto.spec）
echo [3/4] 打包中（可能需要 1-3 分鐘）...
pyinstaller pcauto.spec --clean --noconfirm

:: 5. 把 config.json 複製到 dist 目錄
echo [4/4] 複製設定檔...
if not exist "dist\pcauto" mkdir dist\pcauto
copy /y config.json dist\pcauto\config.json >nul

echo.
echo ================================
echo   打包完成！
echo   程式：dist\pcauto\pcauto.exe
echo   設定：dist\pcauto\config.json  ^(首次使用請填寫^)
echo ================================
echo.
echo 按任意鍵打開輸出目錄...
pause >nul
explorer dist\pcauto
