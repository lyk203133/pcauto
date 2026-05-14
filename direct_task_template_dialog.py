"""
任務模板管理對話框（管理員功能）
使用本地 task_templates.json 存儲模板，格式與 direct_task_templates 表一致
"""
import json
import uuid
from pathlib import Path

from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QListWidget, QListWidgetItem, QLineEdit, QTextEdit,
    QFormLayout, QFrame, QMessageBox, QSplitter, QWidget,
    QAbstractItemView
)
from PyQt5.QtCore import Qt

TEMPLATES_FILE = Path(__file__).parent / 'task_templates.json'

DIALOG_STYLE = """
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
QListWidget {
    background-color: #FFFFFF;
    border: none;
    border-radius: 10px;
    outline: none;
    font-size: 13px;
}
QListWidget::item {
    padding: 10px 12px;
    border-bottom: 1px solid #F2F2F7;
    color: #1C1C1E;
}
QListWidget::item:selected { background-color: #E5F0FF; color: #007AFF; }
QListWidget::item:hover    { background-color: #F2F2F7; }
QLineEdit {
    background-color: #FFFFFF;
    border: 1px solid #C7C7CC;
    border-radius: 8px;
    padding: 6px 10px;
    font-size: 13px;
    color: #1C1C1E;
    min-height: 26px;
}
QLineEdit:focus { border-color: #007AFF; }
QTextEdit {
    background-color: #FFFFFF;
    border: 1px solid #C7C7CC;
    border-radius: 8px;
    padding: 6px 10px;
    font-size: 12px;
    font-family: 'Menlo', 'SF Mono', 'Consolas', monospace;
    color: #1C1C1E;
}
QTextEdit:focus { border-color: #007AFF; }
QPushButton#primary {
    background-color: #007AFF;
    color: #FFFFFF;
    border: none;
    border-radius: 8px;
    padding: 8px 14px;
    font-size: 13px;
    font-weight: 600;
}
QPushButton#primary:hover  { background-color: #0066DD; }
QPushButton#primary:disabled { background-color: #C7C7CC; }
QPushButton#danger {
    background-color: #FF3B30;
    color: #FFFFFF;
    border: none;
    border-radius: 8px;
    padding: 8px 14px;
    font-size: 13px;
    font-weight: 600;
}
QPushButton#danger:hover  { background-color: #DD2A20; }
QPushButton#danger:disabled { background-color: #C7C7CC; }
QPushButton#secondary {
    background-color: #E5E5EA;
    color: #1C1C1E;
    border: none;
    border-radius: 8px;
    padding: 8px 14px;
    font-size: 13px;
}
QPushButton#secondary:hover  { background-color: #D1D1D6; }
QPushButton#cancel_btn {
    background-color: transparent;
    color: #8E8E93;
    border: 1px solid #C7C7CC;
    border-radius: 8px;
    font-size: 13px;
    padding: 8px 14px;
}
QPushButton#cancel_btn:hover { background-color: #E5E5EA; }
"""


def _load_templates() -> list:
    """從本地 JSON 文件加載模板"""
    if TEMPLATES_FILE.exists():
        try:
            with open(TEMPLATES_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            pass
    return []


def _save_templates(templates: list):
    """保存模板到本地 JSON 文件"""
    with open(TEMPLATES_FILE, 'w', encoding='utf-8') as f:
        json.dump(templates, f, ensure_ascii=False, indent=2)


def _make_btn(text, obj_name='secondary', height=34):
    btn = QPushButton(text)
    btn.setObjectName(obj_name)
    btn.setFixedHeight(height)
    btn.setCursor(Qt.PointingHandCursor)
    return btn


class TemplateEditDialog(QDialog):
    """新建/編輯模板的子對話框"""

    def __init__(self, template: dict = None, parent=None):
        super().__init__(parent)
        self.template = template or {}
        self.result_template = None
        is_new = not bool(template)
        self.setWindowTitle('新建模板' if is_new else '編輯模板')
        self.setMinimumSize(500, 480)
        self.setStyleSheet(DIALOG_STYLE)
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(12)

        title = QLabel('📝 模板資訊')
        title.setStyleSheet('font-size:15px; font-weight:700; color:#1C1C1E;')
        root.addWidget(title)

        form = QFormLayout()
        form.setSpacing(10)

        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText('例：VCB 銀行登入轉帳')
        self.name_input.setText(self.template.get('name', ''))
        form.addRow('模板名稱:', self.name_input)

        self.bank_code_input = QLineEdit()
        self.bank_code_input.setPlaceholderText('例：VCB')
        self.bank_code_input.setText(self.template.get('bank_code', ''))
        form.addRow('銀行代碼:', self.bank_code_input)

        self.site_url_input = QLineEdit()
        self.site_url_input.setPlaceholderText('例：https://vcb.com.vn/login')
        self.site_url_input.setText(self.template.get('site_url', ''))
        form.addRow('目標 URL:', self.site_url_input)

        root.addLayout(form)

        steps_label = QLabel('操作步驟 (JSON 格式):')
        steps_label.setStyleSheet('font-size:12px; color:#3C3C43; font-weight:500;')
        root.addWidget(steps_label)

        self.steps_edit = QTextEdit()
        self.steps_edit.setPlaceholderText(
            '[\n'
            '  {"action": "navigate", "url": "{{site_url}}"},\n'
            '  {"action": "input", "selector": "#username", "value": "{{account}}"},\n'
            '  {"action": "input", "selector": "#password", "value": "{{password}}"},\n'
            '  {"action": "click", "selector": "#login-btn"}\n'
            ']'
        )
        steps_raw = self.template.get('steps', [])
        if isinstance(steps_raw, list):
            self.steps_edit.setPlainText(json.dumps(steps_raw, ensure_ascii=False, indent=2))
        else:
            self.steps_edit.setPlainText(str(steps_raw))
        root.addWidget(self.steps_edit, stretch=1)

        # 按鈕行
        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)

        cancel_btn = _make_btn('取消', 'cancel_btn')
        cancel_btn.clicked.connect(self.reject)

        save_btn = _make_btn('💾 保存', 'primary')
        save_btn.clicked.connect(self._save)

        btn_row.addWidget(cancel_btn)
        btn_row.addStretch()
        btn_row.addWidget(save_btn)
        root.addLayout(btn_row)

    def _save(self):
        name = self.name_input.text().strip()
        bank_code = self.bank_code_input.text().strip().upper()
        site_url = self.site_url_input.text().strip()
        steps_text = self.steps_edit.toPlainText().strip()

        if not name:
            QMessageBox.warning(self, '提示', '請輸入模板名稱')
            return
        if not bank_code:
            QMessageBox.warning(self, '提示', '請輸入銀行代碼')
            return
        if not site_url:
            QMessageBox.warning(self, '提示', '請輸入目標 URL')
            return

        try:
            steps = json.loads(steps_text) if steps_text else []
        except json.JSONDecodeError as e:
            QMessageBox.critical(self, '錯誤', f'步驟 JSON 格式錯誤:\n{e}')
            return

        self.result_template = {
            'id': self.template.get('id', str(uuid.uuid4())[:8]),
            'name': name,
            'bank_code': bank_code,
            'site_url': site_url,
            'steps': steps,
            'is_active': self.template.get('is_active', 1),
        }
        self.accept()


class DirectTaskTemplateDialog(QDialog):
    """任務模板管理主對話框"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle('📝 任務模板管理')
        self.setMinimumSize(640, 500)
        self.setStyleSheet(DIALOG_STYLE)
        self.templates = _load_templates()
        self._build_ui()
        self._refresh_list()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(10)

        # 標題行
        title_row = QHBoxLayout()
        title = QLabel('📝 任務模板管理')
        title.setStyleSheet('font-size:16px; font-weight:700; color:#1C1C1E;')
        title_row.addWidget(title)
        title_row.addStretch()

        hint = QLabel('本地存儲 · task_templates.json')
        hint.setStyleSheet('font-size:11px; color:#8E8E93;')
        title_row.addWidget(hint)
        root.addLayout(title_row)

        # 列表
        self.list_widget = QListWidget()
        self.list_widget.setSelectionMode(QAbstractItemView.SingleSelection)
        self.list_widget.itemSelectionChanged.connect(self._on_selection_changed)
        self.list_widget.itemDoubleClicked.connect(self._edit_template)
        root.addWidget(self.list_widget, stretch=1)

        # 詳情預覽
        self.detail_label = QLabel('選擇模板查看詳情')
        self.detail_label.setStyleSheet(
            'font-size:11px; color:#3C3C43; padding:8px; '
            'background-color:#FFFFFF; border-radius:8px;'
        )
        self.detail_label.setWordWrap(True)
        self.detail_label.setFixedHeight(56)
        root.addWidget(self.detail_label)

        # 操作按鈕行
        btn_row = QHBoxLayout()
        btn_row.setSpacing(6)

        self.btn_new = _make_btn('➕ 新建')
        self.btn_new.clicked.connect(self._new_template)

        self.btn_edit = _make_btn('✏️ 編輯')
        self.btn_edit.clicked.connect(self._edit_template)
        self.btn_edit.setEnabled(False)

        self.btn_delete = _make_btn('🗑 刪除', 'danger')
        self.btn_delete.clicked.connect(self._delete_template)
        self.btn_delete.setEnabled(False)

        close_btn = _make_btn('關閉', 'cancel_btn')
        close_btn.clicked.connect(self.accept)

        btn_row.addWidget(self.btn_new)
        btn_row.addWidget(self.btn_edit)
        btn_row.addWidget(self.btn_delete)
        btn_row.addStretch()
        btn_row.addWidget(close_btn)
        root.addLayout(btn_row)

    def _refresh_list(self):
        self.list_widget.clear()
        for tmpl in self.templates:
            bank = tmpl.get('bank_code', '?')
            name = tmpl.get('name', '未命名')
            steps_count = len(tmpl.get('steps', []))
            active = '✅' if tmpl.get('is_active', 1) else '⏸'
            item = QListWidgetItem(f'  {active}  [{bank}]  {name}  ·  {steps_count} steps')
            item.setData(Qt.UserRole, tmpl.get('id'))
            self.list_widget.addItem(item)

    def _on_selection_changed(self):
        tmpl = self._current_template()
        has_sel = tmpl is not None
        self.btn_edit.setEnabled(has_sel)
        self.btn_delete.setEnabled(has_sel)
        if tmpl:
            bank = tmpl.get('bank_code', '')
            url = tmpl.get('site_url', '')
            steps = len(tmpl.get('steps', []))
            active_str = '啟用' if tmpl.get('is_active', 1) else '停用'
            self.detail_label.setText(
                f"銀行: {bank}  ·  URL: {url}  ·  步驟: {steps}  ·  狀態: {active_str}"
            )
        else:
            self.detail_label.setText('選擇模板查看詳情')

    def _current_template(self):
        item = self.list_widget.currentItem()
        if not item:
            return None
        tid = item.data(Qt.UserRole)
        for tmpl in self.templates:
            if str(tmpl.get('id')) == str(tid):
                return tmpl
        return None

    def _new_template(self):
        dlg = TemplateEditDialog(parent=self)
        if dlg.exec_() == QDialog.Accepted and dlg.result_template:
            self.templates.append(dlg.result_template)
            _save_templates(self.templates)
            self._refresh_list()

    def _edit_template(self):
        tmpl = self._current_template()
        if not tmpl:
            return
        dlg = TemplateEditDialog(template=tmpl, parent=self)
        if dlg.exec_() == QDialog.Accepted and dlg.result_template:
            # 替換原模板
            for i, t in enumerate(self.templates):
                if str(t.get('id')) == str(tmpl.get('id')):
                    self.templates[i] = dlg.result_template
                    break
            _save_templates(self.templates)
            self._refresh_list()

    def _delete_template(self):
        tmpl = self._current_template()
        if not tmpl:
            return
        name = tmpl.get('name', '未命名')
        reply = QMessageBox.question(
            self, '確認刪除',
            f'確定刪除模板「{name}」嗎？',
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            self.templates = [
                t for t in self.templates
                if str(t.get('id')) != str(tmpl.get('id'))
            ]
            _save_templates(self.templates)
            self._refresh_list()
            self.detail_label.setText('選擇模板查看詳情')
