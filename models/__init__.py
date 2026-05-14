"""
任務數據模型
定義任務步驟和網站任務的數據結構
"""

from datetime import datetime


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
        from i18n import t
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
