"""
瀏覽器自動化執行線程
接受 steps 列表（來自後端 API），支持模板變量替換
"""
import os
import re
import random
import time
import traceback
import logging
from datetime import datetime

from PyQt5.QtCore import QThread, pyqtSignal

logger = logging.getLogger(__name__)


def _render(value: str, ctx: dict) -> str:
    """替換 {{variable}} 模板變量"""
    if not isinstance(value, str):
        return value
    def replacer(m):
        key = m.group(1).strip()
        return str(ctx.get(key, m.group(0)))
    return re.sub(r'\{\{(\w+)\}\}', replacer, value)


class BrowserThread(QThread):
    """瀏覽器操作線程，接受 steps 列表驅動自動化"""

    log_signal            = pyqtSignal(str)
    status_signal         = pyqtSignal(str)
    captcha_signal        = pyqtSignal(str)
    captcha_resolved_signal = pyqtSignal()
    task_complete_signal  = pyqtSignal(bool, str, str)  # success, message, order_no

    def __init__(self, config: dict, task_data: dict):
        """
        config    — 瀏覽器配置 {'browser_type', 'humanize', 'proxy'}
        task_data — 後端返回的任務字典，包含 steps、order_no、task_id 等
        """
        super().__init__()
        self.config    = config
        self.task_data = task_data
        self.order_no  = task_data.get('order_no', '')
        self.task_id   = task_data.get('task_id', 0)

        # 模板上下文：把 task_data 的所有字段都放進去
        self.ctx = {k: str(v) for k, v in task_data.items() if v is not None}

        self.browser       = None
        self.page          = None
        self.is_running    = False
        self.should_stop   = False

    # ── 主流程 ────────────────────────────────────────────────────────────────

    def run(self):
        self.is_running  = True
        self.should_stop = False
        try:
            self._init_browser()
            self._execute_steps()
        except Exception as e:
            logger.error(f'執行出錯: {e}\n{traceback.format_exc()}')
            self.log_signal.emit(f'❌ 執行出錯: {e}')
            self.task_complete_signal.emit(False, str(e), self.order_no)
        finally:
            self._cleanup()

    # ── 瀏覽器初始化 ──────────────────────────────────────────────────────────

    def _init_browser(self):
        self.log_signal.emit('🌐 正在啟動瀏覽器...')
        browser_type = self.config.get('browser_type', 'cloakbrowser')
        if browser_type == 'chrome':
            self._init_chrome()
        else:
            self._init_cloakbrowser()

    def _init_chrome(self):
        from playwright.sync_api import sync_playwright

        self.log_signal.emit('使用系統 Chrome')
        chrome_paths = []
        if os.name == 'nt':
            for base in [
                os.environ.get('ProgramFiles', 'C:\\Program Files'),
                os.environ.get('ProgramFiles(x86)', 'C:\\Program Files (x86)'),
                os.environ.get('LOCALAPPDATA', ''),
            ]:
                chrome_paths.append(
                    os.path.join(base, 'Google', 'Chrome', 'Application', 'chrome.exe')
                )

        executable_path = next((p for p in chrome_paths if os.path.exists(p)), None)
        if executable_path:
            self.log_signal.emit(f'Chrome 路徑: {executable_path}')

        for attempt in range(3):
            try:
                pw = sync_playwright().start()
                opts = {
                    'headless': False,
                    'args': ['--start-maximized', '--disable-blink-features=AutomationControlled'],
                }
                if executable_path:
                    opts['executable_path'] = executable_path
                if self.config.get('proxy'):
                    opts['proxy'] = {'server': self.config['proxy']}
                self.browser = pw.chromium.launch(**opts)
                self.page    = self.browser.new_page()
                self.page.add_init_script(
                    "Object.defineProperty(navigator,'webdriver',{get:()=>undefined});"
                )
                self.log_signal.emit('✅ Chrome 啟動成功')
                return
            except Exception as e:
                try:
                    pw.stop()
                except Exception:
                    pass
                if attempt < 2:
                    self.log_signal.emit(f'啟動失敗，重試 ({attempt+1}/3): {e}')
                    time.sleep(2)
                else:
                    raise

    def _init_cloakbrowser(self):
        from cloakbrowser import launch

        self.log_signal.emit('使用 CloakBrowser')
        kwargs = {
            'headless': False,
            'humanize': self.config.get('humanize', True),
        }
        if self.config.get('proxy'):
            kwargs['proxy'] = self.config['proxy']

        for attempt in range(3):
            try:
                self.browser = launch(**kwargs)
                self.page    = self.browser.new_page()
                self.log_signal.emit('✅ CloakBrowser 啟動成功')
                return
            except Exception as e:
                if attempt < 2:
                    self.log_signal.emit(f'啟動失敗，重試 ({attempt+1}/3): {e}')
                    time.sleep(2)
                else:
                    raise

    # ── 步驟執行 ──────────────────────────────────────────────────────────────

    def _execute_steps(self):
        steps = self.task_data.get('steps') or []
        total = len(steps)
        self.log_signal.emit(f'▶ 開始執行任務 {self.order_no}，共 {total} 步')
        self.log_signal.emit('-' * 40)

        for idx, step in enumerate(steps):
            if self.should_stop:
                self.log_signal.emit('⏹ 用戶已停止')
                break

            action = step.get('action', '?')
            self.log_signal.emit(f'步驟 {idx+1}/{total}: {action}')

            # 步驟開始 → 通知後端（running）
            self._send_step_callback(
                step=f'step_{idx+1}_{action}',
                status='running',
                message=f'步驟 {idx+1}/{total}: {action}',
            )

            if self._check_captcha():
                self._handle_captcha()

            ok = self._execute_step(step)

            # 步驟結果 → 通知後端
            if ok:
                self.log_signal.emit(f'  ✅ 步驟 {idx+1} 完成')
                self._send_step_callback(
                    step=f'step_{idx+1}_{action}',
                    status='success',
                    message=f'步驟 {idx+1} 完成',
                )
            else:
                self.log_signal.emit(f'  ⚠️ 步驟 {idx+1} 可能未成功')
                self._send_step_callback(
                    step=f'step_{idx+1}_{action}',
                    status='failed',
                    message=f'步驟 {idx+1} 執行異常',
                )

            # 步驟間隨機等待
            time.sleep(random.uniform(0.5, 1.2))

        if not self.should_stop:
            self.log_signal.emit('-' * 40)
            self.log_signal.emit('✅ 任務完成')
            self.task_complete_signal.emit(True, '任務完成', self.order_no)

    def _execute_step(self, step: dict, timeout: int = 15) -> bool:
        """執行單個步驟，action 字段對應後端 API 規格"""
        if self.should_stop:
            return False

        action   = step.get('action', '')
        selector = _render(step.get('selector', ''), self.ctx)
        value    = _render(step.get('value', ''), self.ctx)
        url      = _render(step.get('url', ''), self.ctx)
        expected = _render(step.get('expected', ''), self.ctx)

        try:
            if action == 'navigate':
                self.page.goto(url, timeout=timeout * 1000)
                self.log_signal.emit(f'  → navigate {url}')

            elif action == 'click':
                self.page.click(selector, timeout=timeout * 1000)
                self.log_signal.emit(f'  → click {selector}')

            elif action == 'input':
                disp = value[:20] + '...' if len(value) > 20 else value
                self.log_signal.emit(f'  → input {selector} = {disp}')
                if not self._fill_with_verify(selector, value, '輸入值', timeout=timeout):
                    return False

            elif action == 'type':
                # 模擬人工逐字輸入（type 後同樣做回讀驗證）
                self.log_signal.emit(f'  → type {selector}')
                self.page.type(selector, value, delay=random.randint(50, 150), timeout=timeout * 1000)
                if not self._verify_input(selector, value):
                    self.log_signal.emit('  ⚠️ type 後值不一致，改用 fill 重試')
                    if not self._fill_with_verify(selector, value, '輸入值', timeout=timeout):
                        return False

            elif action == 'select':
                self.page.select_option(selector, value, timeout=timeout * 1000)
                self.log_signal.emit(f'  → select {selector} = {value}')

            elif action == 'wait':
                seconds = float(step.get('seconds', step.get('value', 1)))
                self.log_signal.emit(f'  → wait {seconds}s')
                for _ in range(int(seconds)):
                    if self.should_stop:
                        return False
                    time.sleep(1)
                frac = seconds - int(seconds)
                if frac > 0:
                    time.sleep(frac)

            elif action == 'wait_text':
                # 等待元素出現指定文字
                self.log_signal.emit(f'  → wait_text {selector} = "{expected}"')
                self.page.wait_for_selector(selector, timeout=timeout * 1000)
                text = self.page.inner_text(selector)
                if expected and expected not in text:
                    self.log_signal.emit(f'  ⚠️ 期望文字 "{expected}" 未找到，實際: "{text[:50]}"')
                    return False

            elif action == 'wait_selector':
                self.page.wait_for_selector(selector, timeout=timeout * 1000)
                self.log_signal.emit(f'  → wait_selector {selector}')

            elif action == 'wait_ga':
                # 通知後端需要 GA，然後輪詢等用戶填入
                self._request_ga()
                ga_code = self._poll_ga(timeout_sec=int(step.get('timeout', 120)))
                if not ga_code:
                    self.log_signal.emit('  ❌ GA 等待超時')
                    return False
                # 填入 GA 碼（帶重試驗證）
                if selector:
                    self.log_signal.emit(f'  → wait_ga: 填入 GA 碼至 {selector}')
                    if not self._fill_with_verify(selector, ga_code, 'GA 碼', timeout=timeout):
                        return False
                else:
                    self.log_signal.emit(f'  → wait_ga: GA 碼已取得 (無 selector，請在下一步填入)')
                    # 把 ga_code 存入 ctx 以供後續步驟 {{ga_code}} 使用
                    self.ctx['ga_code'] = ga_code

            elif action == 'screenshot':
                name = step.get('name', f'screenshot_{datetime.now().strftime("%H%M%S")}')
                path = f'{name}.png'
                self.page.screenshot(path=path)
                self.log_signal.emit(f'  → screenshot → {path}')

            elif action == 'js':
                code = _render(step.get('code', ''), self.ctx)
                self.page.evaluate(code)
                self.log_signal.emit('  → js executed')

            elif action == 'scroll':
                amount = int(step.get('amount', 500))
                self.page.mouse.wheel(0, amount)
                self.log_signal.emit(f'  → scroll {amount}px')

            else:
                self.log_signal.emit(f'  ⚠️ 未知 action: {action}，跳過')

            return True

        except Exception as e:
            if self.should_stop:
                return False
            self.log_signal.emit(f'  ❌ 步驟執行失敗: {e}')
            return False

    # ── 填入值驗證 ────────────────────────────────────────────────────────────

    def _verify_input(self, selector: str, expected: str) -> bool:
        """回讀欄位值，與期望值比對，返回是否一致。"""
        try:
            return self.page.input_value(selector, timeout=3000) == expected
        except Exception:
            return True   # 不支援 input_value 的元素視為通過

    def _fill_with_verify(self, selector: str, value: str, label: str = '值',
                           max_retries: int = 3, timeout: int = 15) -> bool:
        """
        填入值 + 回讀驗證，不一致時清空重填，最多重試 max_retries 次。
        全部失敗才返回 False（步驟失敗）。
        """
        for attempt in range(1, max_retries + 1):
            try:
                self.page.fill(selector, value, timeout=timeout * 1000)
            except Exception as e:
                self.log_signal.emit(f'  ❌ {label}填入失敗（第{attempt}次）: {e}')
                if attempt < max_retries:
                    time.sleep(0.5)
                continue

            if self._verify_input(selector, value):
                self.log_signal.emit(f'  ✔ {label}驗證通過（第{attempt}次）')
                return True

            # 值不一致：讀出實際值做日誌
            try:
                actual = self.page.input_value(selector, timeout=2000)
            except Exception:
                actual = '(無法讀取)'
            disp_exp = value[:20]  + ('...' if len(value)  > 20 else '')
            disp_act = actual[:20] + ('...' if len(actual) > 20 else '')
            self.log_signal.emit(
                f'  ⚠️ {label}不一致（第{attempt}次）'
                f'  期望={repr(disp_exp)}  實際={repr(disp_act)}'
            )

            if attempt < max_retries:
                self.log_signal.emit(f'  🔄 清空後重新填入...')
                try:
                    self.page.fill(selector, '', timeout=3000)
                except Exception:
                    pass
                time.sleep(0.5)

        self.log_signal.emit(f'  ❌ {label}重試 {max_retries} 次仍不一致，步驟失敗')
        return False

    # ── 步驟回調 ──────────────────────────────────────────────────────────────

    def _send_step_callback(self, step: str, status: str, message: str = ''):
        """非阻塞：把步驟進度發到後端 /api/pcauto/step-callback"""
        from config_manager import load_config
        import requests as _req
        cfg        = load_config()
        server_url = cfg.get('server_url', '').rstrip('/')
        api_key    = cfg.get('api_key', '')
        if not server_url or not api_key:
            return
        try:
            _req.post(
                f'{server_url}/api/pcauto/step-callback',
                json={
                    'task_id':  self.task_id,
                    'order_no': self.order_no,
                    'step':     step,
                    'status':   status,
                    'message':  message,
                },
                headers={'X-Pcauto-Key': api_key},
                timeout=4,
            )
        except Exception:
            pass  # 步驟回調失敗不影響主流程

    # ── GA / OTP ──────────────────────────────────────────────────────────────

    def _request_ga(self):
        """通知後端需要 GA 碼"""
        from config_manager import load_config
        cfg        = load_config()
        server_url = cfg.get('server_url', '').rstrip('/')
        api_key    = cfg.get('api_key', '')
        try:
            import requests as _req
            _req.post(
                f'{server_url}/api/pcauto/request-ga',
                json={'task_id': self.task_id, 'order_no': self.order_no},
                headers={'X-Pcauto-Key': api_key},
                timeout=5,
            )
            self.log_signal.emit('  🔐 已通知用戶輸入 GA 碼，等待中...')
        except Exception as e:
            self.log_signal.emit(f'  ⚠️ request-ga 失敗: {e}')

    def _poll_ga(self, timeout_sec: int = 120) -> str:
        """輪詢後端直到 GA 碼填入，最多等 timeout_sec 秒"""
        from config_manager import load_config
        import requests as _req
        cfg        = load_config()
        server_url = cfg.get('server_url', '').rstrip('/')
        api_key    = cfg.get('api_key', '')
        deadline   = time.time() + timeout_sec

        while time.time() < deadline:
            if self.should_stop:
                return ''
            try:
                resp = _req.get(
                    f'{server_url}/api/pcauto/get-ga',
                    params={'task_id': self.task_id},
                    headers={'X-Pcauto-Key': api_key},
                    timeout=5,
                )
                data = resp.json()
                if data.get('ready') and data.get('ga_code'):
                    return data['ga_code']
            except Exception:
                pass
            time.sleep(1)   # GA 碼時效短，1s 輪詢
        return ''

    # ── 驗證碼 ────────────────────────────────────────────────────────────────

    def _check_captcha(self) -> bool:
        selectors = [
            '.g-recaptcha', '[data-sitekey]', '.cf-turnstile',
            '#hcaptcha', '.h-captcha', '#captcha', '.captcha-container',
            'iframe[src*="captcha"]', '.challenge-form',
        ]
        for sel in selectors:
            try:
                if self.page.locator(sel).is_visible(timeout=300):
                    return True
            except Exception:
                continue
        return False

    def _handle_captcha(self):
        self.log_signal.emit('⚠️ 檢測到驗證碼，等待人工處理...')
        self.captcha_signal.emit('⚠️ 請手動完成驗證碼後繼續')
        while self._check_captcha():
            if self.should_stop:
                return
            time.sleep(1)
        self.log_signal.emit('✅ 驗證碼已解決')
        self.captcha_resolved_signal.emit()

    # ── 清理 ──────────────────────────────────────────────────────────────────

    def _cleanup(self):
        try:
            if self.browser:
                self.browser.close()
        except Exception:
            pass
        self.is_running = False
        self.status_signal.emit('已停止')

    def stop(self):
        self.should_stop = True
        self.log_signal.emit('⏹ 正在停止...')
        if self.browser:
            try:
                for ctx in self.browser.contexts:
                    for pg in ctx.pages:
                        try:
                            pg.close()
                        except Exception:
                            pass
            except Exception:
                pass
            try:
                self.browser.close()
            except Exception:
                pass
