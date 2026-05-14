"""
配置管理器 — 讀寫 config.json
打包後 config.json 放在 exe/app 旁邊，不在 _MEIPASS 裡
"""
import sys
import json
from pathlib import Path

def _app_dir() -> Path:
    """返回應用程式根目錄（開發 = 原始碼目錄；打包 = exe 所在目錄）"""
    if getattr(sys, 'frozen', False):
        # PyInstaller 打包後：exe 路徑的父目錄
        return Path(sys.executable).parent
    # 開發模式：config_manager.py 所在目錄
    return Path(__file__).parent

CONFIG_FILE = _app_dir() / 'config.json'

DEFAULT_CONFIG = {
    'server_url':    'http://localhost:8000',
    'api_key':       '',
    'hmac_secret':   '',
    'poll_interval': 10,
}


def load_config() -> dict:
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
            # 補充缺失的 key
            for k, v in DEFAULT_CONFIG.items():
                data.setdefault(k, v)
            return data
        except Exception:
            pass
    return DEFAULT_CONFIG.copy()


def save_config(config: dict):
    with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
        json.dump(config, f, ensure_ascii=False, indent=2)


def get(key: str, default=None):
    return load_config().get(key, default)


def set_value(key: str, value):
    cfg = load_config()
    cfg[key] = value
    save_config(cfg)
