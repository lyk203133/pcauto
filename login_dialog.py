"""
登入對話框 — iOS 風格，啟動時顯示
呼叫 /api/pcauto/login，成功後保存 JWT、role、username 到 config
"""
import requests
from urllib.parse import urlparse, urlunparse

from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, QFormLayout, QFrame
)
from PyQt5.QtCore import Qt

import config_manager

LOGIN_STYLE = """
QDialog {
    background-color: #F2F2F7;
    font-family: -apple-system, 'Helvetica Neue', Arial, sans-serif;
    font-size: 13px;
    color: #1C1C1E;
}
QFrame#card {
    background-color: #FFFFFF;
    border-radius: 12px;
    border: none;
}
QLineEdit {
    background-color: #F2F2F7;
    border: 1px solid #C7C7CC;
    border-radius: 8px;
    padding: 8px 10px;
    font-size: 13px;
    color: #1C1C1E;
    min-height: 28px;
}
QLineEdit:focus {
    border-color: #007AFF;
    background-color: #FFFFFF;
}
QComboBox {
    background-color: #F2F2F7;
    border: 1px solid #C7C7CC;
    border-radius: 8px;
    padding: 6px 10px;
    font-size: 13px;
    color: #1C1C1E;
    min-height: 28px;
}
QComboBox:focus { border-color: #007AFF; }
QComboBox::drop-down { border: none; width: 18px; }
QComboBox QAbstractItemView {
    background-color: #FFFFFF;
    border: 1px solid #C7C7CC;
    border-radius: 8px;
    selection-background-color: #E5F0FF;
    selection-color: #007AFF;
}
QPushButton#primary {
    background-color: #007AFF;
    color: #FFFFFF;
    border: none;
    border-radius: 10px;
    padding: 10px 0px;
    font-size: 14px;
    font-weight: 600;
}
QPushButton#primary:hover  { background-color: #0066DD; }
QPushButton#primary:pressed { background-color: #0055BB; }
QPushButton#primary:disabled { background-color: #C7C7CC; color: #FFFFFF; }
QPushButton#cancel_btn {
    background-color: transparent;
    color: #8E8E93;
    border: 1px solid #C7C7CC;
    border-radius: 10px;
    font-size: 13px;
    padding: 8px 0px;
}
QPushButton#cancel_btn:hover { background-color: #E5E5EA; }
QLabel#error_label {
    color: #FF3B30;
    font-size: 12px;
    padding: 4px 0;
}
QLabel#title_label {
    font-size: 22px;
    font-weight: 700;
    color: #1C1C1E;
}
QLabel#subtitle_label {
    font-size: 12px;
    color: #8E8E93;
}
QLabel.field_label {
    font-size: 12px;
    color: #3C3C43;
    font-weight: 500;
}
"""


def _extract_base_url(poll_url: str) -> str:
    """從掃單 URL 提取 base URL（scheme + host + port）"""
    if not poll_url:
        return ''
    try:
        parsed = urlparse(poll_url)
        return urlunparse((parsed.scheme, parsed.netloc, '', '', '', ''))
    except Exception:
        return ''


class LoginDialog(QDialog):
    """iOS 風格登入對話框"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle('AutoBrowser — 登入')
        self.setFixedWidth(360)
        self.setWindowFlags(Qt.Dialog | Qt.WindowCloseButtonHint)
        self.setStyleSheet(LOGIN_STYLE)
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 28, 24, 24)
        root.setSpacing(16)

        # ── 標題區 ────────────────────────────────────────────────────────
        title = QLabel('🤖 AutoBrowser')
        title.setObjectName('title_label')
        title.setAlignment(Qt.AlignCenter)
        root.addWidget(title)

        subtitle = QLabel('管理員登入')
        subtitle.setObjectName('subtitle_label')
        subtitle.setAlignment(Qt.AlignCenter)
        root.addWidget(subtitle)

        root.addSpacing(4)

        # ── 表單卡片 ──────────────────────────────────────────────────────
        card = QFrame()
        card.setObjectName('card')
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(16, 16, 16, 16)
        card_layout.setSpacing(12)

        form = QFormLayout()
        form.setSpacing(10)
        form.setLabelAlignment(Qt.AlignLeft)
        form.setFormAlignment(Qt.AlignLeft)

        # 服務器地址
        cfg = config_manager.load_config()
        base_url = cfg.get('server_url') or _extract_base_url(cfg.get('poll_url', ''))

        self.server_input = QLineEdit()
        self.server_input.setPlaceholderText('http://your-server.com')
        self.server_input.setText(base_url)
        form.addRow('服務器地址:', self.server_input)

        # 管理員帳號
        self.username_input = QLineEdit()
        self.username_input.setPlaceholderText('管理員帳號')
        self.username_input.setText(cfg.get('username', ''))
        form.addRow('帳號:', self.username_input)

        # 密碼
        self.password_input = QLineEdit()
        self.password_input.setEchoMode(QLineEdit.Password)
        self.password_input.setPlaceholderText('密碼')
        form.addRow('密碼:', self.password_input)

        # 監聽會員（商戶 api_key，決定掃哪個商戶的單）
        self.watch_key_input = QLineEdit()
        self.watch_key_input.setPlaceholderText('商戶 API Key（留空則掃所有單）')
        self.watch_key_input.setText(cfg.get('watch_merchant_api_key', ''))
        form.addRow('監聽會員:', self.watch_key_input)

        card_layout.addLayout(form)
        root.addWidget(card)

        # ── 錯誤提示 ──────────────────────────────────────────────────────
        self.error_label = QLabel('')
        self.error_label.setObjectName('error_label')
        self.error_label.setAlignment(Qt.AlignCenter)
        self.error_label.setWordWrap(True)
        self.error_label.setVisible(False)
        root.addWidget(self.error_label)

        # ── 按鈕 ──────────────────────────────────────────────────────────
        self.login_btn = QPushButton('登入')
        self.login_btn.setObjectName('primary')
        self.login_btn.setFixedHeight(44)
        self.login_btn.setCursor(Qt.PointingHandCursor)
        self.login_btn.clicked.connect(self._do_login)
        root.addWidget(self.login_btn)

        cancel_btn = QPushButton('取消')
        cancel_btn.setObjectName('cancel_btn')
        cancel_btn.setFixedHeight(36)
        cancel_btn.setCursor(Qt.PointingHandCursor)
        cancel_btn.clicked.connect(self.reject)
        root.addWidget(cancel_btn)

        # Enter 鍵觸發登入
        self.password_input.returnPressed.connect(self._do_login)
        self.username_input.returnPressed.connect(self.password_input.setFocus)

    def _do_login(self):
        """管理員帳號密碼登入"""
        server   = self.server_input.text().strip().rstrip('/')
        username = self.username_input.text().strip()
        password = self.password_input.text()

        if not server:
            self._show_error('請輸入服務器地址')
            return
        if not username:
            self._show_error('請輸入帳號')
            return
        if not password:
            self._show_error('請輸入密碼')
            return

        self.login_btn.setEnabled(False)
        self.login_btn.setText('登入中...')
        self._show_error('')

        try:
            resp = requests.post(
                f'{server}/api/pcauto/login',
                json={'username': username, 'password': password, 'user_type': 'admin'},
                timeout=10
            )
            if resp.status_code == 200:
                data = resp.json()
                if data.get('success'):
                    cfg = config_manager.load_config()
                    cfg['jwt_token']              = data.get('token', '')
                    cfg['user_role']              = 'admin'
                    cfg['username']               = data.get('username', username)
                    cfg['server_url']             = server
                    cfg['poll_url']               = f'{server}/api/pcauto/pending-tasks'
                    cfg['callback_url']           = f'{server}/api/pcauto/callback'
                    cfg['watch_merchant_api_key'] = self.watch_key_input.text().strip()
                    config_manager.save_config(cfg)
                    self.accept()
                    return
                self._show_error(data.get('message', '登入失敗'))
            elif resp.status_code == 401:
                self._show_error('帳號或密碼錯誤')
            elif resp.status_code == 404:
                self._show_error('服務器地址錯誤或 API 不存在')
            else:
                self._show_error(f'服務器錯誤 ({resp.status_code})')
        except requests.exceptions.ConnectionError:
            self._show_error('無法連接到服務器，請檢查地址')
        except requests.exceptions.Timeout:
            self._show_error('連接超時，請稍後重試')
        except Exception as e:
            self._show_error(f'登入異常: {e}')
        finally:
            self.login_btn.setEnabled(True)
            self.login_btn.setText('登入')

    def _show_error(self, msg: str):
        if msg:
            self.error_label.setText(f'⚠️ {msg}')
            self.error_label.setVisible(True)
        else:
            self.error_label.setVisible(False)
