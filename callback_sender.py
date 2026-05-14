"""
回調發送器 — 任務完成/失敗後 POST 回調，帶 HMAC-SHA256 簽名
"""
import hmac
import hashlib
import time
import requests
import logging
from config_manager import load_config

logger = logging.getLogger(__name__)


def send_callback(task_id: int, order_no: str, status: int) -> bool:
    """
    發送回調到後端
    status: 2=完成, 3=失敗
    簽名算法: HMAC-SHA256(hmac_secret, order_no + "|" + status + "|" + timestamp)
    """
    cfg = load_config()
    server_url = cfg.get('server_url', '').rstrip('/')
    api_key    = cfg.get('api_key', '')
    secret     = cfg.get('hmac_secret', '')

    if not server_url or not api_key:
        logger.warning('回調 URL 或 API Key 未設定，跳過回調')
        return False

    callback_url = f'{server_url}/api/pcauto/callback'
    timestamp    = int(time.time())
    msg          = f'{order_no}|{status}|{timestamp}'
    sign         = hmac.new(secret.encode(), msg.encode(), hashlib.sha256).hexdigest()

    payload = {
        'task_id':  task_id,
        'order_no': order_no,
        'status':   status,
        'timestamp': timestamp,
        'sign':     sign,
    }

    try:
        resp = requests.post(
            callback_url,
            json=payload,
            headers={'X-Pcauto-Key': api_key},
            timeout=10,
        )
        if resp.status_code == 200 and resp.json().get('success'):
            logger.info(f'回調成功: {order_no} status={status}')
            return True
        else:
            logger.error(f'回調失敗: {resp.status_code} {resp.text}')
            return False
    except Exception as e:
        logger.error(f'回調異常: {e}')
        return False
