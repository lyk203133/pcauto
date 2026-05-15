use anyhow::Result;
use hmac::{Hmac, Mac};
use sha2::Sha256;
use std::time::{SystemTime, UNIX_EPOCH};

use crate::models::AppConfig;

type HmacSha256 = Hmac<Sha256>;

/// 計算 HMAC-SHA256 簽名
/// message = "{order_no}|{status}|{timestamp}"
pub fn compute_hmac(secret: &str, order_no: &str, status: i32, timestamp: u64) -> String {
    let message = format!("{order_no}|{status}|{timestamp}");
    let mut mac =
        HmacSha256::new_from_slice(secret.as_bytes()).expect("HMAC can take key of any size");
    mac.update(message.as_bytes());
    let result = mac.finalize();
    hex::encode(result.into_bytes())
}

/// 發送任務完成回調
/// status: 2=完成, 3=失敗
pub async fn send_callback(
    client: &reqwest::Client,
    cfg: &AppConfig,
    task_id: u64,
    order_no: &str,
    status: i32,
    reason: &str,
    failure_image_data: Option<&str>,
) -> Result<bool> {
    let server_url = cfg.server_url.trim_end_matches('/');
    if server_url.is_empty() || cfg.api_key.is_empty() {
        tracing::warn!("回調 URL 或 API Key 未設定，跳過回調");
        return Ok(false);
    }

    let callback_url = format!("{server_url}/api/pcauto/callback");
    let timestamp = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .unwrap_or_default()
        .as_secs();

    let sign = compute_hmac(&cfg.hmac_secret, order_no, status, timestamp);

    let mut payload = serde_json::json!({
        "task_id": task_id,
        "order_no": order_no,
        "status": status,
        "reason": reason,
        "error_msg": if status == 3 { reason } else { "" },
        "timestamp": timestamp,
        "sign": sign,
    });
    if let Some(image_data) = failure_image_data.map(str::trim).filter(|v| !v.is_empty()) {
        payload["failure_image_data"] = serde_json::json!(image_data);
    }

    let resp = client
        .post(&callback_url)
        .header("X-Pcauto-Key", &cfg.api_key)
        .json(&payload)
        .timeout(std::time::Duration::from_secs(10))
        .send()
        .await?;

    let status_code = resp.status();
    if status_code.is_success() {
        let body: serde_json::Value = resp.json().await.unwrap_or_default();
        if body
            .get("success")
            .and_then(|v| v.as_bool())
            .unwrap_or(false)
        {
            tracing::info!("回調成功: {order_no} status={status}");
            return Ok(true);
        }
        tracing::error!("回調失敗（業務錯誤）: {body}");
    } else {
        tracing::error!("回調失敗 HTTP {status_code}: {order_no}");
    }
    Ok(false)
}

/// 發送步驟進度回調
pub async fn send_step_callback(
    client: &reqwest::Client,
    cfg: &AppConfig,
    task_id: u64,
    order_no: &str,
    step: &str,
    step_name: &str,
    action: &str,
    attempt: u64,
    max_retries: u64,
    status: &str,
    message: &str,
    reason: Option<&str>,
) {
    let server_url = cfg.server_url.trim_end_matches('/');
    if server_url.is_empty() || cfg.api_key.is_empty() {
        return;
    }
    let url = format!("{server_url}/api/pcauto/step-callback");
    let payload = serde_json::json!({
        "task_id": task_id,
        "order_no": order_no,
        "step": step,
        "step_name": step_name,
        "action": action,
        "attempt": attempt,
        "max_retries": max_retries,
        "status": status,
        "message": message,
        "reason": reason.unwrap_or(""),
    });
    let result = client
        .post(&url)
        .header("X-Pcauto-Key", &cfg.api_key)
        .json(&payload)
        .timeout(std::time::Duration::from_secs(4))
        .send()
        .await;
    if let Err(e) = result {
        tracing::debug!("步驟回調失敗（非致命）: {e}");
    }
}

/// 通知後端需要 GA 碼
pub async fn request_ga(
    client: &reqwest::Client,
    cfg: &AppConfig,
    task_id: u64,
    order_no: &str,
    variable: &str,
) {
    let server_url = cfg.server_url.trim_end_matches('/');
    if server_url.is_empty() || cfg.api_key.is_empty() {
        return;
    }
    let url = format!("{server_url}/api/pcauto/request-ga");
    let payload = serde_json::json!({
        "task_id": task_id,
        "order_no": order_no,
        "variable": variable,
    });
    let result = client
        .post(&url)
        .header("X-Pcauto-Key", &cfg.api_key)
        .json(&payload)
        .timeout(std::time::Duration::from_secs(5))
        .send()
        .await;
    if let Err(e) = result {
        tracing::warn!("request-ga 失敗: {e}");
    }
}

/// 回傳圖形驗證碼圖片，通知後端讓會員端輸入
pub async fn request_captcha(
    client: &reqwest::Client,
    cfg: &AppConfig,
    task_id: u64,
    order_no: &str,
    image_data: &str,
    variable: &str,
) -> bool {
    let server_url = cfg.server_url.trim_end_matches('/');
    if server_url.is_empty() || cfg.api_key.is_empty() {
        return false;
    }
    let url = format!("{server_url}/api/pcauto/request-captcha");
    let payload = serde_json::json!({
        "task_id": task_id,
        "order_no": order_no,
        "image_data": image_data,
        "variable": variable,
    });
    let result = client
        .post(&url)
        .header("X-Pcauto-Key", &cfg.api_key)
        .json(&payload)
        .timeout(std::time::Duration::from_secs(10))
        .send()
        .await;

    match result {
        Ok(resp) => resp.status().is_success(),
        Err(e) => {
            tracing::warn!("request-captcha 失敗: {e}");
            false
        }
    }
}

/// 輪詢後端直到 GA 碼填入，最多等 timeout_sec 秒
/// 返回 GA 碼（空字符串表示超時）
pub async fn poll_ga(
    client: &reqwest::Client,
    cfg: &AppConfig,
    task_id: u64,
    timeout_sec: u64,
    should_stop: &std::sync::atomic::AtomicBool,
) -> String {
    use std::sync::atomic::Ordering;

    let server_url = cfg.server_url.trim_end_matches('/');
    if server_url.is_empty() || cfg.api_key.is_empty() {
        return String::new();
    }
    let url = format!("{server_url}/api/pcauto/get-ga");
    let deadline = std::time::Instant::now() + std::time::Duration::from_secs(timeout_sec);

    while std::time::Instant::now() < deadline {
        if should_stop.load(Ordering::Relaxed) {
            return String::new();
        }
        let result = client
            .get(&url)
            .header("X-Pcauto-Key", &cfg.api_key)
            .query(&[("task_id", task_id.to_string())])
            .timeout(std::time::Duration::from_secs(5))
            .send()
            .await;

        if let Ok(resp) = result {
            if let Ok(data) = resp.json::<crate::models::GetGaResponse>().await {
                if data.ready {
                    if let Some(code) = data.ga_code.or(data.code) {
                        if !code.is_empty() {
                            return code;
                        }
                    }
                }
            }
        }
        // GA 碼時效短，1s 輪詢
        tokio::time::sleep(std::time::Duration::from_secs(1)).await;
    }
    String::new()
}
