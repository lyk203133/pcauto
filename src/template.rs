use std::collections::HashMap;
use once_cell::sync::Lazy;
use regex::Regex;

static TEMPLATE_RE: Lazy<Regex> = Lazy::new(|| {
    Regex::new(r"\{\{\s*(\w+)\s*\}\}").expect("invalid template regex")
});

/// 替換字符串中的 {{variable}} 模板變量
/// 如果 key 不在 ctx 中，保留原始的 {{key}} 不變
pub fn render(value: &str, ctx: &HashMap<String, String>) -> String {
    TEMPLATE_RE.replace_all(value, |caps: &regex::Captures| {
        let key = caps[1].trim();
        ctx.get(key)
            .cloned()
            .unwrap_or_else(|| caps[0].to_string())
    }).into_owned()
}

/// 渲染 Option<String>，None 返回空字符串
pub fn render_opt(value: Option<&str>, ctx: &HashMap<String, String>) -> String {
    match value {
        Some(v) => render(v, ctx),
        None => String::new(),
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_render_basic() {
        let mut ctx = HashMap::new();
        ctx.insert("order_no".to_string(), "ORD001".to_string());
        ctx.insert("amount".to_string(), "100".to_string());

        assert_eq!(render("訂單 {{order_no}} 金額 {{amount}}", &ctx), "訂單 ORD001 金額 100");
    }

    #[test]
    fn test_render_missing_key() {
        let ctx = HashMap::new();
        assert_eq!(render("{{missing}}", &ctx), "{{missing}}");
    }

    #[test]
    fn test_render_no_template() {
        let ctx = HashMap::new();
        assert_eq!(render("plain text", &ctx), "plain text");
    }
}
