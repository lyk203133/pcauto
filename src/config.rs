use crate::models::AppConfig;
use anyhow::Result;
use std::path::PathBuf;

fn config_path() -> PathBuf {
    // 開發模式優先使用當前目錄；打包後再使用 exe 旁邊的 config.json。
    let cwd_config = PathBuf::from("config.json");
    if cwd_config.exists() {
        return cwd_config;
    }

    if let Ok(exe) = std::env::current_exe() {
        if let Some(parent) = exe.parent() {
            return parent.join("config.json");
        }
    }
    PathBuf::from("config.json")
}

/// 載入配置，缺失字段用 Default 填充
pub fn load_config() -> AppConfig {
    let path = config_path();
    if path.exists() {
        match std::fs::read_to_string(&path) {
            Ok(content) => {
                match serde_json::from_str::<serde_json::Value>(&content) {
                    Ok(mut val) => {
                        // 把預設值補充進去（缺失的 key 用 default 填充）
                        let default = AppConfig::default();
                        let default_val = serde_json::to_value(&default).unwrap_or_default();
                        if let (Some(obj), Some(dobj)) =
                            (val.as_object_mut(), default_val.as_object())
                        {
                            for (k, v) in dobj {
                                obj.entry(k).or_insert_with(|| v.clone());
                            }
                        }
                        if let Ok(cfg) = serde_json::from_value(val) {
                            return cfg;
                        }
                    }
                    Err(e) => {
                        tracing::warn!("config.json 解析失敗: {e}，使用默認配置");
                    }
                }
            }
            Err(e) => {
                tracing::warn!("讀取 config.json 失敗: {e}，使用默認配置");
            }
        }
    }
    AppConfig::default()
}

/// 保存配置到 config.json
pub fn save_config(cfg: &AppConfig) -> Result<()> {
    let path = config_path();
    let content = serde_json::to_string_pretty(cfg)?;
    std::fs::write(&path, content)?;
    Ok(())
}
