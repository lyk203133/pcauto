"""
database.py - MySQL 資料庫模組
用於偵測 trader 資料庫中的 orders 訂單並執行任務
"""

import time
import logging
import pymysql
from datetime import datetime
from typing import Optional, List, Dict, Any

logger = logging.getLogger(__name__)

# 預設資料庫配置
DEFAULT_DB_CONFIG = {
    'host': 'localhost',
    'user': 'root',
    'password': '123456',
    'database': 'trader',
    'charset': 'utf8mb4',
    'port': 3306
}


class DatabaseManager:
    """資料庫管理器"""

    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or DEFAULT_DB_CONFIG.copy()
        self.connection = None
        self.cursor = None

    def connect(self) -> bool:
        """連接到資料庫"""
        try:
            self.connection = pymysql.connect(
                host=self.config['host'],
                user=self.config['user'],
                password=self.config['password'],
                database=self.config['database'],
                charset=self.config.get('charset', 'utf8mb4'),
                port=self.config.get('port', 3306),
                cursorclass=pymysql.cursors.DictCursor
            )
            self.cursor = self.connection.cursor()
            logger.info(f"成功連接到資料庫: {self.config['host']}/{self.config['database']}")
            return True
        except Exception as e:
            logger.error(f"連接資料庫失敗: {e}")
            return False

    def disconnect(self):
        """斷開資料庫連接"""
        try:
            if self.cursor:
                self.cursor.close()
            if self.connection:
                self.connection.close()
            logger.info("已斷開資料庫連接")
        except Exception as e:
            logger.error(f"斷開連接時出錯: {e}")

    def ensure_order_task_table(self) -> bool:
        """確保 order_task 表存在"""
        try:
            create_table_sql = """
            CREATE TABLE IF NOT EXISTS order_task (
                id INT AUTO_INCREMENT PRIMARY KEY,
                order_no VARCHAR(64) NOT NULL UNIQUE,
                status ENUM('pending', 'processing', 'completed', 'failed') DEFAULT 'pending',
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                started_at DATETIME NULL,
                completed_at DATETIME NULL,
                error_message TEXT NULL,
                retry_count INT DEFAULT 0,
                INDEX idx_status (status),
                INDEX idx_created_at (created_at),
                INDEX idx_order_no (order_no)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
            """
            self.cursor.execute(create_table_sql)
            self.connection.commit()
            logger.info("order_task 表已就緒")
            return True
        except Exception as e:
            logger.error(f"創建 order_task 表失敗: {e}")
            return False

    def get_direct_orders(self) -> List[Dict]:
        """獲取所有 channel='DIRECT' 的訂單"""
        try:
            sql = """
            SELECT order_no, created_at 
            FROM orders 
            WHERE channel = 'DIRECT' 
            AND created_at >= DATE_SUB(NOW(), INTERVAL 7 DAY)
            ORDER BY created_at DESC
            """
            self.cursor.execute(sql)
            return self.cursor.fetchall()
        except Exception as e:
            logger.error(f"查詢 DIRECT 訂單失敗: {e}")
            return []

    def get_pending_tasks(self, limit: int = 10) -> List[Dict]:
        """獲取待處理的任務"""
        try:
            sql = """
            SELECT id, order_no, created_at, retry_count
            FROM order_task 
            WHERE status IN ('pending', 'failed')
            AND retry_count < 3
            ORDER BY created_at ASC
            LIMIT %s
            """
            self.cursor.execute(sql, (limit,))
            return self.cursor.fetchall()
        except Exception as e:
            logger.error(f"查詢待處理任務失敗: {e}")
            return []

    def add_order_to_task(self, order_no: str) -> bool:
        """將訂單添加到任務隊列"""
        try:
            sql = """
            INSERT IGNORE INTO order_task (order_no, status, created_at)
            VALUES (%s, 'pending', NOW())
            """
            self.cursor.execute(sql, (order_no,))
            self.connection.commit()
            return True
        except Exception as e:
            logger.error(f"添加任務失敗: {e}")
            return False

    def update_task_status(self, order_no: str, status: str, error_message: str = None):
        """更新任務狀態"""
        try:
            if status == 'processing':
                sql = """
                UPDATE order_task 
                SET status = %s, started_at = NOW(), error_message = NULL
                WHERE order_no = %s
                """
            elif status == 'completed':
                sql = """
                UPDATE order_task 
                SET status = %s, completed_at = NOW()
                WHERE order_no = %s
                """
            elif status == 'failed':
                sql = """
                UPDATE order_task 
                SET status = %s, retry_count = retry_count + 1, error_message = %s
                WHERE order_no = %s
                """
                self.cursor.execute(sql, (status, error_message, order_no))
                self.connection.commit()
                return
            else:
                sql = "UPDATE order_task SET status = %s WHERE order_no = %s"
            
            self.cursor.execute(sql, (status, order_no))
            self.connection.commit()
        except Exception as e:
            logger.error(f"更新任務狀態失敗: {e}")

    def get_task_by_order_no(self, order_no: str) -> Optional[Dict]:
        """根據訂單號獲取任務"""
        try:
            sql = "SELECT * FROM order_task WHERE order_no = %s"
            self.cursor.execute(sql, (order_no,))
            return self.cursor.fetchone()
        except Exception as e:
            logger.error(f"查詢任務失敗: {e}")
            return None

    def sync_direct_orders(self) -> int:
        """同步 DIRECT 訂單到任務隊列"""
        count = 0
        direct_orders = self.get_direct_orders()
        
        for order in direct_orders:
            order_no = order['order_no']
            # 檢查是否已存在
            existing = self.get_task_by_order_no(order_no)
            if not existing:
                if self.add_order_to_task(order_no):
                    count += 1
                    logger.info(f"新增任務: {order_no}")
        
        return count

    def get_statistics(self) -> Dict:
        """獲取任務統計"""
        try:
            sql = """
            SELECT 
                COUNT(*) as total,
                SUM(CASE WHEN status = 'pending' THEN 1 ELSE 0 END) as pending,
                SUM(CASE WHEN status = 'processing' THEN 1 ELSE 0 END) as processing,
                SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) as completed,
                SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) as failed
            FROM order_task
            """
            self.cursor.execute(sql)
            result = self.cursor.fetchone()
            return result or {}
        except Exception as e:
            logger.error(f"獲取統計失敗: {e}")
            return {}

    def test_connection(self) -> tuple:
        """測試資料庫連接"""
        try:
            if self.connect():
                # 測試查詢
                self.cursor.execute("SELECT DATABASE() as db")
                db_name = self.cursor.fetchone()['db']
                
                # 確保 order_task 表存在
                self.ensure_order_task_table()
                
                self.disconnect()
                return True, f"連接成功: {db_name}"
            else:
                return False, "連接失敗"
        except Exception as e:
            return False, f"錯誤: {str(e)}"


class OrderMonitor:
    """訂單監控器 - 定時掃描新訂單"""

    def __init__(self, db_manager: DatabaseManager, callback=None):
        self.db = db_manager
        self.callback = callback  # 回調函數：當有新任務時調用
        self.is_running = False
        self.scan_interval = 30  # 默認30秒

    def start(self, interval: int = 30):
        """開始監控"""
        self.is_running = True
        self.scan_interval = interval
        logger.info(f"訂單監控已啟動，間隔: {interval}秒")

    def stop(self):
        """停止監控"""
        self.is_running = False
        logger.info("訂單監控已停止")

    def scan_once(self) -> List[Dict]:
        """執行一次掃描"""
        if not self.db.connection or not self.db.connection.open:
            if not self.db.connect():
                return []

        # 同步新訂單
        new_count = self.db.sync_direct_orders()
        if new_count > 0:
            logger.info(f"發現 {new_count} 個新訂單")

        # 獲取待處理任務
        tasks = self.db.get_pending_tasks(limit=10)
        
        # 觸發回調
        if tasks and self.callback:
            for task in tasks:
                self.callback(task)

        return tasks

    def run_loop(self):
        """運行監控循環"""
        while self.is_running:
            try:
                self.scan_once()
            except Exception as e:
                logger.error(f"監控循環出錯: {e}")
            
            # 等待下一次掃描
            for _ in range(self.scan_interval):
                if not self.is_running:
                    break
                time.sleep(1)
