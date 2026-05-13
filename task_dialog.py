"""
任務管理對話框
"""
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QListWidget, QListWidgetItem, QTextBrowser, QSplitter, QWidget,
    QAbstractItemView
)
from PyQt5.QtCore import Qt
import i18n
from i18n import t
import json
from pathlib import Path


class TaskDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.main_window = parent
        self.setWindowTitle(t("panel_task_list"))
        self.setMinimumSize(800, 600)
        self.tasks_dir = Path("tasks")
        self.tasks_dir.mkdir(exist_ok=True)
        self.init_ui()
        self.refresh_task_list()

    def init_ui(self):
        layout = QVBoxLayout(self)

        # 任務列表和詳情
        splitter = QSplitter(Qt.Horizontal)

        # 左側：任務列表
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(5, 5, 5, 5)

        list_label = QLabel(t("panel_task_list"))
        list_label.setStyleSheet("font-weight: bold; font-size: 14px;")
        left_layout.addWidget(list_label)

        self.task_list = QListWidget()
        self.task_list.itemDoubleClicked.connect(self.edit_task)
        left_layout.addWidget(self.task_list)

        # 按鈕行
        btn_layout = QHBoxLayout()

        self.btn_new = QPushButton("➕ " + t("btn_new"))
        self.btn_new.clicked.connect(self.new_task)
        btn_layout.addWidget(self.btn_new)

        self.btn_edit = QPushButton("✏️ " + t("btn_edit"))
        self.btn_edit.clicked.connect(lambda: self.edit_task(self.task_list.currentItem()))
        btn_layout.addWidget(self.btn_edit)

        self.btn_delete = QPushButton("🗑 " + t("btn_delete"))
        self.btn_delete.clicked.connect(self.delete_task)
        btn_layout.addWidget(self.btn_delete)

        left_layout.addLayout(btn_layout)

        self.btn_refresh = QPushButton("🔄 " + t("btn_refresh"))
        self.btn_refresh.clicked.connect(self.refresh_task_list)
        left_layout.addWidget(self.btn_refresh)

        splitter.addWidget(left_widget)

        # 右側：任務詳情
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(5, 5, 5, 5)

        detail_label = QLabel(t("tab_task_detail"))
        detail_label.setStyleSheet("font-weight: bold; font-size: 14px;")
        right_layout.addWidget(detail_label)

        self.detail_text = QTextBrowser()
        self.detail_text.setOpenExternalLinks(True)
        right_layout.addWidget(self.detail_text)

        splitter.addWidget(right_widget)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 2)

        layout.addWidget(splitter)

        # 關閉按鈕
        close_btn = QPushButton(t("btn_ok"))
        close_btn.clicked.connect(self.close)
        layout.addWidget(close_btn)

        # 連接信號
        self.task_list.itemSelectionChanged.connect(self.on_task_selected)

    def refresh_task_list(self):
        """刷新任務列表"""
        self.task_list.clear()
        for task_file in self.tasks_dir.glob("*.json"):
            item = QListWidgetItem(task_file.stem)
            self.task_list.addItem(item)

    def on_task_selected(self):
        """任務選中時顯示詳情"""
        current = self.task_list.currentItem()
        if not current:
            return

        task_name = current.text()
        task_file = self.tasks_dir / f"{task_name}.json"

        if task_file.exists():
            try:
                with open(task_file, 'r', encoding='utf-8') as f:
                    task_data = json.load(f)

                html = f"<h2>{task_data.get('name', task_name)}</h2>"
                html += f"<p><b>{t('detail_domain')}</b> {task_data.get('url', 'N/A')}</p>"
                html += f"<p><b>{t('detail_description')}</b> {task_data.get('description', 'N/A')}</p>"
                html += f"<p><b>{t('detail_steps_count')}</b> {len(task_data.get('steps', []))}</p>"

                self.detail_text.setHtml(html)
            except Exception as e:
                self.detail_text.setHtml(f"<p style='color:red;'>Error: {e}</p>")
        else:
            self.detail_text.clear()

    def new_task(self):
        """新建任務"""
        if self.main_window:
            self.close()
            self.main_window.new_task()

    def edit_task(self, item):
        """編輯任務"""
        if item and self.main_window:
            self.main_window.task_list.setCurrentRow(self.task_list.row(item))
            self.close()
            self.main_window.edit_task(item)

    def delete_task(self):
        """刪除任務"""
        current = self.task_list.currentItem()
        if not current:
            return

        task_name = current.text()
        task_file = self.tasks_dir / f"{task_name}.json"

        from PyQt5.QtWidgets import QMessageBox
        reply = QMessageBox.question(
            self, t("menu_delete_task"),
            f"Delete task '{task_name}'?",
            QMessageBox.Yes | QMessageBox.No
        )

        if reply == QMessageBox.Yes and task_file.exists():
            task_file.unlink()
            self.refresh_task_list()
            self.detail_text.clear()
