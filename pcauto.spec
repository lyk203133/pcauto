# -*- mode: python ; coding: utf-8 -*-
"""
pcauto 跨平台打包規格
  Windows → dist/pcauto/pcauto.exe  (COLLECT 目錄)
  macOS   → dist/pcauto.app         (App Bundle)

用法：
  pyinstaller pcauto.spec --clean
"""
import sys
import os

IS_WIN = sys.platform == 'win32'
IS_MAC = sys.platform == 'darwin'

# ── 隨包攜帶的資料檔 ──────────────────────────────────────
# config.json 不打包（用戶需要手動編輯），程式啟動時找不到會自動建立預設值
datas = [
    ('tasks.json',  '.'),
]
# 如果存在圖示就帶入
if IS_WIN and os.path.exists('icon.ico'):
    pass  # icon 在 EXE 裡直接引用
if IS_MAC and os.path.exists('icon.icns'):
    datas.append(('icon.icns', '.'))

# ── 隱式引入（PyInstaller 靜態分析掃不到的）────────────────
hidden = [
    # PyQt5 核心
    'PyQt5',
    'PyQt5.QtCore',
    'PyQt5.QtGui',
    'PyQt5.QtWidgets',
    'PyQt5.sip',
    # 網路
    'requests',
    'requests.adapters',
    'requests.auth',
    'urllib3',
    'urllib3.util',
    'urllib3.util.retry',
    'certifi',
    # 標準庫
    'hmac',
    'hashlib',
    'json',
    'logging',
    'logging.handlers',
    'threading',
    'queue',
    # 本地模組（相對 import 的同目錄模組）
    'config_manager',
    'callback_sender',
    'task_poller',
    'browser_thread',
    'main_window',
    'settings_dialog',
    'i18n',
    'version',
]

# playwright（可選）
try:
    import playwright
    hidden += [
        'playwright',
        'playwright.sync_api',
        'playwright._impl._sync_api',
        'playwright._impl._browser',
        'playwright._impl._browser_context',
        'playwright._impl._page',
    ]
except ImportError:
    pass

# ── 分析 ──────────────────────────────────────────────────
a = Analysis(
    ['main.py'],
    pathex=[os.path.abspath('.')],
    binaries=[],
    datas=datas,
    hiddenimports=hidden,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'tkinter', 'matplotlib', 'scipy', 'numpy',
        'pandas', 'PIL', 'cv2',
    ],
    noarchive=False,
)

pyz = PYZ(a.pure)

# ── EXE ───────────────────────────────────────────────────
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='pcauto',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,                          # 不顯示控制台視窗
    disable_windowed_traceback=False,
    argv_emulation=IS_MAC,                  # macOS 需要 True
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='icon.ico' if (IS_WIN and os.path.exists('icon.ico')) else
         ('icon.icns' if (IS_MAC and os.path.exists('icon.icns')) else None),
)

# ── COLLECT（Windows / Linux 目錄模式）────────────────────
coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='pcauto',
)

# ── BUNDLE（macOS .app）───────────────────────────────────
if IS_MAC:
    app = BUNDLE(
        coll,
        name='pcauto.app',
        icon='icon.icns' if os.path.exists('icon.icns') else None,
        bundle_identifier='com.pcauto.trader',
        info_plist={
            'CFBundleName':             'pcauto',
            'CFBundleDisplayName':      'pcauto',
            'CFBundleShortVersionString': '1.0.0',
            'CFBundleVersion':          '1.0.0',
            'NSHighResolutionCapable':  True,
            'NSRequiresAquaSystemAppearance': False,  # 支援 Dark Mode
        },
    )
