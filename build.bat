@echo off
chcp 65001 >nul
echo ========================================
echo   自动化浏览器工具 - 打包脚本
echo ========================================
echo.

:: 检查依赖
echo [1/3] 检查打包工具...
pip show pyinstaller >nul 2>&1
if %errorlevel% neq 0 (
    echo   安装 PyInstaller...
    pip install pyinstaller -q
)

:: 创建 spec 文件
echo [2/3] 生成配置文件...
(
echo # -*- mode: python ; coding: utf-8 -*-
import sys

block_cipher = None

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[
        ('C:/Users/*/.cloakbrowser/*', 'cloakbrowser/'),
    ],
    datas=[
        ('tasks.json', '.'),
    ],
    hiddenimports=[
        'PyQt5',
        'PyQt5.QtCore',
        'PyQt5.QtGui',
        'PyQt5.QtWidgets',
        'cloakbrowser',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='自动化浏览器工具',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='icon.ico' if __import__('os').path.exists('icon.ico') else None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='自动化浏览器工具',
)
) > build_spec.py

:: 执行打包
echo [3/3] 开始打包...
pyinstaller build_spec.py --clean

echo.
echo ========================================
echo   打包完成！
echo   输出目录: dist/自动化浏览器工具/
echo ========================================
echo.
echo 按任意键打开输出目录...
pause >nul
explorer dist\自动化浏览器工具
