"""
瀏覽器對話框
"""
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QGroupBox, QComboBox, QCheckBox, QSpinBox, QLineEdit, QTextEdit
)
from PyQt5.QtCore import Qt
import i18n
from i18n import t


class BrowserDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.main_window = parent
        self.setWindowTitle(t("tab_browser_config"))
        self.setMinimumSize(600, 500)
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)

        # 瀏覽器類型
        browser_group = QGroupBox(t("config_browser"))
        browser_layout = QVBoxLayout(browser_group)

        self.browser_type = QComboBox()
        self.browser_type.addItems([t("config_browser_chrome"), t("config_browser_cloak")])
        browser_layout.addWidget(self.browser_type)

        layout.addWidget(browser_group)

        # 瀏覽器選項
        options_group = QGroupBox(t("config_browser_options"))
        options_layout = QVBoxLayout(options_group)

        self.headless_check = QCheckBox(t("config_headless"))
        options_layout.addWidget(self.headless_check)

        self.humanize_check = QCheckBox(t("config_humanize"))
        options_layout.addWidget(self.humanize_check)

        self.geoip_check = QCheckBox(t("config_geoip"))
        options_layout.addWidget(self.geoip_check)

        layout.addWidget(options_group)

        # 代理配置
        proxy_group = QGroupBox(t("config_proxy"))
        proxy_layout = QVBoxLayout(proxy_group)

        self.proxy_type = QComboBox()
        self.proxy_type.addItems([t("config_proxy_none"), "HTTP", "SOCKS5"])
        proxy_layout.addWidget(self.proxy_type)

        self.proxy_host = QLineEdit()
        self.proxy_host.setPlaceholderText("127.0.0.1")
        proxy_layout.addWidget(QLabel("Host:"))
        proxy_layout.addWidget(self.proxy_host)

        self.proxy_port = QLineEdit()
        self.proxy_port.setPlaceholderText("7890")
        proxy_layout.addWidget(QLabel("Port:"))
        proxy_layout.addWidget(self.proxy_port)

        layout.addWidget(proxy_group)

        # 按鈕
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        open_btn = QPushButton("🌐 " + t("btn_browser"))
        open_btn.clicked.connect(self.open_browser)
        btn_layout.addWidget(open_btn)

        close_btn = QPushButton(t("btn_cancel"))
        close_btn.clicked.connect(self.close)
        btn_layout.addWidget(close_btn)

        layout.addLayout(btn_layout)

    def open_browser(self):
        """打開瀏覽器"""
        self.close()
        if self.main_window:
            self.main_window._launch_browser()
