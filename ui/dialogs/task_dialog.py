"""
任務編輯對話框
"""

from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QGroupBox,
    QLineEdit, QTextEdit, QTableWidget, QTableWidgetItem,
    QHeaderView, QPushButton, QDialogButtonBox, QMessageBox
)

from models import TaskStep, SiteTask
from i18n import t
from ui.dialogs.step_dialog import StepEditDialog


class TaskEditDialog(QDialog):
    """任務編輯對話框"""

    def __init__(self, task=None, parent=None):
        super().__init__(parent)
        self.task = task or SiteTask()
        self.step_dialogs = []
        self.setup_ui()

    def setup_ui(self):
        title_key = "dialog_edit_task" if self.task.domain else "dialog_new_task"
        self.setWindowTitle(t(title_key))
        self.setMinimumSize(900, 650)

        layout = QVBoxLayout(self)

        # 基本資訊
        info_group = QGroupBox(t("dialog_task_info"))
        info_layout = QFormLayout()

        self.name_edit = QLineEdit(self.task.name)
        self.name_edit.setPlaceholderText(t("dialog_task_name_placeholder"))
        info_layout.addRow(t("dialog_task_name"), self.name_edit)

        self.domain_edit = QLineEdit(self.task.domain)
        self.domain_edit.setPlaceholderText(t("dialog_domain_placeholder"))
        info_layout.addRow(t("dialog_domain"), self.domain_edit)

        self.desc_edit = QTextEdit(self.task.description)
        self.desc_edit.setPlaceholderText(t("dialog_desc_placeholder"))
        self.desc_edit.setMaximumHeight(60)
        info_layout.addRow(t("dialog_description"), self.desc_edit)

        info_group.setLayout(info_layout)
        layout.addWidget(info_group)

        # 步驟列表
        steps_group = QGroupBox(t("dialog_steps"))
        steps_layout = QVBoxLayout()

        self.steps_table = QTableWidget()
        self.steps_table.setColumnCount(4)
        self.steps_table.setHorizontalHeaderLabels([
            t("dialog_col_index"),
            t("dialog_col_type"),
            t("dialog_col_params"),
            t("dialog_col_wait")
        ])
        self.steps_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.steps_table.setColumnWidth(0, 50)
        self.steps_table.setColumnWidth(1, 150)
        self.steps_table.setColumnWidth(3, 80)
        self.steps_table.setMaximumHeight(250)

        for i, step in enumerate(self.task.steps):
            self._add_step_row(i, step)

        steps_layout.addWidget(self.steps_table)

        btn_layout = QHBoxLayout()

        add_btn = QPushButton(t("dialog_btn_add_step"))
        add_btn.clicked.connect(self._add_step)
        btn_layout.addWidget(add_btn)

        edit_btn = QPushButton(t("btn_edit"))
        edit_btn.clicked.connect(self._edit_step)
        btn_layout.addWidget(edit_btn)

        remove_btn = QPushButton(t("dialog_btn_remove_step"))
        remove_btn.clicked.connect(self._remove_step)
        btn_layout.addWidget(remove_btn)

        move_up_btn = QPushButton(t("dialog_btn_move_up"))
        move_up_btn.clicked.connect(self._move_step_up)
        btn_layout.addWidget(move_up_btn)

        move_down_btn = QPushButton(t("dialog_btn_move_down"))
        move_down_btn.clicked.connect(self._move_step_down)
        btn_layout.addWidget(move_down_btn)

        steps_layout.addLayout(btn_layout)
        steps_group.setLayout(steps_layout)
        layout.addWidget(steps_group)

        btn_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btn_box.accepted.connect(self._save)
        btn_box.rejected.connect(self.reject)
        layout.addWidget(btn_box)

    def _add_step_row(self, row, step):
        self.steps_table.insertRow(row)

        self.steps_table.setItem(row, 0, QTableWidgetItem(str(row + 1)))
        self.steps_table.setItem(row, 1, QTableWidgetItem(step.get_label()))

        params_text = self._get_params_summary(step)
        self.steps_table.setItem(row, 2, QTableWidgetItem(params_text))

        wait = step.params.get('wait', '1') or '1'
        self.steps_table.setItem(row, 3, QTableWidgetItem(f"{wait}s"))

    def _get_params_summary(self, step) -> str:
        """獲取參數摘要"""
        if step.type == 'goto':
            url = step.params.get('url', '')
            return url[:40] + ('...' if len(url) > 40 else '')
        elif step.type in ['click', 'hover']:
            return step.params.get('selector', '')[:40]
        elif step.type in ['fill', 'type']:
            selector = step.params.get('selector', '')
            value = step.params.get('value', '')
            return f"{selector[:20]}... → {value[:15]}..."
        elif step.type in ['scroll_down', 'scroll_up']:
            return f"{step.params.get('amount', '500')}px"
        elif step.type == 'screenshot':
            return step.params.get('name', '')
        elif step.type == 'wait':
            return f"{step.params.get('seconds', '1')}s"
        elif step.type == 'js':
            code = step.params.get('code', '')
            return code[:40] + ('...' if len(code) > 40 else '')
        return ""

    def _add_step(self):
        dialog = StepEditDialog(parent=self)
        if dialog.exec_():
            step = dialog.get_step()
            row = self.steps_table.rowCount()
            self._add_step_row(row, step)
            self.step_dialogs.append((row, step))
            self._renumber_rows()

    def _edit_step(self):
        row = self.steps_table.currentRow()
        if row < 0:
            QMessageBox.warning(self, t("msg_warning"), "請先選擇要編輯的步驟")
            return

        step = self._get_step_from_row(row)
        dialog = StepEditDialog(step, self)
        if dialog.exec_():
            new_step = dialog.get_step()
            self._update_step_row(row, new_step)

    def _update_step_row(self, row, step):
        self.steps_table.item(row, 1).setText(step.get_label())
        self.steps_table.item(row, 2).setText(self._get_params_summary(step))
        self.steps_table.item(row, 3).setText(f"{step.params.get('wait', '1')}s")

    def _get_step_from_row(self, row) -> TaskStep:
        step_data = self._collect_all_steps()
        if row < len(step_data):
            return step_data[row]
        return TaskStep('goto', {'url': 'https://example.com', 'wait': '2'})

    def _collect_all_steps(self) -> list:
        steps = []
        for i in range(self.steps_table.rowCount()):
            step_type = 'goto'
            params = {'url': '', 'wait': '2'}

            for saved_row, saved_step in self.step_dialogs:
                if saved_row == i:
                    steps.append(saved_step)
                    break
            else:
                steps.append(TaskStep(step_type, params))
        return steps

    def _remove_step(self):
        row = self.steps_table.currentRow()
        if row >= 0:
            self.steps_table.removeRow(row)
            new_dialogs = []
            for saved_row, saved_step in self.step_dialogs:
                if saved_row < row:
                    new_dialogs.append((saved_row, saved_step))
                elif saved_row > row:
                    new_dialogs.append((saved_row - 1, saved_step))
            self.step_dialogs = new_dialogs
            self._renumber_rows()

    def _move_step_up(self):
        row = self.steps_table.currentRow()
        if row > 0:
            self._swap_rows(row, row - 1)
            self.steps_table.selectRow(row - 1)

    def _move_step_down(self):
        row = self.steps_table.currentRow()
        if row < self.steps_table.rowCount() - 1:
            self._swap_rows(row, row + 1)
            self.steps_table.selectRow(row + 1)

    def _swap_rows(self, r1, r2):
        for col in range(self.steps_table.columnCount()):
            item1 = self.steps_table.takeItem(r1, col)
            item2 = self.steps_table.takeItem(r2, col)
            if item1:
                self.steps_table.setItem(r2, col, item1)
            if item2:
                self.steps_table.setItem(r1, col, item2)

        dialog_map = {}
        for saved_row, saved_step in self.step_dialogs:
            dialog_map[saved_row] = saved_step

        temp = dialog_map.get(r1)
        dialog_map[r1] = dialog_map.get(r2)
        dialog_map[r2] = temp

        self.step_dialogs = [(r, dialog_map[r]) for r in sorted(dialog_map.keys())]
        self._renumber_rows()

    def _renumber_rows(self):
        for i in range(self.steps_table.rowCount()):
            self.steps_table.setItem(i, 0, QTableWidgetItem(str(i + 1)))

    def _save(self):
        name = self.name_edit.text().strip()
        domain = self.domain_edit.text().strip()

        if not name:
            QMessageBox.warning(self, t("msg_warning"), t("msg_enter_task_name"))
            return
        if not domain:
            QMessageBox.warning(self, t("msg_warning"), t("msg_enter_domain"))
            return

        self.task.name = name
        self.task.domain = domain
        self.task.description = self.desc_edit.toPlainText().strip()

        self.task.steps = []
        for i in range(self.steps_table.rowCount()):
            step = None
            for saved_row, saved_step in self.step_dialogs:
                if saved_row == i:
                    step = saved_step
                    break

            if not step:
                step = TaskStep('goto', {'url': 'https://example.com', 'wait': '2'})

            self.task.steps.append(step)

        self.accept()

    def get_task(self) -> SiteTask:
        return self.task
