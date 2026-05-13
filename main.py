"""
自動化瀏覽器工具 - 主程序
基於 CloakBrowser + PyQt5 的 Windows 桌面應用
支持驗證碼檢測和用戶介入填寫
支持多國語言：繁體中文、英文、越南文
支持參數下拉選項預設
支持 MySQL 資料庫訂單監控

任務設計：一個網站 = 一個任務文件
"""

import sys
import json
import os
import time
import random
import logging
from datetime import datetime
from pathlib import Path

from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QTextEdit, QLineEdit, QLabel, QComboBox,
    QFileDialog, QMessageBox, QGroupBox, QCheckBox, QSpinBox,
    QStatusBar, QMenuBar, QMenu, QAction, QTabWidget, QTableWidget,
    QTableWidgetItem, QHeaderView, QSplitter, QToolBar, QListWidget,
    QListWidgetItem, QDialog, QFormLayout, QDialogButtonBox, QTextBrowser,
    QFrame, QScrollArea, QSizePolicy, QDoubleSpinBox
)
from PyQt5.QtCore import QThread, pyqtSignal, Qt, QSize, QDir, QTimer
from PyQt5.QtGui import QFont, QIcon, QTextCursor, QColor

from cloakbrowser import launch
import i18n
from i18n import (
    t, set_language, get_current_lang,
    get_scroll_presets, get_wait_presets, get_selector_types,
    get_common_selectors, get_step_wait_presets, get_preset_custom_key
)
from database import DatabaseManager, OrderMonitor, DEFAULT_DB_CONFIG

# 配置日誌
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('automation.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# 任務文件目錄
TASKS_DIR = "tasks"


class TaskStep:
    """任務步驟"""
    STEP_TYPES = {
        'goto': {'label_key': 'step_goto', 'params': ['url', 'wait']},
        'click': {'label_key': 'step_click', 'params': ['selector', 'wait']},
        'fill': {'label_key': 'step_fill', 'params': ['selector', 'value', 'wait']},
        'type': {'label_key': 'step_type', 'params': ['selector', 'value', 'wait']},
        'hover': {'label_key': 'step_hover', 'params': ['selector', 'wait']},
        'scroll_down': {'label_key': 'step_scroll_down', 'params': ['amount', 'wait']},
        'scroll_up': {'label_key': 'step_scroll_up', 'params': ['amount', 'wait']},
        'screenshot': {'label_key': 'step_screenshot', 'params': ['name', 'wait']},
        'wait': {'label_key': 'step_wait', 'params': ['seconds']},
        'js': {'label_key': 'step_js', 'params': ['code']},
    }

    def __init__(self, step_type='goto', params=None):
        self.type = step_type
        self.params = params or {k: '' for k in self.STEP_TYPES[step_type]['params']}

    def get_label(self):
        """獲取翻譯後的標籤"""
        label_key = self.STEP_TYPES.get(self.type, {}).get('label_key', '')
        return t(label_key)

    def to_dict(self):
        d = {'type': self.type}
        d.update(self.params)
        return d

    @staticmethod
    def from_dict(d):
        params = {k: d.get(k, '') for k in TaskStep.STEP_TYPES[d['type']]['params']}
        return TaskStep(d['type'], params)


class SiteTask:
    """網站任務"""
    def __init__(self):
        self.name = ''           # 任務名稱
        self.domain = ''         # 域名
        self.description = ''   # 描述
        self.steps = []          # 步驟列表
        self.enabled = True      # 是否啟用
        self.created_at = datetime.now().isoformat()
        self.updated_at = datetime.now().isoformat()

    def to_dict(self):
        return {
            'name': self.name,
            'domain': self.domain,
            'description': self.description,
            'enabled': self.enabled,
            'steps': [s.to_dict() if isinstance(s, TaskStep) else s for s in self.steps],
            'created_at': self.created_at,
            'updated_at': datetime.now().isoformat()
        }

    @staticmethod
    def from_dict(d):
        task = SiteTask()
        task.name = d.get('name', '')
        task.domain = d.get('domain', '')
        task.description = d.get('description', '')
        task.enabled = d.get('enabled', True)
        task.created_at = d.get('created_at', datetime.now().isoformat())
        task.steps = [TaskStep.from_dict(s) for s in d.get('steps', [])]
        return task


class TaskManager:
    """任務管理器"""
    def __init__(self, tasks_dir=TASKS_DIR):
        self.tasks_dir = Path(tasks_dir)
        self.tasks_dir.mkdir(exist_ok=True)
        self.tasks = {}
        self.load_all()

    def load_all(self):
        """加載所有任務"""
        self.tasks = {}
        for f in self.tasks_dir.glob('*.json'):
            try:
                with open(f, 'r', encoding='utf-8') as fp:
                    task = SiteTask.from_dict(json.load(fp))
                    self.tasks[task.domain] = task
            except Exception as e:
                logger.error(f"加載任務失敗 {f}: {e}")

    def save(self, task: SiteTask):
        """保存任務"""
        filename = self._safe_filename(task.domain) + '.json'
        filepath = self.tasks_dir / filename
        with open(filepath, 'w', encoding='utf-8') as fp:
            json.dump(task.to_dict(), fp, ensure_ascii=False, indent=2)
        self.tasks[task.domain] = task

    def delete(self, domain: str):
        """刪除任務"""
        if domain in self.tasks:
            filename = self._safe_filename(domain) + '.json'
            filepath = self.tasks_dir / filename
            if filepath.exists():
                filepath.unlink()
            del self.tasks[domain]

    def get(self, domain: str) -> SiteTask:
        return self.tasks.get(domain)

    def _safe_filename(self, domain: str) -> str:
        return domain.replace('/', '_').replace('\\', '_').replace(':', '_')


class BrowserThread(QThread):
    """瀏覽器操作線程"""

    log_signal = pyqtSignal(str)
    status_signal = pyqtSignal(str)
    captcha_signal = pyqtSignal(str)
    captcha_resolved_signal = pyqtSignal()
    task_complete_signal = pyqtSignal(bool, str, str)  # success, message, order_no
    step_signal = pyqtSignal(int, int)  # 當前步驟, 總步驟

    def __init__(self, config: dict, task: SiteTask, order_no: str = None):
        super().__init__()
        self.config = config
        self.task = task
        self.order_no = order_no  # 訂單號
        self.browser = None
        self.page = None
        self.is_running = False
        self.is_paused = False
        self.should_stop = False
        self._stop_requested = False

    def run(self):
        self.is_running = True
        self.should_stop = False
        self._stop_requested = False

        try:
            self._init_browser()
            self._execute_steps()
        except Exception as e:
            import traceback
            logger.error(f"執行出錯: {e}")
            logger.error(traceback.format_exc())
            self.log_signal.emit(t("error_execute", error=e))
            error_msg = str(e)
            if "Broken pipe" in error_msg or "connection" in error_msg.lower():
                self.log_signal.emit(t("error_network_hint"))
            self.task_complete_signal.emit(False, error_msg, self.order_no)
        finally:
            self._cleanup()

    def _init_browser(self):
        self.log_signal.emit(t("browser_starting"))

        browser_type = self.config.get('browser_type', 'cloakbrowser')

        if browser_type == 'chrome':
            self._init_chrome()
        else:
            self._init_cloakbrowser()

    def _init_chrome(self):
        """使用系統 Chrome 瀏覽器"""
        from playwright.sync_api import sync_playwright

        self.log_signal.emit(t("browser_using_chrome"))

        import subprocess
        import os

        chrome_paths = []
        if os.name == 'nt':
            program_files = os.environ.get('ProgramFiles', 'C:\\Program Files')
            program_files_x86 = os.environ.get('ProgramFiles(x86)', 'C:\\Program Files (x86)')
            local_appdata = os.environ.get('LOCALAPPDATA', os.path.expanduser('~\\AppData\\Local'))

            chrome_paths = [
                os.path.join(program_files, 'Google', 'Chrome', 'Application', 'chrome.exe'),
                os.path.join(program_files_x86, 'Google', 'Chrome', 'Application', 'chrome.exe'),
                os.path.join(local_appdata, 'Google', 'Chrome', 'Application', 'chrome.exe'),
                'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe',
                'C:\\Program Files (x86)\\Google\\Chrome\\Application\\chrome.exe',
            ]

            try:
                result = subprocess.run(
                    ['reg', 'query', 'HKEY_LOCAL_MACHINE\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\App Paths\\chrome.exe'],
                    capture_output=True, text=True
                )
                for line in result.stdout.split('\n'):
                    if 'Path' in line:
                        path = line.split('REG_SZ')[-1].strip()
                        if path:
                            chrome_paths.insert(0, os.path.join(path, 'chrome.exe'))
            except:
                pass

        executable_path = None
        for path in chrome_paths:
            if os.path.exists(path):
                executable_path = path
                break

        if executable_path:
            self.log_signal.emit(t("browser_found_chrome", path=executable_path))

        max_retries = 3
        for attempt in range(max_retries):
            try:
                self.log_signal.emit(t("browser_attempt", current=attempt + 1, total=max_retries))

                pw = sync_playwright().start()

                launch_options = {
                    'headless': False,
                    'args': [
                        '--start-maximized',
                        '--disable-blink-features=AutomationControlled',
                    ]
                }

                if executable_path:
                    launch_options['executable_path'] = executable_path

                if self.config.get('proxy'):
                    launch_options['proxy'] = {
                        'server': self.config['proxy'].replace('http://', '').replace('https://', '').replace('socks5://', 'socks5://')
                    }
                    self.log_signal.emit(t("proxy_using", proxy=self.config['proxy']))

                self.browser = pw.chromium.launch(**launch_options)
                self.page = self.browser.new_page()

                self.page.add_init_script("""
                    Object.defineProperty(navigator, 'webdriver', {
                        get: () => undefined
                    });
                """)

                self.log_signal.emit(t("browser_chrome_success"))
                self.status_signal.emit(t("status_running"))
                return

            except Exception as e:
                try:
                    pw.stop()
                except:
                    pass
                if attempt < max_retries - 1:
                    self.log_signal.emit(t("browser_start_failed_retry", error=str(e)))
                    time.sleep(2)
                else:
                    raise

    def _init_cloakbrowser(self):
        """使用 CloakBrowser 隱身瀏覽器"""
        self.log_signal.emit(t("browser_using_cloak"))
        self.log_signal.emit(t("browser_first_run_hint"))

        launch_kwargs = {
            'headless': False,
            'humanize': self.config.get('humanize', True),
        }

        if self.config.get('proxy'):
            launch_kwargs['proxy'] = self.config['proxy']
            self.log_signal.emit(t("proxy_using", proxy=self.config['proxy']))

        if self.config.get('geoip', False):
            launch_kwargs['geoip'] = True
            self.log_signal.emit(t("geoip_enabled"))

        if not self.config.get('proxy'):
            self.log_signal.emit(t("local_mode"))

        max_retries = 3
        for attempt in range(max_retries):
            try:
                self.log_signal.emit(t("browser_attempt", current=attempt + 1, total=max_retries))
                self.browser = launch(**launch_kwargs)
                self.page = self.browser.new_page()
                self.log_signal.emit(t("browser_cloak_success"))
                self.status_signal.emit(t("status_running"))
                return
            except Exception as e:
                if attempt < max_retries - 1:
                    self.log_signal.emit(t("browser_start_failed"))
                    time.sleep(2)
                else:
                    raise

    def _execute_steps(self):
        steps = [s.to_dict() if isinstance(s, TaskStep) else s for s in self.task.steps]
        total = len(steps)

        self.log_signal.emit(t("task_start", name=self.task.name))
        if self.order_no:
            self.log_signal.emit(t("task_order_no", order_no=self.order_no))
        self.log_signal.emit(t("task_target", domain=self.task.domain))
        self.log_signal.emit(t("task_total_steps", count=total))
        self.log_signal.emit("-" * 40)

        for idx, step in enumerate(steps):
            if self.should_stop or self._stop_requested:
                self.log_signal.emit(t("msg_user_stopped"))
                break

            while self.is_paused and not self.should_stop:
                time.sleep(0.5)
                if self.should_stop:
                    break

            self.step_signal.emit(idx + 1, total)
            self.log_signal.emit(t("step_executing", current=idx + 1, total=total))

            if self._check_captcha():
                self._handle_captcha()

            success = self._execute_step(step)
            if success:
                self.log_signal.emit(t("step_complete", current=idx + 1))
            else:
                self.log_signal.emit(t("step_may_failed", current=idx + 1))

            wait_time = float(step.get('wait', 1) or 1)
            time.sleep(wait_time + random.uniform(0.2, 0.5))

        if not self.should_stop:
            self.log_signal.emit("-" * 40)
            self.log_signal.emit(t("msg_task_complete"))
            self.task_complete_signal.emit(True, t("msg_task_complete"), self.order_no)

    def _check_captcha(self) -> bool:
        captcha_selectors = [
            '.g-recaptcha', '[data-sitekey]', '.cf-turnstile',
            '#hcaptcha', '.h-captcha', '#captcha', '.captcha-container',
            'iframe[src*="captcha"]', '.challenge-form',
        ]

        for selector in captcha_selectors:
            try:
                if self.page.locator(selector).is_visible(timeout=500):
                    return True
            except:
                continue
        return False

    def _handle_captcha(self):
        self.log_signal.emit(t("captcha_detected"))
        self.captcha_signal.emit(t("captcha_hint"))

        while self._check_captcha():
            if self.should_stop:
                return
            time.sleep(1)

        self.log_signal.emit(t("captcha_resolved"))
        self.captcha_resolved_signal.emit()

    def _execute_step(self, step: dict, timeout: int = 10) -> bool:
        """執行單個步驟，帶超時和停止檢查"""
        step_type = step.get('type', '')

        if self.should_stop or self._stop_requested:
            return False

        try:
            if step_type == 'goto':
                url = step.get('url', '')
                self.page.goto(url, timeout=timeout * 1000)
                self.log_signal.emit(t("log_goto", url=url))

            elif step_type == 'click':
                selector = step.get('selector', '')
                self.page.click(selector, timeout=timeout * 1000)
                self.log_signal.emit(t("log_click", selector=selector))

            elif step_type == 'fill':
                selector = step.get('selector', '')
                value = step.get('value', '')
                self.page.fill(selector, value, timeout=timeout * 1000)
                self.log_signal.emit(t("log_fill", selector=selector, value=value[:20]))

            elif step_type == 'type':
                selector = step.get('selector', '')
                value = step.get('value', '')
                self.page.type(selector, value, delay=random.randint(50, 150), timeout=timeout * 1000)
                self.log_signal.emit(t("log_type", selector=selector))

            elif step_type == 'hover':
                selector = step.get('selector', '')
                self.page.hover(selector, timeout=timeout * 1000)
                self.log_signal.emit(t("log_hover", selector=selector))

            elif step_type == 'scroll_down':
                amount = int(step.get('amount', 500))
                self.page.mouse.wheel(0, amount)
                self.log_signal.emit(t("log_scroll_down", amount=amount))

            elif step_type == 'scroll_up':
                amount = int(step.get('amount', 500))
                self.page.mouse.wheel(0, -amount)
                self.log_signal.emit(t("log_scroll_up", amount=amount))

            elif step_type == 'screenshot':
                name = step.get('name', f'screenshot_{datetime.now().strftime("%H%M%S")}')
                path = f'{name}.png'
                self.page.screenshot(path=path)
                self.log_signal.emit(t("log_screenshot", path=path))

            elif step_type == 'wait':
                seconds = float(step.get('seconds', 1))
                self.log_signal.emit(t("log_wait", seconds=seconds))
                for _ in range(int(seconds)):
                    if self.should_stop or self._stop_requested:
                        return False
                    time.sleep(1)
                remaining = seconds - int(seconds)
                if remaining > 0:
                    time.sleep(remaining)
                if self.should_stop or self._stop_requested:
                    return False

            elif step_type == 'js':
                code = step.get('code', '')
                self.page.evaluate(code)
                self.log_signal.emit(t("log_js"))

            return True

        except Exception as e:
            error_msg = str(e)
            if self.should_stop or self._stop_requested:
                self.log_signal.emit(t("step_stopped"))
                return False
            self.log_signal.emit(t("step_execute_failed", error=error_msg))
            return False

    def _cleanup(self):
        try:
            if self.browser:
                self.browser.close()
        except:
            pass
        self.is_running = False
        self.status_signal.emit(t("status_stopped"))

    def stop(self):
        """立即停止執行"""
        self.should_stop = True
        self._stop_requested = True
        self.is_paused = False
        self.log_signal.emit(t("status_stopping"))

        if self.browser:
            try:
                for context in self.browser.contexts:
                    for page in context.pages:
                        try:
                            page.close()
                        except:
                            pass
            except:
                pass
            try:
                self.browser.close()
            except:
                pass

    def pause(self):
        self.is_paused = True
        self.status_signal.emit(t("status_paused"))

    def resume(self):
        self.is_paused = False
        self.status_signal.emit(t("status_running"))


class StepEditDialog(QDialog):
    """步驟編輯對話框 - 使用下拉選項"""

    def __init__(self, step=None, parent=None):
        super().__init__(parent)
        self.step = step or TaskStep('goto', {'url': 'https://example.com', 'wait': '2'})
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


class MainWindow(QMainWindow):
    """主窗口"""

    def __init__(self):
        super().__init__()
        self.task_manager = TaskManager()
        self.browser_thread = None
        self.current_task = None
        
        # 資料庫相關
        self.db_manager = None
        self.order_monitor = None
        self.db_connected = False
        
        self.init_ui()
        self.refresh_task_list()
        
        # 嘗試連接資料庫
        self._init_database()

    def _init_database(self):
        """初始化資料庫連接"""
        try:
            self.db_manager = DatabaseManager()
            success, msg = self.db_manager.test_connection()
            if success:
                self.db_connected = True
                self.log(t("db_connected", msg=msg))
                self._update_db_status()
            else:
                self.log(t("db_connect_failed", msg=msg))
                self.db_connected = False
        except ImportError:
            self.log("PyMySQL 未安裝，無法使用資料庫功能")
        except Exception as e:
            self.log(t("db_connect_error", error=str(e)))
            self.db_connected = False

    def _update_db_status(self):
        """更新資料庫狀態顯示"""
        if hasattr(self, 'db_status_label') and self.db_manager:
            if self.db_connected:
                stats = self.db_manager.get_statistics()
                total = stats.get('total', 0)
                pending = stats.get('pending', 0)
                completed = stats.get('completed', 0)
                self.db_status_label.setText(
                    t("db_status_info", total=total, pending=pending, completed=completed)
                )
                self.db_status_label.setStyleSheet("color: green;")
            else:
                self.db_status_label.setText(t("db_status_disconnected"))
                self.db_status_label.setStyleSheet("color: red;")

    def init_ui(self):
        self.setWindowTitle(t("app_title"))
        self.setMinimumSize(1200, 800)

        self._create_menu()
        self._create_toolbar()

        central = QWidget()
        self.setCentralWidget(central)
        layout = QHBoxLayout(central)

        left_panel = self._create_task_panel()
        right_panel = self._create_work_panel()

        splitter = QSplitter(Qt.Horizontal)
        splitter.addWidget(left_panel)
        splitter.addWidget(right_panel)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 3)
        splitter.setSizes([300, 900])

        layout.addWidget(splitter)

        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage(t("ready"))

        self.captcha_label = QLabel("")
        self.captcha_label.setStyleSheet("color: orange; font-weight: bold;")
        self.status_bar.addPermanentWidget(self.captcha_label)

        # 資料庫狀態
        self.db_status_label = QLabel(t("db_status_disconnected"))
        self.db_status_label.setStyleSheet("color: gray;")
        self.status_bar.addPermanentWidget(self.db_status_label)

    def _create_menu(self):
        menubar = self.menuBar()

        # 檔案菜單
        file_menu = menubar.addMenu(t("menu_file"))

        new_action = QAction(t("menu_new_task"), self)
        new_action.triggered.connect(self.new_task)
        file_menu.addAction(new_action)

        import_action = QAction(t("menu_import_task"), self)
        import_action.triggered.connect(self.import_task)
        file_menu.addAction(import_action)

        file_menu.addSeparator()

        exit_action = QAction(t("menu_exit"), self)
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        # 語言菜單
        lang_menu = menubar.addMenu(t("menu_language"))

        self.lang_actions = {}
        for lang_code, lang_name in i18n.t.lang_names.items():
            action = QAction(lang_name, self)
            action.setCheckable(True)
            action.setData(lang_code)
            action.triggered.connect(lambda checked, code=lang_code: self._change_language(code))
            lang_menu.addAction(action)
            self.lang_actions[lang_code] = action

        current_lang = get_current_lang()
        if current_lang in self.lang_actions:
            self.lang_actions[current_lang].setChecked(True)

        # 資料庫菜單
        db_menu = menubar.addMenu(t("menu_database"))

        db_connect_action = QAction(t("menu_db_connect"), self)
        db_connect_action.triggered.connect(self._connect_database)
        db_menu.addAction(db_connect_action)

        db_sync_action = QAction(t("menu_db_sync"), self)
        db_sync_action.triggered.connect(self._sync_orders)
        db_menu.addAction(db_sync_action)

        db_menu.addSeparator()

        db_start_monitor_action = QAction(t("menu_db_start_monitor"), self)
        db_start_monitor_action.triggered.connect(self._start_monitor)
        db_menu.addAction(db_start_monitor_action)

        db_stop_monitor_action = QAction(t("menu_db_stop_monitor"), self)
        db_stop_monitor_action.triggered.connect(self._stop_monitor)
        db_menu.addAction(db_stop_monitor_action)

        # 幫助菜單
        help_menu = menubar.addMenu(t("menu_help"))
        about_action = QAction(t("menu_about"), self)
        about_action.triggered.connect(self.show_about)
        help_menu.addAction(about_action)

    def _change_language(self, lang_code):
        """更改語言"""
        set_language(lang_code)

        for code, action in self.lang_actions.items():
            action.setChecked(code == lang_code)

        self._rebuild_ui()

    def _rebuild_ui(self):
        """重新構建 UI（語言切換後）"""
        self.menuBar().clear()
        self._create_menu()

        for tb in self.findChildren(QToolBar):
            self.removeToolBar(tb)
        self._create_toolbar()

        self.setWindowTitle(t("app_title"))
        self.task_panel_title.setText(t("panel_task_list"))

        self.btn_new.setText(t("btn_new"))
        self.btn_edit.setText(t("btn_edit"))
        self.btn_delete.setText(t("btn_delete"))
        self.btn_refresh.setText(t("btn_refresh"))

        self.run_btn.setText(t("toolbar_run"))
        self.stop_btn.setText(t("toolbar_stop"))
        self.pause_btn.setText(t("toolbar_pause"))
        self.captcha_btn.setText(t("toolbar_captcha_resolved"))

        self.tabs.setTabText(0, t("tab_task_detail"))
        self.tabs.setTabText(1, t("tab_execution_log"))
        self.tabs.setTabText(2, t("tab_browser_config"))
        self.tabs.setTabText(3, t("tab_database"))

        self.detail_label.setText(t("select_task_hint"))
        self.btn_clear_log.setText(t("btn_clear_log"))

        self.proxy_group.setTitle(t("config_proxy"))
        self.browser_group.setTitle(t("config_browser"))
        self.browser_type.setItemText(0, t("config_browser_chrome"))
        self.browser_type.setItemText(1, t("config_browser_cloak"))
        self.headless_check.setText(t("config_headless"))
        self.humanize_check.setText(t("config_humanize"))
        self.geoip_check.setText(t("config_geoip"))
        self.proxy_type.model().item(0).setText(t("config_proxy_none"))

        # 更新資料庫面板
        if hasattr(self, 'db_config_group'):
            self.db_config_group.setTitle(t("db_config_title"))
            self.btn_db_test.setText(t("db_btn_test"))
            self.btn_db_connect.setText(t("db_btn_connect"))
            self.btn_db_sync.setText(t("db_btn_sync"))
            self.btn_db_start_monitor.setText(t("db_btn_start_monitor"))
            self.btn_db_stop_monitor.setText(t("db_btn_stop_monitor"))

        self.status_bar.showMessage(t("ready"))
        self._update_db_status()

    def _create_toolbar(self):
        toolbar = QToolBar()
        toolbar.setIconSize(QSize(28, 28))
        self.addToolBar(toolbar)

        self.run_btn = QPushButton(t("toolbar_run"))
        self.run_btn.clicked.connect(self.run_task)
        toolbar.addWidget(self.run_btn)

        self.stop_btn = QPushButton(t("toolbar_stop"))
        self.stop_btn.clicked.connect(self.stop_task)
        self.stop_btn.setEnabled(False)
        toolbar.addWidget(self.stop_btn)

        self.pause_btn = QPushButton(t("toolbar_pause"))
        self.pause_btn.clicked.connect(self.pause_task)
        self.pause_btn.setEnabled(False)
        toolbar.addWidget(self.pause_btn)

        toolbar.addSeparator()

        self.captcha_btn = QPushButton(t("toolbar_captcha_resolved"))
        self.captcha_btn.clicked.connect(self.resolve_captcha)
        self.captcha_btn.setEnabled(False)
        toolbar.addWidget(self.captcha_btn)

    def _create_task_panel(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)

        self.task_panel_title = QLabel(t("panel_task_list"))
        self.task_panel_title.setStyleSheet("font-size: 16px; font-weight: bold;")
        layout.addWidget(self.task_panel_title)

        self.task_list = QListWidget()
        self.task_list.itemDoubleClicked.connect(self.edit_task)
        layout.addWidget(self.task_list)

        btn_layout = QHBoxLayout()

        self.btn_new = QPushButton(t("btn_new"))
        self.btn_new.clicked.connect(self.new_task)
        btn_layout.addWidget(self.btn_new)

        self.btn_edit = QPushButton(t("btn_edit"))
        self.btn_edit.clicked.connect(lambda: self.edit_task(self.task_list.currentItem()))
        btn_layout.addWidget(self.btn_edit)

        self.btn_delete = QPushButton(t("btn_delete"))
        self.btn_delete.clicked.connect(self.delete_task)
        btn_layout.addWidget(self.btn_delete)

        layout.addLayout(btn_layout)

        self.btn_refresh = QPushButton(t("btn_refresh"))
        self.btn_refresh.clicked.connect(self.refresh_task_list)
        layout.addWidget(self.btn_refresh)

        return panel

    def _create_work_panel(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)

        self.tabs = QTabWidget()

        # 任務詳情頁
        detail_tab = QWidget()
        detail_layout = QVBoxLayout(detail_tab)

        self.detail_label = QLabel(t("select_task_hint"))
        self.detail_label.setStyleSheet("font-size: 14px; padding: 10px;")
        detail_layout.addWidget(self.detail_label)

        self.detail_text = QTextBrowser()
        self.detail_text.setOpenExternalLinks(True)
        detail_layout.addWidget(self.detail_text)

        self.tabs.addTab(detail_tab, t("tab_task_detail"))

        # 日誌頁
        log_tab = QWidget()
        log_layout = QVBoxLayout(log_tab)

        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setFont(QFont("Consolas", 10))
        log_layout.addWidget(self.log_text)

        self.btn_clear_log = QPushButton(t("btn_clear_log"))
        self.btn_clear_log.clicked.connect(self.log_text.clear)
        log_layout.addWidget(self.btn_clear_log)

        self.tabs.addTab(log_tab, t("tab_execution_log"))

        # 配置頁
        config_tab = self._create_config_tab()
        self.tabs.addTab(config_tab, t("tab_browser_config"))

        # 資料庫頁
        db_tab = self._create_database_tab()
        self.tabs.addTab(db_tab, t("tab_database"))

        layout.addWidget(self.tabs)

        return panel

    def _create_config_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)

        self.proxy_group = QGroupBox(t("config_proxy"))
        proxy_layout = QVBoxLayout()

        self.proxy_type = QComboBox()
        self.proxy_type.addItems([t("config_proxy_none"), "HTTP", "HTTPS", "SOCKS5"])
        proxy_layout.addWidget(QLabel(t("config_proxy_type")))
        proxy_layout.addWidget(self.proxy_type)

        self.proxy_input = QLineEdit()
        self.proxy_input.setPlaceholderText(t("config_proxy_placeholder"))
        proxy_layout.addWidget(QLabel(t("config_proxy_address")))
        proxy_layout.addWidget(self.proxy_input)

        self.proxy_group.setLayout(proxy_layout)
        layout.addWidget(self.proxy_group)

        self.browser_group = QGroupBox(t("config_browser"))
        browser_layout = QVBoxLayout()

        browser_type_layout = QHBoxLayout()
        browser_type_layout.addWidget(QLabel(t("config_browser_label")))
        self.browser_type = QComboBox()
        self.browser_type.addItem(t("config_browser_chrome"), "chrome")
        self.browser_type.addItem(t("config_browser_cloak"), "cloakbrowser")
        browser_type_layout.addWidget(self.browser_type)
        browser_layout.addLayout(browser_type_layout)

        self.headless_check = QCheckBox(t("config_headless"))
        browser_layout.addWidget(self.headless_check)

        self.humanize_check = QCheckBox(t("config_humanize"))
        self.humanize_check.setChecked(True)
        browser_layout.addWidget(self.humanize_check)

        self.geoip_check = QCheckBox(t("config_geoip"))
        self.geoip_check.setChecked(False)
        browser_layout.addWidget(self.geoip_check)

        self.browser_group.setLayout(browser_layout)
        layout.addWidget(self.browser_group)

        layout.addStretch()

        return tab

    def _create_database_tab(self) -> QWidget:
        """創建資料庫配置頁面"""
        tab = QWidget()
        layout = QVBoxLayout(tab)

        # 配置區
        self.db_config_group = QGroupBox(t("db_config_title"))
        db_config_layout = QFormLayout()

        self.db_host = QLineEdit("localhost")
        db_config_layout.addRow(t("db_host") + ":", self.db_host)

        self.db_port = QSpinBox()
        self.db_port.setRange(1, 65535)
        self.db_port.setValue(3306)
        db_config_layout.addRow(t("db_port") + ":", self.db_port)

        self.db_user = QLineEdit("root")
        db_config_layout.addRow(t("db_user") + ":", self.db_user)

        self.db_password = QLineEdit("123456")
        self.db_password.setEchoMode(QLineEdit.Password)
        db_config_layout.addRow(t("db_password") + ":", self.db_password)

        self.db_database = QLineEdit("trader")
        db_config_layout.addRow(t("db_database") + ":", self.db_database)

        self.db_config_group.setLayout(db_config_layout)
        layout.addWidget(self.db_config_group)

        # 操作按鈕
        btn_layout = QHBoxLayout()

        self.btn_db_test = QPushButton(t("db_btn_test"))
        self.btn_db_test.clicked.connect(self._test_database)
        btn_layout.addWidget(self.btn_db_test)

        self.btn_db_connect = QPushButton(t("db_btn_connect"))
        self.btn_db_connect.clicked.connect(self._connect_database)
        btn_layout.addWidget(self.btn_db_connect)

        self.btn_db_sync = QPushButton(t("db_btn_sync"))
        self.btn_db_sync.clicked.connect(self._sync_orders)
        btn_layout.addWidget(self.btn_db_sync)

        layout.addLayout(btn_layout)

        # 監控控制
        monitor_group = QGroupBox(t("db_monitor_title"))
        monitor_layout = QVBoxLayout()

        self.monitor_interval = QSpinBox()
        self.monitor_interval.setRange(5, 300)
        self.monitor_interval.setValue(30)
        self.monitor_interval.setSuffix(" 秒")
        monitor_layout.addWidget(QLabel(t("db_monitor_interval") + ":"))
        monitor_layout.addWidget(self.monitor_interval)

        monitor_btn_layout = QHBoxLayout()
        self.btn_db_start_monitor = QPushButton(t("db_btn_start_monitor"))
        self.btn_db_start_monitor.clicked.connect(self._start_monitor)
        monitor_btn_layout.addWidget(self.btn_db_start_monitor)

        self.btn_db_stop_monitor = QPushButton(t("db_btn_stop_monitor"))
        self.btn_db_stop_monitor.clicked.connect(self._stop_monitor)
        self.btn_db_stop_monitor.setEnabled(False)
        monitor_btn_layout.addWidget(self.btn_db_stop_monitor)

        monitor_layout.addLayout(monitor_btn_layout)

        self.monitor_status_label = QLabel(t("db_monitor_stopped"))
        self.monitor_status_label.setStyleSheet("color: gray;")
        monitor_layout.addWidget(self.monitor_status_label)

        monitor_group.setLayout(monitor_layout)
        layout.addWidget(monitor_group)

        # 任務隊列
        task_queue_group = QGroupBox(t("db_task_queue"))
        task_queue_layout = QVBoxLayout()

        self.task_queue_table = QTableWidget()
        self.task_queue_table.setColumnCount(4)
        self.task_queue_table.setHorizontalHeaderLabels([
            "ID", t("db_order_no"), t("db_status"), t("db_created_at")
        ])
        self.task_queue_table.setMaximumHeight(150)
        task_queue_layout.addWidget(self.task_queue_table)

        refresh_btn = QPushButton(t("btn_refresh"))
        refresh_btn.clicked.connect(self._refresh_task_queue)
        task_queue_layout.addWidget(refresh_btn)

        task_queue_group.setLayout(task_queue_layout)
        layout.addWidget(task_queue_group)

        layout.addStretch()

        return tab

    def _test_database(self):
        """測試資料庫連接"""
        config = self._get_db_config()
        test_db = DatabaseManager(config)
        success, msg = test_db.test_connection()
        
        if success:
            QMessageBox.information(self, t("msg_info"), t("db_test_success", msg=msg))
        else:
            QMessageBox.warning(self, t("msg_error"), t("db_test_failed", msg=msg))

    def _get_db_config(self) -> dict:
        """獲取資料庫配置"""
        return {
            'host': self.db_host.text().strip() or 'localhost',
            'port': self.db_port.value(),
            'user': self.db_user.text().strip() or 'root',
            'password': self.db_password.text(),
            'database': self.db_database.text().strip() or 'trader',
        }

    def _connect_database(self):
        """連接資料庫"""
        config = self._get_db_config()
        self.db_manager = DatabaseManager(config)
        success, msg = self.db_manager.test_connection()
        
        if success:
            self.db_connected = True
            self.log(t("db_connected", msg=msg))
            self._update_db_status()
            self._refresh_task_queue()
            QMessageBox.information(self, t("msg_info"), t("db_connect_success"))
        else:
            self.db_connected = False
            self.log(t("db_connect_failed", msg=msg))
            QMessageBox.warning(self, t("msg_error"), t("db_connect_failed", msg=msg))

    def _sync_orders(self):
        """同步訂單"""
        if not self.db_connected or not self.db_manager:
            QMessageBox.warning(self, t("msg_warning"), t("db_not_connected"))
            return

        try:
            count = self.db_manager.sync_direct_orders()
            self.log(t("db_sync_complete", count=count))
            self._refresh_task_queue()
            QMessageBox.information(self, t("msg_info"), t("db_sync_result", count=count))
        except Exception as e:
            QMessageBox.warning(self, t("msg_error"), str(e))

    def _refresh_task_queue(self):
        """刷新任務隊列"""
        if not self.db_connected or not self.db_manager:
            return

        try:
            tasks = self.db_manager.get_pending_tasks(limit=50)
            self.task_queue_table.setRowCount(len(tasks))

            for i, task in enumerate(tasks):
                self.task_queue_table.setItem(i, 0, QTableWidgetItem(str(task['id'])))
                self.task_queue_table.setItem(i, 1, QTableWidgetItem(task['order_no']))
                self.task_queue_table.setItem(i, 2, QTableWidgetItem(task['status']))
                self.task_queue_table.setItem(i, 3, QTableWidgetItem(
                    task['created_at'].strftime('%Y-%m-%d %H:%M:%S') if task.get('created_at') else ''
                ))

            self._update_db_status()
        except Exception as e:
            self.log(f"刷新任務隊列失敗: {e}")

    def _start_monitor(self):
        """開始監控"""
        if not self.db_connected or not self.db_manager:
            QMessageBox.warning(self, t("msg_warning"), t("db_not_connected"))
            return

        interval = self.monitor_interval.value()
        
        if self.order_monitor and self.order_monitor.is_running:
            self.log(t("db_monitor_already_running"))
            return

        self.order_monitor = OrderMonitor(self.db_manager, callback=self._on_new_order)
        self.order_monitor.start(interval=interval)
        
        self.btn_db_start_monitor.setEnabled(False)
        self.btn_db_stop_monitor.setEnabled(True)
        self.monitor_status_label.setText(t("db_monitor_running", interval=interval))
        self.monitor_status_label.setStyleSheet("color: green;")
        
        self.log(t("db_monitor_started", interval=interval))
        
        # 立即執行一次掃描
        tasks = self.order_monitor.scan_once()
        if tasks:
            self.log(t("db_found_tasks", count=len(tasks)))

    def _stop_monitor(self):
        """停止監控"""
        if self.order_monitor:
            self.order_monitor.stop()
        
        self.btn_db_start_monitor.setEnabled(True)
        self.btn_db_stop_monitor.setEnabled(False)
        self.monitor_status_label.setText(t("db_monitor_stopped"))
        self.monitor_status_label.setStyleSheet("color: gray;")
        
        self.log(t("db_monitor_stopped"))

    def _on_new_order(self, task: dict):
        """新訂單回調"""
        order_no = task.get('order_no', '')
        self.log(t("db_new_order", order_no=order_no))
        
        # 自動執行任務
        self._execute_order_task(order_no)

    def _execute_order_task(self, order_no: str):
        """執行訂單任務"""
        if not self.task_manager.tasks:
            self.log(t("db_no_tasks_configured"))
            return

        # 選擇第一個任務作為範例
        task_name = list(self.task_manager.tasks.keys())[0]
        task = self.task_manager.tasks[task_name]
        
        if not task.steps:
            self.log(t("msg_no_steps"))
            return

        config = self.get_config()

        self.log("=" * 50)
        self.log(t("task_start", name=task.name))
        self.log(t("task_order_no", order_no=order_no))

        # 更新按鈕狀態
        self.run_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self.pause_btn.setEnabled(True)

        # 啟動瀏覽器線程
        self.browser_thread = BrowserThread(config, task, order_no=order_no)
        self.browser_thread.log_signal.connect(self.log)
        self.browser_thread.status_signal.connect(lambda s: self.status_bar.showMessage(s))
        self.browser_thread.captcha_signal.connect(self.on_captcha_detected)
        self.browser_thread.captcha_resolved_signal.connect(self.on_captcha_resolved)
        self.browser_thread.task_complete_signal.connect(self._on_order_task_complete)
        self.browser_thread.start()

    def _on_order_task_complete(self, success: bool, message: str, order_no: str):
        """訂單任務完成回調"""
        if self.db_connected and self.db_manager and order_no:
            if success:
                self.db_manager.update_task_status(order_no, 'completed')
                self.log(t("db_task_completed", order_no=order_no))
            else:
                self.db_manager.update_task_status(order_no, 'failed', message)
                self.log(t("db_task_failed", order_no=order_no, error=message))

        self._refresh_task_queue()

        # 更新按鈕狀態
        self.run_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.pause_btn.setEnabled(False)
        self.captcha_btn.setEnabled(False)
        self.captcha_label.setText("")

    def get_config(self) -> dict:
        config = {
            'headless': self.headless_check.isChecked(),
            'humanize': self.humanize_check.isChecked(),
            'geoip': self.geoip_check.isChecked(),
            'browser_type': self.browser_type.currentData(),
        }

        proxy_type = self.proxy_type.currentText()
        proxy = self.proxy_input.text().strip()
        if proxy_type != t("config_proxy_none") and proxy:
            config['proxy'] = f"{proxy_type.lower()}://{proxy}" if "@" not in proxy else f"{proxy_type.lower()}://{proxy}"

        return config

    def refresh_task_list(self):
        self.task_manager.load_all()
        self.task_list.clear()

        for domain, task in self.task_manager.tasks.items():
            item = QListWidgetItem()
            item.setText(f"🌐 {task.name}\n   {domain}")
            item.setData(Qt.UserRole, domain)
            self.task_list.addItem(item)

        self.log(t("msg_tasks_loaded", count=len(self.task_manager.tasks)))

    def show_task_detail(self, domain: str):
        task = self.task_manager.get(domain)
        if not task:
            return

        self.detail_label.setText(f"<b>{task.name}</b> - {task.domain}")

        html = f"""
        <h2>{task.name}</h2>
        <p><b>{t('detail_domain')}</b> {task.domain}</p>
        <p><b>{t('detail_description')}</b> {task.description or t('detail_none')}</p>
        <p><b>{t('detail_steps_count')}</b> {len(task.steps)}</p>
        <hr>
        <h3>{t('detail_steps_title')}</h3>
        <ol>
        """

        for i, step in enumerate(task.steps):
            step_info = TaskStep.STEP_TYPES.get(step.type, {})
            label = t(step_info.get('label_key', ''))

            if step.type == 'goto':
                detail = f"{t('detail_open')} {step.params.get('url', '')}"
            elif step.type in ['click', 'hover']:
                detail = f"{t('detail_click')} {step.params.get('selector', '')}"
            elif step.type in ['fill', 'type']:
                detail = f"{t('detail_fill')} {step.params.get('selector', '')} = {step.params.get('value', '')[:30]}..."
            elif step.type in ['scroll_down', 'scroll_up']:
                detail = f"{t('detail_scroll')} {step.params.get('amount', 500)}px"
            elif step.type == 'screenshot':
                detail = f"{t('detail_screenshot')} {step.params.get('name', '')}"
            elif step.type == 'wait':
                detail = f"{t('detail_wait')} {step.params.get('seconds', 1)}{t('detail_seconds')}"
            elif step.type == 'js':
                detail = t("detail_exec_js")
            else:
                detail = ""

            html += f"<li><b>{label}</b> - {detail}</li>"

        html += "</ol>"
        self.detail_text.setHtml(html)

    def log(self, message: str):
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_text.append(f"[{timestamp}] {message}")
        self.log_text.moveCursor(QTextCursor.End)

    def new_task(self):
        dialog = TaskEditDialog(parent=self)
        if dialog.exec_():
            task = dialog.get_task()
            self.task_manager.save(task)
            self.refresh_task_list()
            self.show_task_detail(task.domain)
            self.log(t("msg_task_created", name=task.name))

    def edit_task(self, item):
        if not item:
            return
        domain = item.data(Qt.UserRole)
        task = self.task_manager.get(domain)
        if not task:
            return

        dialog = TaskEditDialog(task, self)
        if dialog.exec_():
            new_task = dialog.get_task()
            if new_task.domain != domain:
                self.task_manager.delete(domain)
            self.task_manager.save(new_task)
            self.refresh_task_list()
            self.show_task_detail(new_task.domain)
            self.log(t("msg_task_updated", name=new_task.name))

    def delete_task(self):
        item = self.task_list.currentItem()
        if not item:
            QMessageBox.warning(self, t("msg_warning"), t("msg_please_select_task"))
            return

        domain = item.data(Qt.UserRole)
        task = self.task_manager.get(domain)

        reply = QMessageBox.question(
            self, t("msg_confirm_delete"),
            t("msg_confirm_delete_task", name=task.name),
            QMessageBox.Yes | QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            self.task_manager.delete(domain)
            self.refresh_task_list()
            self.detail_label.setText(t("select_task_hint"))
            self.detail_text.setHtml("")
            self.log(t("msg_task_deleted", name=task.name))

    def import_task(self):
        path, _ = QFileDialog.getOpenFileName(
            self, t("menu_import_task"), "", "JSON文件 (*.json)"
        )
        if path:
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    task = SiteTask.from_dict(json.load(f))
                self.task_manager.save(task)
                self.refresh_task_list()
                self.show_task_detail(task.domain)
                self.log(t("msg_import_success", name=task.name))
            except Exception as e:
                QMessageBox.critical(self, t("msg_error"), t("msg_import_failed", error=e))

    def run_task(self):
        item = self.task_list.currentItem()
        if not item:
            QMessageBox.warning(self, t("msg_warning"), t("msg_please_select_task_to_run"))
            return

        domain = item.data(Qt.UserRole)
        task = self.task_manager.get(domain)
        if not task:
            return

        if not task.steps:
            QMessageBox.warning(self, t("msg_warning"), t("msg_no_steps"))
            return

        self.current_task = task
        config = self.get_config()

        self.log("=" * 50)
        self.log(t("task_start", name=task.name))

        self.run_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self.pause_btn.setEnabled(True)

        self.browser_thread = BrowserThread(config, task)
        self.browser_thread.log_signal.connect(self.log)
        self.browser_thread.status_signal.connect(lambda s: self.status_bar.showMessage(s))
        self.browser_thread.captcha_signal.connect(self.on_captcha_detected)
        self.browser_thread.captcha_resolved_signal.connect(self.on_captcha_resolved)
        self.browser_thread.task_complete_signal.connect(self.on_task_complete)
        self.browser_thread.start()

    def stop_task(self):
        """立即停止任務"""
        if self.browser_thread and self.browser_thread.is_running:
            self.browser_thread.stop()
            self.log(t("status_stopping"))
            self.run_btn.setEnabled(True)
            self.stop_btn.setEnabled(False)
            self.pause_btn.setEnabled(False)
            self.captcha_btn.setEnabled(False)
            self.status_bar.showMessage(t("status_stopping"))
        else:
            self.log(t("msg_no_running_task"))

    def pause_task(self):
        if self.browser_thread and self.browser_thread.is_running:
            if self.browser_thread.is_paused:
                self.browser_thread.resume()
                self.pause_btn.setText(t("toolbar_pause"))
            else:
                self.browser_thread.pause()
                self.pause_btn.setText(t("toolbar_resume"))

    def resolve_captcha(self):
        self.captcha_label.setText("")
        self.captcha_btn.setEnabled(False)
        self.log(t("captcha_user_confirmed"))

    def on_captcha_detected(self, message: str):
        self.captcha_label.setText(message)
        self.captcha_btn.setEnabled(True)

    def on_captcha_resolved(self):
        self.captcha_label.setText("")
        self.captcha_btn.setEnabled(False)

    def on_task_complete(self, success: bool, message: str, order_no: str = None):
        self.run_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.pause_btn.setEnabled(False)
        self.captcha_btn.setEnabled(False)
        self.captcha_label.setText("")

        if success:
            self.log(t("msg_task_complete"))
            QMessageBox.information(self, t("msg_info"), message)
        else:
            if "停止" in message or self.browser_thread.should_stop if self.browser_thread else False:
                self.log(t("msg_task_stopped"))
            else:
                self.log(t("msg_task_error", error=message))
                QMessageBox.warning(self, t("msg_error"), message)

    def show_about(self):
        QMessageBox.about(self, t("about_title"), t("about_text"))

    def closeEvent(self, event):
        if self.browser_thread and self.browser_thread.is_running:
            self.browser_thread.stop()
            time.sleep(0.5)
        if self.order_monitor and self.order_monitor.is_running:
            self.order_monitor.stop()
        event.accept()


def main():
    app = QApplication(sys.argv)
    app.setApplicationName(t("app_title"))

    window = MainWindow()
    window.show()

    sys.exit(app.exec_())


if __name__ == '__main__':
    main()
