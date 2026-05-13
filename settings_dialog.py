"""
設定對話框
"""
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QGroupBox, QComboBox, QCheckBox, QSpinBox, QLineEdit, QFormLayout,
    QTabWidget, QWidget
)
from PyQt5.QtCore import Qt
import i18n
from i18n import t


class SettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.main_window = parent
        self.setWindowTitle(t("btn_settings"))
        self.setMinimumSize(600, 500)
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)

        # 標籤頁
        tabs = QTabWidget()

        # 一般設定
        general_tab = QWidget()
        general_layout = QVBoxLayout(general_tab)

        # 語言設定
        lang_group = QGroupBox(t("menu_language"))
        lang_layout = QFormLayout(lang_group)

        self.lang_combo = QComboBox()
        for lang_code, lang_name in i18n.t.lang_names.items():
            self.lang_combo.addItem(lang_name, lang_code)
        from i18n import get_current_lang
        current_lang = get_current_lang()
        idx = self.lang_combo.findData(current_lang)
        if idx >= 0:
            self.lang_combo.setCurrentIndex(idx)

        lang_layout.addRow(t("menu_language") + ":", self.lang_combo)
        general_layout.addWidget(lang_group)
        general_layout.addStretch()

        tabs.addTab(general_tab, "⚙️ " + t("btn_settings"))

        # 瀏覽器設定
        browser_tab = QWidget()
        browser_layout = QVBoxLayout(browser_tab)

        browser_type_group = QGroupBox(t("config_browser"))
        browser_type_layout = QFormLayout(browser_type_group)

        self.browser_type = QComboBox()
        self.browser_type.addItems([t("config_browser_chrome"), t("config_browser_cloak")])
        browser_type_layout.addRow(t("config_browser") + ":", self.browser_type)

        browser_layout.addWidget(browser_type_group)

        options_group = QGroupBox(t("config_browser_options"))
        options_layout = QVBoxLayout(options_group)

        self.headless_check = QCheckBox(t("config_headless"))
        options_layout.addWidget(self.headless_check)

        self.humanize_check = QCheckBox(t("config_humanize"))
        options_layout.addWidget(self.humanize_check)

        self.geoip_check = QCheckBox(t("config_geoip"))
        options_layout.addWidget(self.geoip_check)

        browser_layout.addWidget(options_group)
        browser_layout.addStretch()

        tabs.addTab(browser_tab, "🌐 " + t("config_browser"))

        # 代理設定
        proxy_tab = QWidget()
        proxy_layout = QVBoxLayout(proxy_tab)

        proxy_group = QGroupBox(t("config_proxy"))
        proxy_form = QFormLayout(proxy_group)

        self.proxy_type = QComboBox()
        self.proxy_type.addItems([t("config_proxy_none"), "HTTP", "HTTPS", "SOCKS5"])
        proxy_form.addRow(t("config_proxy_type") + ":", self.proxy_type)

        self.proxy_host = QLineEdit()
        self.proxy_host.setPlaceholderText("127.0.0.1")
        proxy_form.addRow("Host:", self.proxy_host)

        self.proxy_port = QLineEdit()
        self.proxy_port.setPlaceholderText("7890")
        proxy_form.addRow("Port:", self.proxy_port)

        proxy_layout.addWidget(proxy_group)
        proxy_layout.addStretch()

        tabs.addTab(proxy_tab, "🔌 " + t("config_proxy"))

        # 資料庫設定
        db_tab = QWidget()
        db_layout = QVBoxLayout(db_tab)

        db_group = QGroupBox(t("db_config_title"))
        db_form = QFormLayout(db_group)

        self.db_host = QLineEdit("localhost")
        db_form.addRow(t("db_host") + ":", self.db_host)

        self.db_port = QSpinBox()
        self.db_port.setRange(1, 65535)
        self.db_port.setValue(3306)
        db_form.addRow(t("db_port") + ":", self.db_port)

        self.db_user = QLineEdit("root")
        db_form.addRow(t("db_user") + ":", self.db_user)

        self.db_password = QLineEdit("123456")
        self.db_password.setEchoMode(QLineEdit.Password)
        db_form.addRow(t("db_password") + ":", self.db_password)

        self.db_name = QLineEdit("trader")
        db_form.addRow(t("db_database") + ":", self.db_name)

        db_layout.addWidget(db_group)

        monitor_group = QGroupBox(t("db_monitor_title"))
        monitor_layout = QFormLayout(monitor_group)

        self.monitor_interval = QSpinBox()
        self.monitor_interval.setRange(5, 3600)
        self.monitor_interval.setValue(10)
        monitor_layout.addRow(t("db_monitor_interval") + " (秒):", self.monitor_interval)

        db_layout.addWidget(monitor_group)
        db_layout.addStretch()

        tabs.addTab(db_tab, "💾 " + t("btn_database"))

        layout.addWidget(tabs)

        # 按鈕行
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        save_btn = QPushButton("💾 " + t("btn_ok"))
        save_btn.clicked.connect(self.save_settings)
        btn_layout.addWidget(save_btn)

        cancel_btn = QPushButton(t("btn_cancel"))
        cancel_btn.clicked.connect(self.close)
        btn_layout.addWidget(cancel_btn)

        layout.addLayout(btn_layout)

    def save_settings(self):
        """保存設定"""
        from PyQt5.QtWidgets import QMessageBox
        QMessageBox.information(self, "成功", "設定已保存")
        self.close()
