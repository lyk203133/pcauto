"""
自動化瀏覽器工具 - 版本資訊
Automation Browser Tool - Version Information
"""

__version__ = "1.0.0"
__version_info__ = (1, 0, 0)
__author__ = "Auto Browser Team"
__app_name__ = "自動化瀏覽器工具"
__app_name_en__ = "Automation Browser Tool"

# 版本歷史
VERSION_HISTORY = {
    "1.0.0": {
        "date": "2026-05-13",
        "lang_code": "zh_TW",
        "features": [
            "初始版本發布",
            "多語言支援 (繁體中文、English、Tiếng Việt)",
            "任務管理系統",
            "瀏覽器自動化操作",
            "下拉預設選項"
        ]
    }
}

def get_version():
    """取得版本字串"""
    return __version__

def get_version_full():
    """取得完整版本資訊"""
    return f"v{__version__}"
