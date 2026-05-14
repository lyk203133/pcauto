"""
步驟編輯對話框
"""

from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGroupBox, QLabel,
    QComboBox, QLineEdit, QTextEdit, QScrollArea, QFrame,
    QDialogButtonBox, QWidget
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont

from models import TaskStep
from i18n import (
    t, get_scroll_presets, get_wait_presets, get_selector_types,
    get_common_selectors, get_step_wait_presets, get_preset_custom_key
)


class StepEditDialog(QDialog):
    """步驟編輯對話框 - 使用下拉選項"""

    def __init__(self, step=None, parent=None):
        super().__init__(parent)
        self.step = step or TaskStep('goto', {'url': 'https://example.com', 'wait': '2'})
        self.param_widgets = {}
        self.setup_ui()

    def setup_ui(self):
        self.setWindowTitle(t("dialog_edit_step"))
        self.setMinimumSize(600, 450)

        layout = QVBoxLayout(self)

        # 步驟類型選擇
        type_group = QGroupBox(t("dialog_step_type"))
        type_layout = QHBoxLayout()

        self.type_combo = QComboBox()
        for t_key, info in TaskStep.STEP_TYPES.items():
            label = t(info['label_key'])
            self.type_combo.addItem(label, t_key)
        self.type_combo.currentIndexChanged.connect(self._on_type_changed)
        type_layout.addWidget(self.type_combo)
        type_group.setLayout(type_layout)
        layout.addWidget(type_group)

        # 參數編輯區域（帶滾動）
        params_scroll = QScrollArea()
        params_scroll.setWidgetResizable(True)
        params_scroll.setFrameShape(QFrame.NoFrame)

        self.params_widget = QWidget()
        self.params_layout = QVBoxLayout(self.params_widget)
        params_scroll.setWidget(self.params_widget)

        params_group = QGroupBox(t("dialog_edit_params"))
        params_group_layout = QVBoxLayout()
        params_group_layout.addWidget(params_scroll)
        params_group.setLayout(params_group_layout)
        layout.addWidget(params_group)

        # 步驟後等待時間
        wait_group = QGroupBox(t("param_wait_after"))
        wait_layout = QHBoxLayout()

        self.wait_combo = QComboBox()
        self.wait_combo.setEditable(True)
        self.wait_combo.setInsertPolicy(QComboBox.NoInsert)
        self._populate_wait_presets()
        wait_layout.addWidget(self.wait_combo)
        wait_layout.addWidget(QLabel(t("detail_seconds")))
        wait_group.setLayout(wait_layout)
        layout.addWidget(wait_group)

        # 按鈕
        btn_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btn_box.accepted.connect(self.accept)
        btn_box.rejected.connect(self.reject)
        layout.addWidget(btn_box)

        # 加載當前步驟
        if self.step.type in TaskStep.STEP_TYPES:
            idx = list(TaskStep.STEP_TYPES.keys()).index(self.step.type)
            self.type_combo.setCurrentIndex(idx)

        # 設置等待時間
        wait_val = self.step.params.get('wait', '2') or '2'
        self._set_wait_combo_value(wait_val)

        self._update_params_ui()

    def _populate_wait_presets(self):
        """填充等待時間預設"""
        self.wait_combo.clear()
        for val, label in get_step_wait_presets():
            self.wait_combo.addItem(label, val)
        self.wait_combo.addItem(t(get_preset_custom_key()), "CUSTOM")

    def _set_wait_combo_value(self, value: str):
        """設置等待時間下拉框的值"""
        for i in range(self.wait_combo.count()):
            if self.wait_combo.itemData(i) == value:
                self.wait_combo.setCurrentIndex(i)
                return
        self.wait_combo.setCurrentText(value)

    def _on_type_changed(self):
        self._update_params_ui()

    def _update_params_ui(self):
        """更新參數 UI"""
        while self.params_layout.count():
            child = self.params_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        step_type = self.type_combo.currentData()
        param_defs = TaskStep.STEP_TYPES.get(step_type, {}).get('params', [])

        self.param_widgets = {}

        for param in param_defs:
            if param == 'wait':
                continue

            param_widget = self._create_param_widget(step_type, param)
            self.params_layout.addWidget(param_widget)
            self.param_widgets[param] = param_widget

        self.params_layout.addStretch()

    def _create_param_widget(self, step_type: str, param: str) -> QWidget:
        """根據參數類型創建相應的控件"""
        widget = QWidget()
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(0, 5, 0, 5)

        if step_type == 'goto' and param == 'url':
            label = QLabel(t("param_url") + ":")
            input_widget = QLineEdit()
            input_widget.setText(self.step.params.get(param, ''))
            input_widget.setPlaceholderText("https://example.com")
            layout.addWidget(label)
            layout.addWidget(input_widget)
            self.param_widgets[param] = input_widget

        elif step_type in ['click', 'hover'] and param == 'selector':
            self._add_selector_widget(layout, param)

        elif step_type in ['fill', 'type'] and param == 'selector':
            self._add_selector_widget(layout, param)

        elif step_type in ['fill', 'type'] and param == 'value':
            label = QLabel(t("param_value") + ":")
            input_widget = QLineEdit()
            input_widget.setText(self.step.params.get(param, ''))
            input_widget.setPlaceholderText(t("dialog_desc_placeholder"))
            layout.addWidget(label)
            layout.addWidget(input_widget)
            self.param_widgets[param] = input_widget

        elif step_type in ['scroll_down', 'scroll_up'] and param == 'amount':
            label = QLabel(t("param_amount") + ":")
            combo = QComboBox()
            combo.setEditable(True)
            combo.setInsertPolicy(QComboBox.NoInsert)

            for val, display in get_scroll_presets():
                combo.addItem(display, val)

            current_val = self.step.params.get(param, '500')
            found = False
            for i in range(combo.count()):
                if combo.itemData(i) == current_val:
                    combo.setCurrentIndex(i)
                    found = True
                    break
            if not found:
                combo.setCurrentText(current_val)

            layout.addWidget(label)
            layout.addWidget(combo)
            self.param_widgets[param] = combo

        elif step_type == 'screenshot' and param == 'name':
            label = QLabel(t("param_name") + ":")
            input_widget = QLineEdit()
            input_widget.setText(self.step.params.get(param, ''))
            input_widget.setPlaceholderText("screenshot_001")
            layout.addWidget(label)
            layout.addWidget(input_widget)
            self.param_widgets[param] = input_widget

        elif step_type == 'wait' and param == 'seconds':
            label = QLabel(t("param_seconds") + ":")
            combo = QComboBox()
            combo.setEditable(True)
            combo.setInsertPolicy(QComboBox.NoInsert)

            for val, display in get_wait_presets():
                combo.addItem(display, val)

            current_val = self.step.params.get(param, '2')
            found = False
            for i in range(combo.count()):
                if combo.itemData(i) == current_val:
                    combo.setCurrentIndex(i)
                    found = True
                    break
            if not found:
                combo.setCurrentText(current_val)

            layout.addWidget(label)
            layout.addWidget(combo)
            self.param_widgets[param] = combo

        elif step_type == 'js' and param == 'code':
            label = QLabel(t("param_code") + ":")
            input_widget = QTextEdit()
            input_widget.setPlainText(self.step.params.get(param, ''))
            input_widget.setPlaceholderText("document.body.style.background = 'red';")
            input_widget.setMaximumHeight(100)
            input_widget.setFont(QFont("Consolas", 10))
            layout.addWidget(label)
            layout.addWidget(input_widget)
            self.param_widgets[param] = input_widget

        else:
            label = QLabel(f"{param}:")
            input_widget = QLineEdit()
            input_widget.setText(self.step.params.get(param, ''))
            layout.addWidget(label)
            layout.addWidget(input_widget)
            self.param_widgets[param] = input_widget

        return widget

    def _add_selector_widget(self, layout: QHBoxLayout, param: str):
        """添加選擇器控件（下拉 + 輸入）"""
        label = QLabel(t("param_selector") + ":")
        layout.addWidget(label)

        type_combo = QComboBox()
        for val, display in get_selector_types():
            type_combo.addItem(display, val)
        type_combo.currentIndexChanged.connect(self._on_selector_type_changed)
        layout.addWidget(type_combo)

        selector_combo = QComboBox()
        selector_combo.setEditable(True)
        selector_combo.setInsertPolicy(QComboBox.NoInsert)
        self._populate_common_selectors(selector_combo)

        current_val = self.step.params.get(param, '')
        self._set_selector_value(selector_combo, current_val)

        layout.addWidget(selector_combo)

        if param not in self.param_widgets:
            self.param_widgets[param] = {}

        self.param_widgets[param]['type'] = type_combo
        self.param_widgets[param]['selector'] = selector_combo

    def _populate_common_selectors(self, combo: QComboBox):
        """填充常用選擇器預設"""
        combo.clear()
        combo.addItem("-- " + t("common_btn_submit") + " --", "#submit")

        for val, key in get_common_selectors():
            combo.addItem(t(key), val)

        combo.addItem("-- " + t(get_preset_custom_key()) + " --", "CUSTOM")

    def _set_selector_value(self, combo: QComboBox, value: str):
        """設置選擇器的值"""
        for i in range(combo.count()):
            if combo.itemData(i) == value:
                combo.setCurrentIndex(i)
                return
        combo.setCurrentText(value)

    def _on_selector_type_changed(self):
        pass

    def get_step(self) -> TaskStep:
        step_type = self.type_combo.currentData()
        params = {}

        for param, widget in self.param_widgets.items():
            if isinstance(widget, dict):
                selector_combo = widget.get('selector')
                if selector_combo:
                    params[param] = selector_combo.currentText()
            elif isinstance(widget, QComboBox):
                data = widget.currentData()
                if data and data != "CUSTOM":
                    params[param] = data
                else:
                    params[param] = widget.currentText()
            elif isinstance(widget, QLineEdit):
                params[param] = widget.text()
            elif isinstance(widget, QTextEdit):
                params[param] = widget.toPlainText()
            else:
                params[param] = str(widget)

        wait_data = self.wait_combo.currentData()
        if wait_data and wait_data != "CUSTOM":
            params['wait'] = wait_data
        else:
            try:
                params['wait'] = str(int(float(self.wait_combo.currentText())))
            except:
                params['wait'] = '2'

        return TaskStep(step_type, params)
