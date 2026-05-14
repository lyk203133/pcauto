"""
定時掃單 QThread
每隔 poll_interval 秒調用 GET /api/pcauto/pending-tasks，有任務就啟動 BrowserThread
"""
import time
import requests
import logging
from PyQt5.QtCore import QThread, pyqtSignal

from config_manager import load_config
from browser_thread import BrowserThread
from callback_sender import send_callback

logger = logging.getLogger(__name__)


class TaskPollerThread(QThread):
    """定時掃單線程"""

    log_signal          = pyqtSignal(str)
    task_started_signal = pyqtSignal(str)       # order_no
    task_done_signal    = pyqtSignal(str, bool)  # order_no, success
    countdown_signal    = pyqtSignal(int)        # 距下次掃單剩餘秒數

    def __init__(self, parent=None):
        super().__init__(parent)
        self._running        = False
        self._active_threads = {}   # order_no -> BrowserThread

    def run(self):
        self._running = True
        self.log_signal.emit('🔄 掃單服務已啟動')
        while self._running:
            try:
                self._poll_once()
            except Exception as e:
                self.log_signal.emit(f'掃單異常: {e}')
            cfg      = load_config()
            interval = int(cfg.get('poll_interval', 5))
            for remaining in range(interval, 0, -1):
                if not self._running:
                    break
                self.countdown_signal.emit(remaining)
                time.sleep(1)
            if self._running:
                self.countdown_signal.emit(0)
        self.log_signal.emit('⏹ 掃單服務已停止')

    def _poll_once(self):
        cfg        = load_config()
        server_url = cfg.get('server_url', '').rstrip('/')
        api_key    = cfg.get('api_key', '')
        if not server_url or not api_key:
            return

        poll_url = f'{server_url}/api/pcauto/pending-tasks'
        self.log_signal.emit(f'>> 掃單 {poll_url}')
        t0 = time.time()
        try:
            resp = requests.get(
                poll_url,
                headers={'X-Pcauto-Key': api_key},
                timeout=10,
            )
            elapsed = time.time() - t0
            if resp.status_code != 200:
                self.log_signal.emit(
                    f'⚠️ HTTP {resp.status_code}（{elapsed:.2f}s）—— 請確認 API Key 和後端 URL'
                )
                return
            data  = resp.json()
            tasks = data.get('tasks', [])
            if tasks:
                self.log_signal.emit(
                    f'📋 發現 {len(tasks)} 個待處理任務（{elapsed:.2f}s）'
                )
            else:
                self.log_signal.emit(f'🔍 無待處理任務（{elapsed:.2f}s）')
            for task_data in tasks:
                self._start_task(task_data, cfg)
        except requests.exceptions.ConnectionError:
            elapsed = time.time() - t0
            self.log_signal.emit(f'❌ 無法連線後端（{elapsed:.2f}s）：{poll_url}')
        except requests.exceptions.Timeout:
            self.log_signal.emit('❌ 掃單請求逾時（10s）')
        except Exception as e:
            elapsed = time.time() - t0
            self.log_signal.emit(f'❌ 掃單失敗（{elapsed:.2f}s）: {e}')

    def _start_task(self, task_data: dict, cfg: dict):
        order_no = task_data.get('order_no', '')
        task_id  = task_data.get('task_id', 0)

        # 避免重複啟動同一訂單
        if order_no in self._active_threads:
            if self._active_threads[order_no].isRunning():
                return

        browser_cfg = {
            'browser_type': cfg.get('browser_type', 'chrome'),
            'humanize':     cfg.get('humanize', True),
            'proxy':        cfg.get('proxy') or None,
        }

        thread = BrowserThread(browser_cfg, task_data)
        thread.log_signal.connect(self.log_signal)
        thread.task_complete_signal.connect(
            lambda success, msg, _ono, ono=order_no, tid=task_id:
                self._on_task_complete(ono, tid, success)
        )
        self._active_threads[order_no] = thread
        thread.start()
        self.log_signal.emit(f'🚀 已啟動任務: {order_no}')
        self.task_started_signal.emit(order_no)

    def _on_task_complete(self, order_no: str, task_id: int, success: bool):
        status = 2 if success else 3
        send_callback(task_id, order_no, status)
        self.task_done_signal.emit(order_no, success)
        self._active_threads.pop(order_no, None)

    def stop(self):
        self._running = False
        for t in list(self._active_threads.values()):
            if t.isRunning():
                t.stop()
