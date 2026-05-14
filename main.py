"""
自動化瀏覽器工具 — 入口
直接啟動主窗口，無需登入
"""
import sys
import logging

from PyQt5.QtWidgets import QApplication

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('automation.log', encoding='utf-8'),
        logging.StreamHandler(),
    ]
)

logger = logging.getLogger(__name__)


def main():
    app = QApplication(sys.argv)
    app.setApplicationName('AutoBrowser')

    from main_window import MainWindow
    window = MainWindow()
    window.show()

    logger.info('AutoBrowser 已啟動')
    sys.exit(app.exec_())


if __name__ == '__main__':
    main()
