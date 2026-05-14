"""
設定對話框 — 後端 URL、API Key、HMAC Secret、輪詢間隔
"""
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, QFormLayout, QSpinBox, QMessageBox
)
from PyQt5.QtCore import Qt

import config_manager

STYLE = """
QDialog {
    background-color: #F2F2F7;
    font-family: -apple-system, 'Helvetica Neue', Arial, sans-serif;
    font-size: 13px;
    color: #1C1C1E;
}
QLineEdit, QSpinBox {
    background-color: #FFFFFF;
    border: 1px solid #C7C7CC;
    border-radius: 8px;
    padding: 6px 10px;
    font-size: 13px;
    color: #1C1C1E;
    min-height: 28px;
}
QLineEdit:focus, QSpinBox:focus { border-color: #007AFF; }
QPushButton#primary {
    background-color: #007AFF;
    color: #FFFFFF;
    border: none;
    border-radius: 10px;
    padding: 10px 20px;
    font-size: 13px;
    font-weight: 600;
}
QPushButton#primary:hover  { background-color: #0066DD; }
QPushButton#cancel_btn {
    background-color: transparent;
    color: #8E8E93;
    border: 1px solid #C7C7CC;
    border-radius: 10px;
    font-size: 13px;
    padding: 8px 20px;
}
QPushButton#cancel_btn:hover { background-color: #E5E5EA; }
QLabel#section {
    font-size: 10px;
    font-weight: 600;
    color: #8E8E93;
    letter-spacing: 0.5px;
}
"""


class SettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle('⚙️ 設定')
        self.setFixedWidth(420)
        self.setStyleSheet(STYLE)
        self._build_ui()
        self._load()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 24, 24, 20)
        root.setSpacing(14)

        # 標題
        title = QLabel('⚙️ 服務設定')
        title.setStyleSheet('font-size:16px; font-weight:700; color:#1C1C1E;')
        root.addWidget(title)

        # 表單
        form = QFormLayout()
        form.setSpacing(10)
        form.setLabelAlignment(Qt.AlignLeft)

        self.server_url_input = QLineEdit()
        self.server_url_input.setPlaceholderText('http://your-server.com')
        form.addRow('後端 URL:', self.server_url_input)

        self.api_key_input = QLineEdit()
        self.api_key_input.setPlaceholderText('X-Pcauto-Key 值')
        form.addRow('API Key:', self.api_key_input)

        self.hmac_secret_input = QLineEdit()
        self.hmac_secret_input.setEchoMode(QLineEdit.Password)
        self.hmac_secret_input.setPlaceholderText('HMAC-SHA256 密鑰')
        form.addRow('HMAC Secret:', self.hmac_secret_input)

        self.poll_interval_spin = QSpinBox()
        self.poll_interval_spin.setRange(5, 300)
        self.poll_interval_spin.setSuffix(' 秒')
        form.addRow('輪詢間隔:', self.poll_interval_spin)

        root.addLayout(form)

        # 按鈕行
        btn_row = QHBoxLayout()
        btn_row.addStretch()

        cancel_btn = QPushButton('取消')
        cancel_btn.setObjectName('cancel_btn')
        cancel_btn.setFixedHeight(38)
        cancel_btn.setCursor(Qt.PointingHandCursor)
        cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(cancel_btn)

        save_btn = QPushButton('💾 保存')
        save_btn.setObjectName('primary')
        save_btn.setFixedHeight(38)
        save_btn.setCursor(Qt.PointingHandCursor)
        save_btn.clicked.connect(self._save)
        btn_row.addWidget(save_btn)

        root.addLayout(btn_row)

    def _load(self):
        cfg = config_manager.load_config()
        self.server_url_input.setText(cfg.get('server_url', ''))
        self.api_key_input.setText(cfg.get('api_key', ''))
        self.hmac_secret_input.setText(cfg.get('hmac_secret', ''))
        self.poll_interval_spin.setValue(int(cfg.get('poll_interval', 10)))

    def _save(self):
        cfg = config_manager.load_config()
        cfg['server_url']    = self.server_url_input.text().strip().rstrip('/')
        cfg['api_key']       = self.api_key_input.text().strip()
        cfg['hmac_secret']   = self.hmac_secret_input.text()
        cfg['poll_interval'] = self.poll_interval_spin.value()
        config_manager.save_config(cfg)
        QMessageBox.information(self, '成功', '設定已保存')
        self.accept()
