"""
任務管理服務
負責任務的加載、保存、刪除等操作
"""

import json
import logging
from pathlib import Path
from typing import Optional

from models import SiteTask

logger = logging.getLogger(__name__)

# 任務文件目錄
TASKS_DIR = "tasks"


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

    def get(self, domain: str) -> Optional[SiteTask]:
        return self.tasks.get(domain)

    def get_all(self):
        """獲取所有任務"""
        return list(self.tasks.values())

    def _safe_filename(self, domain: str) -> str:
        return domain.replace('/', '_').replace('\\', '_').replace(':', '_')
