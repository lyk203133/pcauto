"""
日誌查看對話框
"""
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QTextEdit,
    QFileDialog
)
from PyQt5.QtCore import Qt
import i18n
from i18n import t


class LogDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.main_window = parent
        self.setWindowTitle(t("tab_execution_log"))
        self.setMinimumSize(700, 500)
        self.init_ui()
        self.load_logs()

    def init_ui(self):
        layout = QVBoxLayout(self)

        # 標題
        title_label = QLabel("📋 " + t("tab_execution_log"))
        title_label.setStyleSheet("font-size: 16px; font-weight: bold;")
        layout.addWidget(title_label)

        # 日誌顯示
        self.log_display = QTextEdit()
        self.log_display.setReadOnly(True)
        self.log_display.setStyleSheet("""
            QTextEdit {
                background-color: #1e1e1e;
                color: #d4d4d4;
                font-family: 'Consolas', 'Monaco', monospace;
                font-size: 12px;
                border-radius: 5px;
            }
        """)
        layout.addWidget(self.log_display)

        # 按鈕行
        btn_layout = QHBoxLayout()

        refresh_btn = QPushButton("🔄 " + t("btn_refresh"))
        refresh_btn.clicked.connect(self.load_logs)
        btn_layout.addWidget(refresh_btn)

        clear_btn = QPushButton("🗑 " + t("btn_clear_log"))
        clear_btn.clicked.connect(self.clear_logs)
        btn_layout.addWidget(clear_btn)

        export_btn = QPushButton("📥 導出日誌")
        export_btn.clicked.connect(self.export_logs)
        btn_layout.addWidget(export_btn)

        btn_layout.addStretch()

        close_btn = QPushButton(t("btn_ok"))
        close_btn.clicked.connect(self.close)
        btn_layout.addWidget(close_btn)

        layout.addLayout(btn_layout)

    def load_logs(self):
        """載入日誌"""
        self.log_display.clear()

        # 從文件載入
        log_file = "automation.log"
        try:
            with open(log_file, 'r', encoding='utf-8') as f:
                logs = f.read()
                self.log_display.setPlainText(logs)
        except FileNotFoundError:
            self.log_display.setPlainText("No log file found.")
        except Exception as e:
            self.log_display.setPlainText(f"Error loading logs: {e}")

        # 滾動到底部
        cursor = self.log_display.textCursor()
        cursor.movePosition(cursor.End)
        self.log_display.setTextCursor(cursor)

    def clear_logs(self):
        """清除日誌"""
        self.log_display.clear()
        # 也清除文件
        try:
            open("automation.log", 'w').close()
        except:
            pass

    def export_logs(self):
        """導出日誌"""
        file_path, _ = QFileDialog.getSaveFileName(
            self, "導出日誌", "automation.log", "Log Files (*.log);;All Files (*)"
        )
        if file_path:
            try:
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(self.log_display.toPlainText())
                from PyQt5.QtWidgets import QMessageBox
                QMessageBox.information(self, "成功", f"日誌已導出到: {file_path}")
            except Exception as e:
                from PyQt5.QtWidgets import QMessageBox
                QMessageBox.warning(self, "錯誤", f"導出失敗: {e}")
