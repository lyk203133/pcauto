"""
資料庫對話框
"""
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QGroupBox, QComboBox, QCheckBox, QSpinBox, QLineEdit, QFormLayout,
    QTableWidget, QTableWidgetItem, QHeaderView, QMessageBox
)
from PyQt5.QtCore import Qt
import i18n
from i18n import t
from database import DatabaseManager, DEFAULT_DB_CONFIG


class DatabaseDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.main_window = parent
        self.db_manager = None
        self.setWindowTitle(t("btn_database"))
        self.setMinimumSize(700, 550)
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)

        # 配置區
        config_group = QGroupBox(t("db_config_title"))
        config_layout = QFormLayout(config_group)

        self.host_input = QLineEdit(DEFAULT_DB_CONFIG['host'])
        config_layout.addRow(t("db_host") + ":", self.host_input)

        self.port_input = QSpinBox()
        self.port_input.setRange(1, 65535)
        self.port_input.setValue(DEFAULT_DB_CONFIG['port'])
        config_layout.addRow(t("db_port") + ":", self.port_input)

        self.user_input = QLineEdit(DEFAULT_DB_CONFIG['user'])
        config_layout.addRow(t("db_user") + ":", self.user_input)

        self.password_input = QLineEdit(DEFAULT_DB_CONFIG['password'])
        self.password_input.setEchoMode(QLineEdit.Password)
        config_layout.addRow(t("db_password") + ":", self.password_input)

        self.database_input = QLineEdit(DEFAULT_DB_CONFIG['database'])
        config_layout.addRow(t("db_database") + ":", self.database_input)

        layout.addWidget(config_group)

        # 連接按鈕
        btn_layout = QHBoxLayout()

        self.test_btn = QPushButton(t("db_btn_test"))
        self.test_btn.clicked.connect(self.test_connection)
        btn_layout.addWidget(self.test_btn)

        self.connect_btn = QPushButton(t("db_btn_connect"))
        self.connect_btn.clicked.connect(self.connect_database)
        btn_layout.addWidget(self.connect_btn)

        self.sync_btn = QPushButton(t("db_btn_sync"))
        self.sync_btn.clicked.connect(self.sync_orders)
        self.sync_btn.setEnabled(False)
        btn_layout.addWidget(self.sync_btn)

        layout.addLayout(btn_layout)

        # 監控設定
        monitor_group = QGroupBox(t("db_monitor_title"))
        monitor_layout = QFormLayout(monitor_group)

        self.interval_input = QSpinBox()
        self.interval_input.setRange(5, 3600)
        self.interval_input.setValue(10)
        self.interval_input.setSuffix(" 秒")
        monitor_layout.addRow(t("db_monitor_interval") + ":", self.interval_input)

        monitor_btn_layout = QHBoxLayout()
        self.start_monitor_btn = QPushButton(t("db_btn_start_monitor"))
        self.start_monitor_btn.clicked.connect(self.start_monitor)
        self.start_monitor_btn.setEnabled(False)
        monitor_btn_layout.addWidget(self.start_monitor_btn)

        self.stop_monitor_btn = QPushButton(t("db_btn_stop_monitor"))
        self.stop_monitor_btn.clicked.connect(self.stop_monitor)
        self.stop_monitor_btn.setEnabled(False)
        monitor_btn_layout.addWidget(self.stop_monitor_btn)

        monitor_layout.addRow("", monitor_btn_layout)

        layout.addWidget(monitor_group)

        # 狀態標籤
        self.status_label = QLabel(t("db_status_disconnected"))
        self.status_label.setStyleSheet("color: gray; padding: 5px;")
        layout.addWidget(self.status_label)

        # 任務列表
        task_group = QGroupBox(t("db_task_queue"))
        task_layout = QVBoxLayout(task_group)

        self.task_table = QTableWidget()
        self.task_table.setColumnCount(4)
        self.task_table.setHorizontalHeaderLabels([
            t("db_order_no"),
            t("db_status"),
            t("db_created_at"),
            "重試次數"
        ])
        self.task_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.task_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.task_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.task_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        task_layout.addWidget(self.task_table)

        layout.addWidget(task_group)

        # 關閉按鈕
        close_btn = QPushButton(t("btn_ok"))
        close_btn.clicked.connect(self.close)
        layout.addWidget(close_btn)

    def test_connection(self):
        """測試連接"""
        try:
            import pymysql
            conn = pymysql.connect(
                host=self.host_input.text(),
                port=self.port_input.value(),
                user=self.user_input.text(),
                password=self.password_input.text(),
                database=self.database_input.text()
            )
            conn.close()
            self.status_label.setText(t("db_test_success", msg=""))
            self.status_label.setStyleSheet("color: green; padding: 5px;")
        except ImportError:
            QMessageBox.warning(self, "錯誤", "PyMySQL 未安裝")
        except Exception as e:
            self.status_label.setText(t("db_test_failed", msg=str(e)))
            self.status_label.setStyleSheet("color: red; padding: 5px;")

    def connect_database(self):
        """連接資料庫"""
        try:
            config = {
                'host': self.host_input.text(),
                'port': self.port_input.value(),
                'user': self.user_input.text(),
                'password': self.password_input.text(),
                'database': self.database_input.text()
            }
            self.db_manager = DatabaseManager(config)

            # 確保 order_task 表存在
            self.db_manager.create_order_task_table()

            self.status_label.setText(t("db_status_connected"))
            self.status_label.setStyleSheet("color: green; padding: 5px;")

            self.sync_btn.setEnabled(True)
            self.start_monitor_btn.setEnabled(True)

            self.refresh_task_list()

            if self.main_window:
                self.main_window.db_manager = self.db_manager
                self.main_window.db_connected = True
                self.main_window._update_db_status()

        except ImportError:
            QMessageBox.warning(self, "錯誤", "PyMySQL 未安裝")
        except Exception as e:
            self.status_label.setText(t("db_connect_error", error=str(e)))
            self.status_label.setStyleSheet("color: red; padding: 5px;")

    def sync_orders(self):
        """同步訂單"""
        if not self.db_manager:
            return

        try:
            count = self.db_manager.sync_direct_orders()
            self.status_label.setText(t("db_sync_result", count=count))
            self.refresh_task_list()

            if self.main_window:
                self.main_window.log(t("db_sync_complete", count=count))
        except Exception as e:
            self.status_label.setText(t("db_connect_error", error=str(e)))

    def start_monitor(self):
        """開始監控"""
        self.start_monitor_btn.setEnabled(False)
        self.stop_monitor_btn.setEnabled(True)
        self.status_label.setText(t("db_monitor_running", interval=self.interval_input.value()))
        self.status_label.setStyleSheet("color: blue; padding: 5px;")

        if self.main_window:
            interval = self.interval_input.value()
            self.main_window._start_monitor(interval=interval)

    def stop_monitor(self):
        """停止監控"""
        self.start_monitor_btn.setEnabled(True)
        self.stop_monitor_btn.setEnabled(False)
        self.status_label.setText(t("db_monitor_stopped"))
        self.status_label.setStyleSheet("color: gray; padding: 5px;")

        if self.main_window:
            self.main_window._stop_monitor()

    def refresh_task_list(self):
        """刷新任務列表"""
        if not self.db_manager:
            return

        try:
            tasks = self.db_manager.get_pending_tasks()
            self.task_table.setRowCount(len(tasks))

            for row, task in enumerate(tasks):
                self.task_table.setItem(row, 0, QTableWidgetItem(str(task.get('order_no', ''))))
                self.task_table.setItem(row, 1, QTableWidgetItem(task.get('status', '')))
                self.task_table.setItem(row, 2, QTableWidgetItem(str(task.get('created_at', ''))))
                self.task_table.setItem(row, 3, QTableWidgetItem(str(task.get('retry_count', 0))))

        except Exception as e:
            self.status_label.setText(t("db_connect_error", error=str(e)))
