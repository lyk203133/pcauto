"""
主窗口 — 顯示運行狀態、日誌、控制按鈕
窄條面板，停靠屏幕右側 20%，左側 80% 留給瀏覽器
"""
import time
import logging
import traceback

from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QStatusBar, QLabel, QTextEdit, QFrame
)
from PyQt5.QtCore import Qt

import config_manager
from task_poller import TaskPollerThread

logger = logging.getLogger(__name__)

IOS_STYLE = """
QMainWindow, QWidget {
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
QPushButton#primary {
    background-color: #007AFF;
    color: #FFFFFF;
    border: none;
    border-radius: 10px;
    padding: 10px 0px;
    font-size: 13px;
    font-weight: 600;
}
QPushButton#primary:hover   { background-color: #0066DD; }
QPushButton#primary:pressed { background-color: #0055BB; }
QPushButton#primary:disabled { background-color: #C7C7CC; }
QPushButton#danger {
    background-color: #FF3B30;
    color: #FFFFFF;
    border: none;
    border-radius: 10px;
    padding: 10px 0px;
    font-size: 13px;
    font-weight: 600;
}
QPushButton#danger:hover   { background-color: #DD2A20; }
QPushButton#danger:disabled { background-color: #C7C7CC; }
QPushButton#secondary {
    background-color: #E5E5EA;
    color: #1C1C1E;
    border: none;
    border-radius: 10px;
    padding: 8px 0px;
    font-size: 12px;
}
QPushButton#secondary:hover { background-color: #D1D1D6; }
QPushButton#icon_btn {
    background-color: transparent;
    color: #007AFF;
    border: none;
    border-radius: 8px;
    padding: 5px;
    font-size: 11px;
}
QPushButton#icon_btn:hover { background-color: #E5F0FF; }
QTextEdit#log_display {
    background-color: #1C1C1E;
    color: #30D158;
    border: none;
    border-radius: 10px;
    padding: 8px;
    font-family: 'Menlo', 'SF Mono', 'Consolas', monospace;
    font-size: 11px;
}
QStatusBar {
    background-color: #F2F2F7;
    border-top: 1px solid #E5E5EA;
    font-size: 10px;
    color: #8E8E93;
    padding: 1px 6px;
}
"""


def _card(parent_layout, margin=(10, 8, 10, 8), spacing=6):
    frame = QFrame()
    frame.setObjectName('card')
    inner = QVBoxLayout(frame)
    inner.setContentsMargins(*margin)
    inner.setSpacing(spacing)
    parent_layout.addWidget(frame)
    return frame, inner


def _btn(text, obj='secondary', h=36):
    b = QPushButton(text)
    b.setObjectName(obj)
    b.setFixedHeight(h)
    b.setCursor(Qt.PointingHandCursor)
    return b


def _section(text):
    lbl = QLabel(text.upper())
    lbl.setStyleSheet('font-size:10px; font-weight:600; color:#8E8E93; letter-spacing:0.5px;')
    return lbl


class MainWindow(QMainWindow):
    """主窗口"""

    def __init__(self):
        super().__init__()
        self.task_poller = None
        self.setStyleSheet(IOS_STYLE)
        self._position_right()
        self._build_ui()
        self._start_poller()

    # ── 定位 ──────────────────────────────────────────────────────────────────

    def _position_right(self):
        from PyQt5.QtWidgets import QApplication
        screen  = QApplication.desktop().screenGeometry()
        w       = max(260, int(screen.width() * 0.20))
        self.setGeometry(screen.width() - w, 0, w, screen.height())
        self.setMinimumWidth(220)
        self.setMaximumWidth(int(screen.width() * 0.30))
        self.setWindowTitle('🤖 AutoBrowser')
        self.setWindowFlags(
            Qt.Window |
            Qt.WindowStaysOnTopHint |
            Qt.WindowCloseButtonHint |
            Qt.WindowMinimizeButtonHint
        )

    # ── UI ────────────────────────────────────────────────────────────────────

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(10, 10, 10, 6)
        root.setSpacing(8)

        # 標題行
        top = QHBoxLayout()
        title = QLabel('🤖 AutoBrowser')
        title.setStyleSheet('font-size:13px; font-weight:700; color:#1C1C1E;')
        top.addWidget(title)
        top.addStretch()
        root.addLayout(top)

        # 狀態卡片
        _, status_card = _card(root, margin=(10, 10, 10, 10), spacing=6)

        self.status_label = QLabel('⏸ 未運行')
        self.status_label.setStyleSheet('font-size:12px; color:#8E8E93;')
        self.status_label.setWordWrap(True)
        status_card.addWidget(self.status_label)

        self.active_label = QLabel('活躍任務: 0')
        self.active_label.setStyleSheet('font-size:11px; color:#8E8E93;')
        status_card.addWidget(self.active_label)

        self.countdown_label = QLabel('')
        self.countdown_label.setStyleSheet('font-size:11px; color:#8E8E93;')
        status_card.addWidget(self.countdown_label)

        # 控制按鈕 — 三個並排
        _, ctrl_card = _card(root, margin=(8, 8, 8, 8), spacing=0)
        btn_row = QHBoxLayout()
        btn_row.setSpacing(6)

        self.btn_start = _btn('▶ 啟動', 'primary', 36)
        self.btn_start.clicked.connect(self._start_poller)
        btn_row.addWidget(self.btn_start)

        self.btn_stop = _btn('⏹ 停止', 'danger', 36)
        self.btn_stop.clicked.connect(self._stop_poller)
        self.btn_stop.setEnabled(False)
        btn_row.addWidget(self.btn_stop)

        self.btn_settings = _btn('⚙ 設定', 'secondary', 36)
        self.btn_settings.clicked.connect(self._open_settings)
        btn_row.addWidget(self.btn_settings)

        ctrl_card.addLayout(btn_row)

        # 日誌
        log_row = QHBoxLayout()
        log_row.addWidget(_section('Log'))
        log_row.addStretch()
        btn_clear = _btn('✖', 'icon_btn', 22)
        btn_clear.setFixedWidth(22)
        btn_clear.setToolTip('清除日誌')
        btn_clear.clicked.connect(self._clear_log)
        log_row.addWidget(btn_clear)
        root.addLayout(log_row)

        self.log_display = QTextEdit()
        self.log_display.setObjectName('log_display')
        self.log_display.setReadOnly(True)
        self.log_display.setPlaceholderText('日誌輸出...')
        root.addWidget(self.log_display, stretch=1)

        # 狀態欄
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage('就緒')

    # ── 掃單控制 ──────────────────────────────────────────────────────────────

    def _start_poller(self):
        if self.task_poller and self.task_poller.isRunning():
            return

        cfg = config_manager.load_config()
        if not cfg.get('server_url') or not cfg.get('api_key'):
            self.log('⚠️ 後端 URL 或 API Key 未設定，請先在設定中配置')
            return

        self.task_poller = TaskPollerThread(self)
        self.task_poller.log_signal.connect(self.log)
        self.task_poller.task_started_signal.connect(
            lambda ono: self._on_task_started(ono)
        )
        self.task_poller.task_done_signal.connect(
            lambda ono, ok: self._on_task_done(ono, ok)
        )
        self.task_poller.countdown_signal.connect(self._on_countdown)
        self.task_poller.start()

        self.btn_start.setEnabled(False)
        self.btn_stop.setEnabled(True)
        self.status_label.setText('🔄 掃單運行中')
        self.status_label.setStyleSheet('font-size:12px; color:#30D158;')

    def _stop_poller(self):
        if self.task_poller and self.task_poller.isRunning():
            self.task_poller.stop()
            self.task_poller.wait(3000)
        self.btn_start.setEnabled(True)
        self.btn_stop.setEnabled(False)
        self.status_label.setText('⏸ 已停止')
        self.status_label.setStyleSheet('font-size:12px; color:#8E8E93;')
        self.countdown_label.setText('')

    def _on_task_started(self, order_no: str):
        self.log(f'🚀 任務已啟動: {order_no}')
        self._refresh_active_count()

    def _on_task_done(self, order_no: str, success: bool):
        icon = '✅' if success else '❌'
        word = '完成' if success else '失敗'
        self.log(f'{icon} 任務{word}: {order_no}')
        self._refresh_active_count()

    def _on_countdown(self, remaining: int):
        if remaining == 0:
            self.countdown_label.setText('⟳ 掃單中...')
            self.countdown_label.setStyleSheet('font-size:11px; color:#64D2FF;')
        else:
            cfg      = config_manager.load_config()
            interval = int(cfg.get('poll_interval', 10))
            self.countdown_label.setText(f'下次掃單: {remaining}s / {interval}s')
            self.countdown_label.setStyleSheet('font-size:11px; color:#8E8E93;')

    def _refresh_active_count(self):
        if self.task_poller:
            count = sum(
                1 for t in self.task_poller._active_threads.values()
                if t.isRunning()
            )
            self.active_label.setText(f'活躍任務: {count}')

    # ── 設定 ──────────────────────────────────────────────────────────────────

    def _open_settings(self):
        from settings_dialog import SettingsDialog
        dlg = SettingsDialog(self)
        if dlg.exec_():
            # 設定保存後重啟掃單（如果正在運行）
            was_running = self.task_poller and self.task_poller.isRunning()
            if was_running:
                self._stop_poller()
                self._start_poller()

    # ── 日誌 ──────────────────────────────────────────────────────────────────

    def log(self, msg: str):
        ts        = time.strftime('%H:%M:%S')
        formatted = f'[{ts}] {msg}'
        self.status_bar.showMessage(formatted)

        msg_str = str(msg)
        if any(k in msg_str for k in ['❌', 'error', '錯誤', '失敗', 'failed']):
            color = '#FF453A'
        elif any(k in msg_str for k in ['⚠️', 'warning', '警告', '驗證碼']):
            color = '#FFD60A'
        elif any(k in msg_str for k in ['✅', 'complete', '完成', 'success', '成功']):
            color = '#30D158'
        elif any(k in msg_str for k in ['▶', '步驟', 'Step', '🚀', '🔄']):
            color = '#64D2FF'
        else:
            color = '#98989D'

        safe = formatted.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
        self.log_display.append(f'<span style="color:{color};">{safe}</span>')
        sb = self.log_display.verticalScrollBar()
        sb.setValue(sb.maximum())

    def _clear_log(self):
        self.log_display.clear()
        self.status_bar.showMessage('就緒')

    # ── 關閉 ──────────────────────────────────────────────────────────────────

    def closeEvent(self, event):
        if self.task_poller and self.task_poller.isRunning():
            self.task_poller.stop()
            self.task_poller.wait(3000)
        event.accept()
