"""
瀏覽器操作服務
負責瀏覽器的啟動、執行步驟、停止等操作
"""

import os
import random
import time
import traceback
import logging
from datetime import datetime

from PyQt5.QtCore import QThread, pyqtSignal

from models import TaskStep, SiteTask
from i18n import t

logger = logging.getLogger(__name__)


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
        import subprocess

        self.log_signal.emit(t("browser_using_chrome"))

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
        from cloakbrowser import launch

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
