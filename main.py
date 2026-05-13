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
    QFrame, QScrollArea, QSizePolicy, QDoubleSpinBox, QDockWidget,
    QStackedWidget, QGraphicsDropShadowEffect
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

        # 設置為無邊框窗口
        self.setWindowFlags(Qt.FramelessWindowHint)

        # 設置為螢幕 1/10 寬度，高度滿屏
        screen = QApplication.desktop().screenGeometry()
        width = int(screen.width() * 0.1)  # 1/10 螢幕寬度
        width = max(70, min(width, 100))   # 限制在 70-100 像素之間
        height = screen.height()
        x = screen.width() - width  # 放在右側
        y = 0
        self.setGeometry(x, y, width, height)
        self.setMinimumSize(width, 400)

        # 創建窄側邊欄 UI
        self._create_sidebar()

        # 狀態列
        self.status_bar = QStatusBar()
        self.status_bar.setStyleSheet("QStatusBar { font-size: 10px; }")
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage(t("ready"))

    def _create_sidebar(self):
        """創建窄側邊欄"""
        # 設置中央部件
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(8)

        # 拖動區域（頂部）
        drag_area = QLabel("🚀 AUTO")
        drag_area.setAlignment(Qt.AlignCenter)
        drag_area.setStyleSheet("""
            QLabel {
                font-size: 12px;
                font-weight: bold;
                color: #fff;
                background-color: #1976D2;
                border-radius: 5px;
                padding: 5px;
            }
        """)
        drag_area.mousePressEvent = lambda e: self._start_drag(e)
        drag_area.mouseMoveEvent = lambda e: self._drag(e)
        layout.addWidget(drag_area)

        # 最小化按鈕
        min_btn = QPushButton("─")
        min_btn.setFixedHeight(25)
        min_btn.clicked.connect(self.showMinimized)
        min_btn.setStyleSheet("""
            QPushButton {
                background-color: #FFC107;
                color: #333;
                border: none;
                border-radius: 5px;
                font-weight: bold;
            }
            QPushButton:hover { background-color: #FFD54F; }
        """)
        layout.addWidget(min_btn)

        # 關閉按鈕
        close_btn = QPushButton("✕")
        close_btn.setFixedHeight(25)
        close_btn.clicked.connect(self.close)
        close_btn.setStyleSheet("""
            QPushButton {
                background-color: #F44336;
                color: #fff;
                border: none;
                border-radius: 5px;
                font-weight: bold;
            }
            QPushButton:hover { background-color: #E57373; }
        """)
        layout.addWidget(close_btn)

        layout.addSpacing(10)

        # 功能按鈕
        buttons = [
            ("🌐", "btn_browser", "_open_browser_dialog"),
            ("📋", "btn_tasks", "_open_task_dialog"),
            ("📝", "btn_logs", "_open_log_dialog"),
            ("⚙️", "btn_settings", "_open_settings_dialog"),
            ("💾", "btn_database", "_open_database_dialog"),
            ("📁", "menu_import_task", "_import_task"),
            ("🏃", "toolbar_run", "_quick_run"),
        ]

        for icon, key, method in buttons:
            btn = QPushButton(icon)
            btn.setFixedHeight(45)
            btn.clicked.connect(getattr(self, method))
            btn.setToolTip(t(key))
            btn.setStyleSheet("""
                QPushButton {
                    font-size: 18px;
                    border: 2px solid #ddd;
                    border-radius: 8px;
                    background-color: #f5f5f5;
                }
                QPushButton:hover {
                    background-color: #e0e0e0;
                    border-color: #1976D2;
                }
            """)
            layout.addWidget(btn)

        layout.addStretch()

        # 語言切換
        self.lang_combo = QComboBox()
        self.lang_combo.setFixedHeight(30)
        for lang_code, lang_name in i18n.t.lang_names.items():
            self.lang_combo.addItem(lang_name[:3], lang_code)
        current_lang = get_current_lang()
        idx = self.lang_combo.findData(current_lang)
        if idx >= 0:
            self.lang_combo.setCurrentIndex(idx)
        self.lang_combo.currentIndexChanged.connect(self._on_language_changed)
        self.lang_combo.setStyleSheet("""
            QComboBox {
                font-size: 10px;
                border: 1px solid #ddd;
                border-radius: 5px;
                padding: 2px 5px;
            }
        """)
        layout.addWidget(self.lang_combo)

    def _start_drag(self, event):
        """開始拖動窗口"""
        if event.button() == Qt.LeftButton:
            self._drag_pos = event.globalPos() - self.frameGeometry().topLeft()
            event.accept()

    def _drag(self, event):
        """拖動窗口"""
        if event.buttons() == Qt.LeftButton:
            self.move(event.globalPos() - self._drag_pos)
            event.accept()

    def _import_task(self):
        """導入任務"""
        from task_dialog import TaskDialog
        dialog = TaskDialog(self)
        dialog.exec_()

    def _quick_run(self):
        """快速運行任務"""
        from task_dialog import TaskDialog
        dialog = TaskDialog(self)
        dialog.exec_()

    def _open_browser_dialog(self):
        """打開瀏覽器對話框"""
        from browser_dialog import BrowserDialog
        dialog = BrowserDialog(self)
        dialog.exec_()

    def _open_task_dialog(self):
        """打開任務管理對話框"""
        from task_dialog import TaskDialog
        dialog = TaskDialog(self)
        dialog.exec_()

    def _open_log_dialog(self):
        """打開日誌查看對話框"""
        from log_dialog import LogDialog
        dialog = LogDialog(self)
        dialog.exec_()

    def _open_settings_dialog(self):
        """打開設定對話框"""
        from settings_dialog import SettingsDialog
        dialog = SettingsDialog(self)
        dialog.exec_()

    def _open_database_dialog(self):
        """打開資料庫對話框"""
        from db_dialog import DatabaseDialog
        dialog = DatabaseDialog(self)
        dialog.exec_()

    def log(self, msg):
        """記錄日誌到狀態列"""
        timestamp = time.strftime("%H:%M:%S")
        self.status_bar.showMessage(f"[{timestamp}] {msg}")

    def clear_log(self):
        """清除日誌"""
        self.status_bar.showMessage(t("ready"))
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

    def _on_language_changed(self, index):
        """工具列語言下拉選單切換"""
        lang_code = self.lang_combo.currentData()
        if lang_code and lang_code != get_current_lang():
            set_language(lang_code)
            for code, action in self.lang_actions.items():
                action.setChecked(code == lang_code)
            self._rebuild_ui()

    def _rebuild_ui(self):
        """重新構建 UI（語言切換後）"""
        self.setWindowTitle(t("app_title"))

        # 更新語言下拉選單
        if hasattr(self, 'lang_combo'):
            self.lang_combo.blockSignals(True)
            current_lang = get_current_lang()
            idx = self.lang_combo.findData(current_lang)
            if idx >= 0:
                self.lang_combo.setCurrentIndex(idx)
            self.lang_combo.blockSignals(False)

        self.status_bar.showMessage(t("ready"))

    def refresh_task_list(self):
        """刷新任務列表"""
        self.task_manager.load_all()
        self.log(t("msg_tasks_loaded", count=len(self.task_manager.tasks)))

    def new_task(self):
        """新建任務"""
        from task_dialog import TaskDialog
        dialog = TaskDialog(self)
        dialog.exec_()

    def edit_task(self, item):
        """編輯任務"""
        from task_dialog import TaskDialog
        dialog = TaskDialog(self)
        dialog.exec_()

    def delete_task(self):
        """刪除任務"""
        from task_dialog import TaskDialog
        dialog = TaskDialog(self)
        dialog.exec_()

    def import_task(self):
        """導入任務"""
        path, _ = QFileDialog.getOpenFileName(
            self, t("menu_import_task"), "", "JSON文件 (*.json)")
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
