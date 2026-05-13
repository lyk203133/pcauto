"""
i18n - 多國語言支援模組
支援：繁體中文 (zh_TW)、英文 (en)、越南文 (vi)
"""

import os
from typing import Dict, List, Tuple

# 當前語言
_current_lang = "zh_TW"

# 翻譯字典
TRANSLATIONS: Dict[str, Dict[str, str]] = {
    "zh_TW": {
        # === 主窗口 ===
        "app_title": "自動化瀏覽器工具 v2.0",
        "ready": "就緒",

        # === 選單 ===
        "menu_file": "檔案",
        "menu_new_task": "新建任務",
        "menu_import_task": "導入任務...",
        "menu_exit": "退出",
        "menu_help": "幫助",
        "menu_about": "關於",
        "menu_language": "語言",

        # === 工具列 ===
        "toolbar_run": "▶ 運行任務",
        "toolbar_stop": "⏹ 停止",
        "toolbar_pause": "⏸ 暫停",
        "toolbar_resume": "▶ 繼續",
        "toolbar_captcha_resolved": "✅ 驗證碼已解決",

        # === 任務面板 ===
        "panel_task_list": "📋 網站任務列表",
        "btn_new": "➕ 新建",
        "btn_edit": "✏️ 編輯",
        "btn_delete": "🗑 刪除",
        "btn_refresh": "🔄 刷新列表",

        # === 工作面板 ===
        "tab_task_detail": "📄 任務詳情",
        "tab_execution_log": "📜 執行日誌",
        "tab_browser_config": "⚙️ 瀏覽器配置",
        "select_task_hint": "選擇左側任務查看詳情",
        "btn_clear_log": "🗑 清空日誌",

        # === 任務詳情 ===
        "detail_domain": "🌐 域名:",
        "detail_description": "📝 描述:",
        "detail_none": "無",
        "detail_steps_count": "📊 步驟數:",
        "detail_steps_title": "📋 操作步驟",

        # === 步驟操作 ===
        "step_goto": "🌐 打開網址",
        "step_click": "🖱️ 點擊元素",
        "step_fill": "📝 填寫文本",
        "step_type": "⌨️ 逐字輸入",
        "step_hover": "👆 懸停",
        "step_scroll_down": "📜 向下滾動",
        "step_scroll_up": "📜 向上滾動",
        "step_screenshot": "📸 截圖",
        "step_wait": "⏱️ 等待",
        "step_js": "⚡ 執行JS",

        # === 步驟詳情 ===
        "detail_open": "打開",
        "detail_click": "點擊",
        "detail_fill": "填寫",
        "detail_type": "輸入",
        "detail_scroll": "滾動",
        "detail_screenshot": "截圖:",
        "detail_wait": "等待",
        "detail_seconds": "秒",
        "detail_exec_js": "執行JavaScript",

        # === 代理配置 ===
        "config_proxy": "🔌 代理設置",
        "config_proxy_type": "類型:",
        "config_proxy_none": "無代理",
        "config_proxy_address": "地址:",
        "config_proxy_placeholder": "例: 127.0.0.1:7890 或 user:pass@host:port",

        # === 瀏覽器配置 ===
        "config_browser": "🌐 瀏覽器配置",
        "config_browser_label": "瀏覽器:",
        "config_browser_chrome": "🌐 系統 Chrome",
        "config_browser_cloak": "🕵️ CloakBrowser (防檢測)",
        "config_headless": "無頭模式 (隱藏瀏覽器)",
        "config_humanize": "人類行為模擬 (建議勾選)",
        "config_geoip": "地理IP匹配 (僅代理模式)",

        # === 任務編輯對話框 ===
        "dialog_edit_task": "編輯網站任務",
        "dialog_new_task": "新建網站任務",
        "dialog_task_info": "📋 任務資訊",
        "dialog_task_name": "任務名稱:",
        "dialog_task_name_placeholder": "例如: 範例網站登入",
        "dialog_domain": "網站域名:",
        "dialog_domain_placeholder": "例如: https://example.com",
        "dialog_description": "描述:",
        "dialog_desc_placeholder": "任務描述（可選）",
        "dialog_steps": "📊 操作步驟",
        "dialog_col_index": "序號",
        "dialog_col_type": "類型",
        "dialog_col_params": "參數",
        "dialog_col_wait": "等待(秒)",
        "dialog_btn_add_step": "➕ 添加步驟",
        "dialog_btn_insert_step": "📥 插入步驟",
        "dialog_btn_remove_step": "🗑 刪除選中",
        "dialog_btn_move_up": "⬆️ 上移",
        "dialog_btn_move_down": "⬇️ 下移",

        # === 步驟參數標籤 ===
        "param_url": "網址 (URL)",
        "param_selector": "CSS 選擇器",
        "param_value": "文本內容",
        "param_amount": "滾動像素",
        "param_name": "文件名",
        "param_seconds": "等待秒數",
        "param_code": "JavaScript 代碼",
        "param_wait_after": "步驟後等待:",
        "param_selector_type": "選擇器類型:",
        "param_action_target": "操作目標:",
        "param_text_value": "文本內容:",
        "param_scroll_amount": "滾動量:",
        "param_wait_seconds": "等待時間:",

        # === 選擇器類型 ===
        "selector_id": "ID (#id)",
        "selector_class": "類別 (.class)",
        "selector_tag": "標籤 (tag)",
        "selector_xpath": "XPath",

        # === 常用選擇器預設 ===
        "common_btn_submit": "提交按鈕 (#submit, .btn-submit)",
        "common_btn_click": "可點擊按鈕 (.btn, button)",
        "common_input_text": "文本輸入框 (input[type=text])",
        "common_input_password": "密碼輸入框 (input[type=password])",
        "common_link": "連結 (a)",
        "common_checkbox": "核取方塊 (input[type=checkbox])",
        "common_select": "下拉選單 (select)",
        "common_div": "DIV 容器 (div)",
        "common_span": "SPAN 文字 (span)",
        "common_form": "表單 (form)",

        # === 滾動量預設 ===
        "scroll_small": "小滾動 (200px)",
        "scroll_medium": "中等滾動 (500px)",
        "scroll_large": "大滾動 (800px)",
        "scroll_full": "整頁滾動 (1000px)",

        # === 等待時間預設 ===
        "wait_quick": "快速 (1秒)",
        "wait_short": "短等待 (2秒)",
        "wait_normal": "正常 (3秒)",
        "wait_long": "長等待 (5秒)",
        "wait_extra": "超長等待 (10秒)",
        "wait_minute": "一分鐘 (60秒)",

        # === 步驟編輯對話框 ===
        "dialog_edit_step": "編輯步驟",
        "dialog_step_type": "步驟類型:",
        "dialog_edit_params": "📝 步驟參數",

        # === 驗證消息 ===
        "msg_warning": "提示",
        "msg_error": "錯誤",
        "msg_info": "資訊",
        "msg_please_select_task": "請先選擇要刪除的任務",
        "msg_please_select_task_to_run": "請先在左側選擇要執行的任務",
        "msg_no_steps": "該任務沒有任何步驟，請先編輯添加步驟",
        "msg_enter_task_name": "請輸入任務名稱",
        "msg_enter_domain": "請輸入網站域名",
        "msg_confirm_delete": "確認刪除",
        "msg_confirm_delete_task": "確定刪除任務「{name}」嗎？",
        "msg_import_failed": "導入失敗: {error}",
        "msg_import_success": "📥 已導入任務: {name}",
        "msg_task_created": "✅ 已創建任務: {name}",
        "msg_task_updated": "✅ 已更新任務: {name}",
        "msg_task_deleted": "🗑 已刪除任務: {name}",
        "msg_tasks_loaded": "📂 已載入 {count} 個任務",

        # === 執行狀態 ===
        "status_running": "運行中",
        "status_stopped": "已停止",
        "status_paused": "已暫停",
        "status_stopping": "正在停止...",
        "msg_no_running_task": "⚠️ 沒有正在運行的任務",
        "msg_user_stopped": "⏹ 用戶停止執行",
        "msg_task_stopped": "⏹ 任務已停止",
        "msg_task_complete": "✅ 任務執行完成",
        "msg_task_error": "❌ 任務異常: {error}",

        # === 瀏覽器啟動 ===
        "browser_starting": "🚀 正在啟動瀏覽器...",
        "browser_using_chrome": "🌐 使用系統 Chrome 瀏覽器",
        "browser_using_cloak": "🕵️ 使用 CloakBrowser 隱身瀏覽器",
        "browser_first_run_hint": "💡 首次運行可能需要下載瀏覽器...",
        "browser_found_chrome": "📍 找到 Chrome: {path}",
        "browser_attempt": "🔄 啟動嘗試 {current}/{total}...",
        "browser_chrome_success": "✅ Chrome 瀏覽器啟動成功",
        "browser_cloak_success": "✅ CloakBrowser 啟動成功",
        "browser_start_failed_retry": "⚠️ 啟動失敗: {error}，重試中...",
        "browser_start_failed": "⚠️ 啟動失敗，重試中...",

        # === 代理 ===
        "proxy_using": "📡 使用代理: {proxy}",
        "geoip_enabled": "🌍 啟用地理IP匹配",
        "local_mode": "🏠 本地模式",

        # === 任務執行 ===
        "task_start": "📋 開始執行任務: {name}",
        "task_target": "🌐 目標網站: {domain}",
        "task_total_steps": "📊 共 {count} 個步驟",
        "step_executing": "▶ 步驟 {current}/{total}",
        "step_complete": "✅ 步驟 {current} 完成",
        "step_may_failed": "⚠️ 步驟 {current} 可能失敗",
        "step_stopped": "⏹ 已停止",
        "step_execute_failed": "   ❌ 執行失敗: {error}",

        # === 步驟動作日誌 ===
        "log_goto": "   🌐 打開: {url}",
        "log_click": "   🖱️ 點擊: {selector}",
        "log_fill": "   📝 填寫: {selector} = {value}...",
        "log_type": "   ⌨️ 輸入: {selector}",
        "log_hover": "   👆 懸停: {selector}",
        "log_scroll_down": "   📜 向下滾動 {amount}px",
        "log_scroll_up": "   📜 向上滾動 {amount}px",
        "log_screenshot": "   📸 截圖: {path}",
        "log_wait": "   ⏱️ 等待 {seconds} 秒",
        "log_js": "   ⚡ 執行JS代碼",

        # === 驗證碼 ===
        "captcha_detected": "⚠️ 檢測到驗證碼!",
        "captcha_hint": "檢測到驗證碼，請手動填寫後點擊\"驗證碼已解決\"",
        "captcha_resolved": "✅ 驗證碼已解決",
        "captcha_user_confirmed": "✅ 用戶確認驗證碼已解決",

        # === 執行錯誤 ===
        "error_execute": "❌ 錯誤: {error}",
        "error_network_hint": "💡 提示: 請檢查網絡連接，或嘗試關閉代理/geoip",

        # === 關於 ===
        "about_title": "關於",
        "about_text": "自動化瀏覽器工具 v2.0\n\n基於 CloakBrowser + PyQt5\n\n一個網站 = 一個任務文件\n支援驗證碼檢測和用戶介入",

        # === 語言 ===
        "lang_zh_TW": "繁體中文",
        "lang_en": "English",
        "lang_vi": "Tiếng Việt",

        # === 快捷預設 ===
        "preset_custom": "自訂...",

        # === 按鈕 ===
        "btn_ok": "確定",
        "btn_cancel": "取消",

        # === 資料庫功能 ===
        "tab_database": "💾 資料庫",
        "menu_database": "資料庫",
        "menu_db_connect": "連接資料庫",
        "menu_db_sync": "同步訂單",
        "menu_db_start_monitor": "開始監控",
        "menu_db_stop_monitor": "停止監控",

        # === 資料庫配置 ===
        "db_config_title": "📀 資料庫配置",
        "db_host": "主機",
        "db_port": "端口",
        "db_user": "用戶名",
        "db_password": "密碼",
        "db_database": "資料庫",
        "db_btn_test": "🔍 測試連接",
        "db_btn_connect": "🔗 連接",
        "db_btn_sync": "🔄 同步訂單",
        "db_btn_start_monitor": "▶ 開始監控",
        "db_btn_stop_monitor": "⏹ 停止監控",

        # === 監控配置 ===
        "db_monitor_title": "📡 訂單監控",
        "db_monitor_interval": "掃描間隔",
        "db_monitor_running": "監控中 (間隔 {interval} 秒)",
        "db_monitor_stopped": "已停止",
        "db_monitor_already_running": "監控已在運行",

        # === 任務隊列 ===
        "db_task_queue": "📋 任務隊列",
        "db_order_no": "訂單號",
        "db_status": "狀態",
        "db_created_at": "創建時間",

        # === 資料庫狀態 ===
        "db_status_info": "總計: {total} | 待處理: {pending} | 已完成: {completed}",
        "db_status_disconnected": "未連接資料庫",
        "db_status_connected": "已連接",

        # === 資料庫操作 ===
        "db_connected": "✅ 資料庫連接成功: {msg}",
        "db_connect_failed": "❌ 資料庫連接失敗: {msg}",
        "db_connect_error": "❌ 資料庫錯誤: {error}",
        "db_connect_success": "資料庫連接成功",
        "db_not_connected": "請先連接資料庫",
        "db_test_success": "✅ 連接測試成功: {msg}",
        "db_test_failed": "❌ 連接測試失敗: {msg}",

        # === 訂單同步 ===
        "db_sync_complete": "✅ 同步完成，新增 {count} 個任務",
        "db_sync_result": "已同步 {count} 個新訂單",
        "db_found_tasks": "發現 {count} 個待處理任務",
        "db_new_order": "📦 新訂單: {order_no}",
        "db_no_tasks_configured": "沒有配置任務",

        # === 任務執行 ===
        "task_order_no": "📦 訂單號: {order_no}",
        "db_task_completed": "✅ 任務完成: {order_no}",
        "db_task_failed": "❌ 任務失敗: {order_no} - {error}",
        "db_monitor_started": "📡 監控已啟動 (間隔 {interval} 秒)",
    },

    "en": {
        # === Main Window ===
        "app_title": "Automation Browser Tool v2.0",
        "ready": "Ready",

        # === Menu ===
        "menu_file": "File",
        "menu_new_task": "New Task",
        "menu_import_task": "Import Task...",
        "menu_exit": "Exit",
        "menu_help": "Help",
        "menu_about": "About",
        "menu_language": "Language",

        # === Toolbar ===
        "toolbar_run": "▶ Run Task",
        "toolbar_stop": "⏹ Stop",
        "toolbar_pause": "⏸ Pause",
        "toolbar_resume": "▶ Resume",
        "toolbar_captcha_resolved": "✅ Captcha Resolved",

        # === Task Panel ===
        "panel_task_list": "📋 Website Task List",
        "btn_new": "➕ New",
        "btn_edit": "✏️ Edit",
        "btn_delete": "🗑 Delete",
        "btn_refresh": "🔄 Refresh List",

        # === Work Panel ===
        "tab_task_detail": "📄 Task Details",
        "tab_execution_log": "📜 Execution Log",
        "tab_browser_config": "⚙️ Browser Config",
        "select_task_hint": "Select a task on the left to view details",
        "btn_clear_log": "🗑 Clear Log",

        # === Task Detail ===
        "detail_domain": "🌐 Domain:",
        "detail_description": "📝 Description:",
        "detail_none": "None",
        "detail_steps_count": "📊 Steps:",
        "detail_steps_title": "📋 Operation Steps",

        # === Step Types ===
        "step_goto": "🌐 Open URL",
        "step_click": "🖱️ Click Element",
        "step_fill": "📝 Fill Text",
        "step_type": "⌨️ Type Text",
        "step_hover": "👆 Hover",
        "step_scroll_down": "📜 Scroll Down",
        "step_scroll_up": "📜 Scroll Up",
        "step_screenshot": "📸 Screenshot",
        "step_wait": "⏱️ Wait",
        "step_js": "⚡ Execute JS",

        # === Step Details ===
        "detail_open": "Open",
        "detail_click": "Click",
        "detail_fill": "Fill",
        "detail_type": "Type",
        "detail_scroll": "Scroll",
        "detail_screenshot": "Screenshot:",
        "detail_wait": "Wait",
        "detail_seconds": "seconds",
        "detail_exec_js": "Execute JavaScript",

        # === Proxy Config ===
        "config_proxy": "🔌 Proxy Settings",
        "config_proxy_type": "Type:",
        "config_proxy_none": "No Proxy",
        "config_proxy_address": "Address:",
        "config_proxy_placeholder": "e.g: 127.0.0.1:7890 or user:pass@host:port",

        # === Browser Config ===
        "config_browser": "🌐 Browser Config",
        "config_browser_label": "Browser:",
        "config_browser_chrome": "🌐 System Chrome",
        "config_browser_cloak": "🕵️ CloakBrowser (Anti-detect)",
        "config_headless": "Headless Mode (Hide Browser)",
        "config_humanize": "Human Behavior Simulation (Recommended)",
        "config_geoip": "Geo IP Matching (Proxy Mode Only)",

        # === Task Edit Dialog ===
        "dialog_edit_task": "Edit Website Task",
        "dialog_new_task": "New Website Task",
        "dialog_task_info": "📋 Task Info",
        "dialog_task_name": "Task Name:",
        "dialog_task_name_placeholder": "e.g: Example Site Login",
        "dialog_domain": "Website Domain:",
        "dialog_domain_placeholder": "e.g: https://example.com",
        "dialog_description": "Description:",
        "dialog_desc_placeholder": "Task description (optional)",
        "dialog_steps": "📊 Operation Steps",
        "dialog_col_index": "#",
        "dialog_col_type": "Type",
        "dialog_col_params": "Parameters",
        "dialog_col_wait": "Wait(s)",
        "dialog_btn_add_step": "➕ Add Step",
        "dialog_btn_insert_step": "📥 Insert Step",
        "dialog_btn_remove_step": "🗑 Delete Selected",
        "dialog_btn_move_up": "⬆️ Move Up",
        "dialog_btn_move_down": "⬇️ Move Down",

        # === Parameter Labels ===
        "param_url": "URL",
        "param_selector": "CSS Selector",
        "param_value": "Text Content",
        "param_amount": "Scroll Pixels",
        "param_name": "Filename",
        "param_seconds": "Wait Seconds",
        "param_code": "JavaScript Code",
        "param_wait_after": "Wait After Step:",
        "param_selector_type": "Selector Type:",
        "param_action_target": "Target:",
        "param_text_value": "Text:",
        "param_scroll_amount": "Scroll Amount:",
        "param_wait_seconds": "Wait Time:",

        # === Selector Types ===
        "selector_id": "ID (#id)",
        "selector_class": "Class (.class)",
        "selector_tag": "Tag (tag)",
        "selector_xpath": "XPath",

        # === Common Selectors ===
        "common_btn_submit": "Submit Button (#submit, .btn-submit)",
        "common_btn_click": "Clickable Button (.btn, button)",
        "common_input_text": "Text Input (input[type=text])",
        "common_input_password": "Password Input (input[type=password])",
        "common_link": "Link (a)",
        "common_checkbox": "Checkbox (input[type=checkbox])",
        "common_select": "Dropdown (select)",
        "common_div": "DIV Container (div)",
        "common_span": "SPAN Text (span)",
        "common_form": "Form (form)",

        # === Scroll Amounts ===
        "scroll_small": "Small (200px)",
        "scroll_medium": "Medium (500px)",
        "scroll_large": "Large (800px)",
        "scroll_full": "Full Page (1000px)",

        # === Wait Times ===
        "wait_quick": "Quick (1s)",
        "wait_short": "Short (2s)",
        "wait_normal": "Normal (3s)",
        "wait_long": "Long (5s)",
        "wait_extra": "Extra Long (10s)",
        "wait_minute": "One Minute (60s)",

        # === Step Edit Dialog ===
        "dialog_edit_step": "Edit Step",
        "dialog_step_type": "Step Type:",
        "dialog_edit_params": "📝 Step Parameters",

        # === Messages ===
        "msg_warning": "Warning",
        "msg_error": "Error",
        "msg_info": "Info",
        "msg_please_select_task": "Please select a task to delete first",
        "msg_please_select_task_to_run": "Please select a task to run on the left first",
        "msg_no_steps": "This task has no steps. Please edit and add steps first",
        "msg_enter_task_name": "Please enter a task name",
        "msg_enter_domain": "Please enter a website domain",
        "msg_confirm_delete": "Confirm Delete",
        "msg_confirm_delete_task": "Are you sure you want to delete task \"{name}\"?",
        "msg_import_failed": "Import failed: {error}",
        "msg_import_success": "📥 Task imported: {name}",
        "msg_task_created": "✅ Task created: {name}",
        "msg_task_updated": "✅ Task updated: {name}",
        "msg_task_deleted": "🗑 Task deleted: {name}",
        "msg_tasks_loaded": "📂 Loaded {count} tasks",

        # === Execution Status ===
        "status_running": "Running",
        "status_stopped": "Stopped",
        "status_paused": "Paused",
        "status_stopping": "Stopping...",
        "msg_no_running_task": "⚠️ No task is currently running",
        "msg_user_stopped": "⏹ User stopped execution",
        "msg_task_stopped": "⏹ Task stopped",
        "msg_task_complete": "✅ Task execution completed",
        "msg_task_error": "❌ Task error: {error}",

        # === Browser Startup ===
        "browser_starting": "🚀 Starting browser...",
        "browser_using_chrome": "🌐 Using system Chrome browser",
        "browser_using_cloak": "🕵️ Using CloakBrowser stealth browser",
        "browser_first_run_hint": "💡 First run may require downloading browser...",
        "browser_found_chrome": "📍 Found Chrome: {path}",
        "browser_attempt": "🔄 Startup attempt {current}/{total}...",
        "browser_chrome_success": "✅ Chrome browser started successfully",
        "browser_cloak_success": "✅ CloakBrowser started successfully",
        "browser_start_failed_retry": "⚠️ Startup failed: {error}, retrying...",
        "browser_start_failed": "⚠️ Startup failed, retrying...",

        # === Proxy ===
        "proxy_using": "📡 Using proxy: {proxy}",
        "geoip_enabled": "🌍 Geo IP matching enabled",
        "local_mode": "🏠 Local mode",

        # === Task Execution ===
        "task_start": "📋 Starting task: {name}",
        "task_target": "🌐 Target website: {domain}",
        "task_total_steps": "📊 Total {count} steps",
        "step_executing": "▶ Step {current}/{total}",
        "step_complete": "✅ Step {current} completed",
        "step_may_failed": "⚠️ Step {current} may have failed",
        "step_stopped": "⏹ Stopped",
        "step_execute_failed": "   ❌ Execute failed: {error}",

        # === Step Action Logs ===
        "log_goto": "   🌐 Open: {url}",
        "log_click": "   🖱️ Click: {selector}",
        "log_fill": "   📝 Fill: {selector} = {value}...",
        "log_type": "   ⌨️ Type: {selector}",
        "log_hover": "   👆 Hover: {selector}",
        "log_scroll_down": "   📜 Scroll down {amount}px",
        "log_scroll_up": "   📜 Scroll up {amount}px",
        "log_screenshot": "   📸 Screenshot: {path}",
        "log_wait": "   ⏱️ Wait {seconds} seconds",
        "log_js": "   ⚡ Execute JS code",

        # === Captcha ===
        "captcha_detected": "⚠️ Captcha detected!",
        "captcha_hint": "Captcha detected. Please manually solve it and click \"Captcha Resolved\"",
        "captcha_resolved": "✅ Captcha resolved",
        "captcha_user_confirmed": "✅ User confirmed captcha resolved",

        # === Execution Errors ===
        "error_execute": "❌ Error: {error}",
        "error_network_hint": "💡 Hint: Please check network connection, or try disabling proxy/geoip",

        # === About ===
        "about_title": "About",
        "about_text": "Automation Browser Tool v2.0\n\nBased on CloakBrowser + PyQt5\n\nOne website = One task file\nSupports captcha detection and user intervention",

        # === Language ===
        "lang_zh_TW": "繁體中文",
        "lang_en": "English",
        "lang_vi": "Tiếng Việt",

        # === Presets ===
        "preset_custom": "Custom...",

        # === Buttons ===
        "btn_ok": "OK",
        "btn_cancel": "Cancel",

        # === Database Features ===
        "tab_database": "💾 Database",
        "menu_database": "Database",
        "menu_db_connect": "Connect Database",
        "menu_db_sync": "Sync Orders",
        "menu_db_start_monitor": "Start Monitor",
        "menu_db_stop_monitor": "Stop Monitor",

        # === Database Config ===
        "db_config_title": "📀 Database Configuration",
        "db_host": "Host",
        "db_port": "Port",
        "db_user": "Username",
        "db_password": "Password",
        "db_database": "Database",
        "db_btn_test": "🔍 Test Connection",
        "db_btn_connect": "🔗 Connect",
        "db_btn_sync": "🔄 Sync Orders",
        "db_btn_start_monitor": "▶ Start Monitor",
        "db_btn_stop_monitor": "⏹ Stop Monitor",

        # === Monitor Config ===
        "db_monitor_title": "📡 Order Monitor",
        "db_monitor_interval": "Scan Interval",
        "db_monitor_running": "Monitoring (interval {interval}s)",
        "db_monitor_stopped": "Stopped",
        "db_monitor_already_running": "Monitor already running",

        # === Task Queue ===
        "db_task_queue": "📋 Task Queue",
        "db_order_no": "Order No",
        "db_status": "Status",
        "db_created_at": "Created At",

        # === Database Status ===
        "db_status_info": "Total: {total} | Pending: {pending} | Completed: {completed}",
        "db_status_disconnected": "Database Disconnected",
        "db_status_connected": "Connected",

        # === Database Operations ===
        "db_connected": "✅ Database connected: {msg}",
        "db_connect_failed": "❌ Database connection failed: {msg}",
        "db_connect_error": "❌ Database error: {error}",
        "db_connect_success": "Database connected successfully",
        "db_not_connected": "Please connect to database first",
        "db_test_success": "✅ Connection test passed: {msg}",
        "db_test_failed": "❌ Connection test failed: {msg}",

        # === Order Sync ===
        "db_sync_complete": "✅ Sync complete, added {count} tasks",
        "db_sync_result": "Synced {count} new orders",
        "db_found_tasks": "Found {count} pending tasks",
        "db_new_order": "📦 New order: {order_no}",
        "db_no_tasks_configured": "No tasks configured",

        # === Task Execution ===
        "task_order_no": "📦 Order No: {order_no}",
        "db_task_completed": "✅ Task completed: {order_no}",
        "db_task_failed": "❌ Task failed: {order_no} - {error}",
        "db_monitor_started": "📡 Monitor started (interval {interval}s)",
    },

    "vi": {
        # === Cửa sổ chính ===
        "app_title": "Công Cụ Tự Động Hóa Trình Duyệt v2.0",
        "ready": "Sẵn sàng",

        # === Menu ===
        "menu_file": "Tệp",
        "menu_new_task": "Tạo Tác Vụ Mới",
        "menu_import_task": "Nhập Tác Vụ...",
        "menu_exit": "Thoát",
        "menu_help": "Trợ giúp",
        "menu_about": "Giới thiệu",
        "menu_language": "Ngôn ngữ",

        # === Thanh công cụ ===
        "toolbar_run": "▶ Chạy Tác Vụ",
        "toolbar_stop": "⏹ Dừng",
        "toolbar_pause": "⏸ Tạm dừng",
        "toolbar_resume": "▶ Tiếp tục",
        "toolbar_captcha_resolved": "✅ Captcha Đã Giải",

        # === Bảng tác vụ ===
        "panel_task_list": "📋 Danh Sách Tác Vụ Website",
        "btn_new": "➕ Tạo Mới",
        "btn_edit": "✏️ Chỉnh sửa",
        "btn_delete": "🗑 Xóa",
        "btn_refresh": "🔄 Làm mới danh sách",

        # === Bảng làm việc ===
        "tab_task_detail": "📄 Chi Tiết Tác Vụ",
        "tab_execution_log": "📜 Nhật Ký Thực Thi",
        "tab_browser_config": "⚙️ Cấu Hình Trình Duyệt",
        "select_task_hint": "Chọn tác vụ bên trái để xem chi tiết",
        "btn_clear_log": "🗑 Xóa nhật ký",

        # === Chi tiết tác vụ ===
        "detail_domain": "🌐 Tên miền:",
        "detail_description": "📝 Mô tả:",
        "detail_none": "Không có",
        "detail_steps_count": "📊 Số bước:",
        "detail_steps_title": "📋 Các Bước Thực Hiện",

        # === Loại bước ===
        "step_goto": "🌐 Mở URL",
        "step_click": "🖱️ Nhấp Phần Tử",
        "step_fill": "📝 Điền Văn Bản",
        "step_type": "⌨️ Nhập Từng Ký Tự",
        "step_hover": "👆 Di Chuột",
        "step_scroll_down": "📜 Cuộn Xuống",
        "step_scroll_up": "📜 Cuộn Lên",
        "step_screenshot": "📸 Chụp Màn Hình",
        "step_wait": "⏱️ Chờ",
        "step_js": "⚡ Thực Thi JS",

        # === Chi tiết bước ===
        "detail_open": "Mở",
        "detail_click": "Nhấp",
        "detail_fill": "Điền",
        "detail_type": "Nhập",
        "detail_scroll": "Cuộn",
        "detail_screenshot": "Chụp:",
        "detail_wait": "Chờ",
        "detail_seconds": "giây",
        "detail_exec_js": "Thực thi JavaScript",

        # === Cấu hình proxy ===
        "config_proxy": "🔌 Cài Đặt Proxy",
        "config_proxy_type": "Loại:",
        "config_proxy_none": "Không Proxy",
        "config_proxy_address": "Địa chỉ:",
        "config_proxy_placeholder": "VD: 127.0.0.1:7890 hoặc user:pass@host:port",

        # === Cấu hình trình duyệt ===
        "config_browser": "🌐 Cấu Hình Trình Duyệt",
        "config_browser_label": "Trình duyệt:",
        "config_browser_chrome": "🌐 Chrome Hệ Thống",
        "config_browser_cloak": "🕵️ CloakBrowser (Chống phát hiện)",
        "config_headless": "Chế độ ẩn (Ẩn trình duyệt)",
        "config_humanize": "Mô phỏng hành vi con người (Khuyến nghị)",
        "config_geoip": "Khớp Geo IP (Chỉ chế độ Proxy)",

        # === Hộp thoại chỉnh sửa tác vụ ===
        "dialog_edit_task": "Chỉnh Sửa Tác Vụ Website",
        "dialog_new_task": "Tạo Tác Vụ Website Mới",
        "dialog_task_info": "📋 Thông Tin Tác Vụ",
        "dialog_task_name": "Tên tác vụ:",
        "dialog_task_name_placeholder": "VD: Đăng nhập website mẫu",
        "dialog_domain": "Tên miền website:",
        "dialog_domain_placeholder": "VD: https://example.com",
        "dialog_description": "Mô tả:",
        "dialog_desc_placeholder": "Mô tả tác vụ (tùy chọn)",
        "dialog_steps": "📊 Các Bước Thực Hiện",
        "dialog_col_index": "STT",
        "dialog_col_type": "Loại",
        "dialog_col_params": "Tham số",
        "dialog_col_wait": "Chờ(giây)",
        "dialog_btn_add_step": "➕ Thêm Bước",
        "dialog_btn_insert_step": "📥 Chèn Bước",
        "dialog_btn_remove_step": "🗑 Xóa Đã Chọn",
        "dialog_btn_move_up": "⬆️ Lên",
        "dialog_btn_move_down": "⬇️ Xuống",

        # === Nhãn tham số ===
        "param_url": "URL",
        "param_selector": "CSS Selector",
        "param_value": "Nội dung văn bản",
        "param_amount": "Pixel cuộn",
        "param_name": "Tên file",
        "param_seconds": "Số giây chờ",
        "param_code": "Mã JavaScript",
        "param_wait_after": "Chờ sau bước:",
        "param_selector_type": "Loại bộ chọn:",
        "param_action_target": "Mục tiêu:",
        "param_text_value": "Văn bản:",
        "param_scroll_amount": "Lượng cuộn:",
        "param_wait_seconds": "Thời gian chờ:",

        # === Loại bộ chọn ===
        "selector_id": "ID (#id)",
        "selector_class": "Lớp (.class)",
        "selector_tag": "Thẻ (tag)",
        "selector_xpath": "XPath",

        # === Bộ chọn phổ biến ===
        "common_btn_submit": "Nút Gửi (#submit, .btn-submit)",
        "common_btn_click": "Nút Bấm (.btn, button)",
        "common_input_text": "Ô Nhập Văn Bản (input[type=text])",
        "common_input_password": "Ô Nhập Mật Khẩu (input[type=password])",
        "common_link": "Liên Kết (a)",
        "common_checkbox": "Hộp Kiểm (input[type=checkbox])",
        "common_select": "Danh Sách (select)",
        "common_div": "Thùng Chứa (div)",
        "common_span": "Văn Bản (span)",
        "common_form": "Biểu Mẫu (form)",

        # === Lượng cuộn ===
        "scroll_small": "Nhỏ (200px)",
        "scroll_medium": "Vừa (500px)",
        "scroll_large": "Lớn (800px)",
        "scroll_full": "Toàn Trang (1000px)",

        # === Thời gian chờ ===
        "wait_quick": "Nhanh (1 giây)",
        "wait_short": "Ngắn (2 giây)",
        "wait_normal": "Bình thường (3 giây)",
        "wait_long": "Dài (5 giây)",
        "wait_extra": "Rất Dài (10 giây)",
        "wait_minute": "Một Phút (60 giây)",

        # === Hộp thoại chỉnh sửa bước ===
        "dialog_edit_step": "Chỉnh Sửa Bước",
        "dialog_step_type": "Loại bước:",
        "dialog_edit_params": "📝 Tham Số Bước",

        # === Thông báo ===
        "msg_warning": "Cảnh báo",
        "msg_error": "Lỗi",
        "msg_info": "Thông tin",
        "msg_please_select_task": "Vui lòng chọn tác vụ cần xóa trước",
        "msg_please_select_task_to_run": "Vui lòng chọn tác vụ cần chạy ở bên trái trước",
        "msg_no_steps": "Tác vụ này không có bước nào. Vui lòng chỉnh sửa và thêm bước trước",
        "msg_enter_task_name": "Vui lòng nhập tên tác vụ",
        "msg_enter_domain": "Vui lòng nhập tên miền website",
        "msg_confirm_delete": "Xác nhận xóa",
        "msg_confirm_delete_task": "Bạn có chắc muốn xóa tác vụ \"{name}\"?",
        "msg_import_failed": "Nhập thất bại: {error}",
        "msg_import_success": "📥 Đã nhập tác vụ: {name}",
        "msg_task_created": "✅ Đã tạo tác vụ: {name}",
        "msg_task_updated": "✅ Đã cập nhật tác vụ: {name}",
        "msg_task_deleted": "🗑 Đã xóa tác vụ: {name}",
        "msg_tasks_loaded": "📂 Đã tải {count} tác vụ",

        # === Trạng thái thực thi ===
        "status_running": "Đang chạy",
        "status_stopped": "Đã dừng",
        "status_paused": "Đã tạm dừng",
        "status_stopping": "Đang dừng...",
        "msg_no_running_task": "⚠️ Không có tác vụ nào đang chạy",
        "msg_user_stopped": "⏹ Người dùng dừng thực thi",
        "msg_task_stopped": "⏹ Tác vụ đã dừng",
        "msg_task_complete": "✅ Tác vụ hoàn thành",
        "msg_task_error": "❌ Lỗi tác vụ: {error}",

        # === Khởi động trình duyệt ===
        "browser_starting": "🚀 Đang khởi động trình duyệt...",
        "browser_using_chrome": "🌐 Sử dụng trình duyệt Chrome hệ thống",
        "browser_using_cloak": "🕵️ Sử dụng CloakBrowser trình duyệt ẩn danh",
        "browser_first_run_hint": "💡 Lần chạy đầu tiên có thể cần tải trình duyệt...",
        "browser_found_chrome": "📍 Tìm thấy Chrome: {path}",
        "browser_attempt": "🔄 Lần thử khởi động {current}/{total}...",
        "browser_chrome_success": "✅ Trình duyệt Chrome khởi động thành công",
        "browser_cloak_success": "✅ CloakBrowser khởi động thành công",
        "browser_start_failed_retry": "⚠️ Khởi động thất bại: {error}, đang thử lại...",
        "browser_start_failed": "⚠️ Khởi động thất bại, đang thử lại...",

        # === Proxy ===
        "proxy_using": "📡 Sử dụng proxy: {proxy}",
        "geoip_enabled": "🌍 Đã bật khớp Geo IP",
        "local_mode": "🏠 Chế độ cục bộ",

        # === Thực thi tác vụ ===
        "task_start": "📋 Bắt đầu thực thi tác vụ: {name}",
        "task_target": "🌐 Website đích: {domain}",
        "task_total_steps": "📊 Tổng {count} bước",
        "step_executing": "▶ Bước {current}/{total}",
        "step_complete": "✅ Bước {current} hoàn thành",
        "step_may_failed": "⚠️ Bước {current} có thể thất bại",
        "step_stopped": "⏹ Đã dừng",
        "step_execute_failed": "   ❌ Thực thi thất bại: {error}",

        # === Nhật ký hành động bước ===
        "log_goto": "   🌐 Mở: {url}",
        "log_click": "   🖱️ Nhấp: {selector}",
        "log_fill": "   📝 Điền: {selector} = {value}...",
        "log_type": "   ⌨️ Nhập: {selector}",
        "log_hover": "   👆 Di chuột: {selector}",
        "log_scroll_down": "   📜 Cuộn xuống {amount}px",
        "log_scroll_up": "   📜 Cuộn lên {amount}px",
        "log_screenshot": "   📸 Chụp: {path}",
        "log_wait": "   ⏱️ Chờ {seconds} giây",
        "log_js": "   ⚡ Thực thi mã JS",

        # === Captcha ===
        "captcha_detected": "⚠️ Phát hiện captcha!",
        "captcha_hint": "Phát hiện captcha. Vui lòng giải thủ công rồi nhấn \"Captcha Đã Giải\"",
        "captcha_resolved": "✅ Captcha đã được giải",
        "captcha_user_confirmed": "✅ Người dùng xác nhận captcha đã giải",

        # === Lỗi thực thi ===
        "error_execute": "❌ Lỗi: {error}",
        "error_network_hint": "💡 Gợi ý: Vui lòng kiểm tra kết nối mạng, hoặc thử tắt proxy/geoip",

        # === Giới thiệu ===
        "about_title": "Giới thiệu",
        "about_text": "Công Cụ Tự Động Hóa Trình Duyệt v2.0\n\nDựa trên CloakBrowser + PyQt5\n\nMột website = Một tệp tác vụ\nHỗ trợ phát hiện captcha và can thiệp người dùng",

        # === Ngôn ngữ ===
        "lang_zh_TW": "繁體中文",
        "lang_en": "English",
        "lang_vi": "Tiếng Việt",

        # === Presets ===
        "preset_custom": "Tùy chỉnh...",

        # === Buttons ===
        "btn_ok": "Đồng ý",
        "btn_cancel": "Hủy",

        # === Tính năng cơ sở dữ liệu ===
        "tab_database": "💾 Cơ Sở Dữ Liệu",
        "menu_database": "Cơ Sở Dữ Liệu",
        "menu_db_connect": "Kết nối CSDL",
        "menu_db_sync": "Đồng bộ đơn hàng",
        "menu_db_start_monitor": "Bắt đầu giám sát",
        "menu_db_stop_monitor": "Dừng giám sát",

        # === Cấu hình CSDL ===
        "db_config_title": "📀 Cấu Hình Cơ Sở Dữ Liệu",
        "db_host": "Máy chủ",
        "db_port": "Cổng",
        "db_user": "Tên người dùng",
        "db_password": "Mật khẩu",
        "db_database": "Cơ sở dữ liệu",
        "db_btn_test": "🔍 Kiểm tra kết nối",
        "db_btn_connect": "🔗 Kết nối",
        "db_btn_sync": "🔄 Đồng bộ đơn hàng",
        "db_btn_start_monitor": "▶ Bắt đầu giám sát",
        "db_btn_stop_monitor": "⏹ Dừng giám sát",

        # === Cấu hình giám sát ===
        "db_monitor_title": "📡 Giám sát đơn hàng",
        "db_monitor_interval": "Khoảng quét",
        "db_monitor_running": "Đang giám sát (khoảng {interval} giây)",
        "db_monitor_stopped": "Đã dừng",
        "db_monitor_already_running": "Giám sát đang chạy",

        # === Hàng đợi tác vụ ===
        "db_task_queue": "📋 Hàng Đợi Tác Vụ",
        "db_order_no": "Số đơn hàng",
        "db_status": "Trạng thái",
        "db_created_at": "Thời gian tạo",

        # === Trạng thái CSDL ===
        "db_status_info": "Tổng: {total} | Chờ: {pending} | Hoàn thành: {completed}",
        "db_status_disconnected": "Chưa kết nối CSDL",
        "db_status_connected": "Đã kết nối",

        # === Thao tác CSDL ===
        "db_connected": "✅ Kết nối CSDL thành công: {msg}",
        "db_connect_failed": "❌ Kết nối CSDL thất bại: {msg}",
        "db_connect_error": "❌ Lỗi CSDL: {error}",
        "db_connect_success": "Kết nối CSDL thành công",
        "db_not_connected": "Vui lòng kết nối CSDL trước",
        "db_test_success": "✅ Kiểm tra kết nối thành công: {msg}",
        "db_test_failed": "❌ Kiểm tra kết nối thất bại: {msg}",

        # === Đồng bộ đơn hàng ===
        "db_sync_complete": "✅ Đồng bộ xong, thêm {count} tác vụ",
        "db_sync_result": "Đã đồng bộ {count} đơn hàng mới",
        "db_found_tasks": "Tìm thấy {count} tác vụ đang chờ",
        "db_new_order": "📦 Đơn hàng mới: {order_no}",
        "db_no_tasks_configured": "Chưa có tác vụ được cấu hình",

        # === Thực thi tác vụ ===
        "task_order_no": "📦 Số đơn hàng: {order_no}",
        "db_task_completed": "✅ Tác vụ hoàn thành: {order_no}",
        "db_task_failed": "❌ Tác vụ thất bại: {order_no} - {error}",
        "db_monitor_started": "📡 Bắt đầu giám sát (khoảng {interval} giây)",
    }
}


# ============================================================
# 預設選項配置
# ============================================================

# 滾動量預設 (值, 顯示名稱key)
SCROLL_PRESETS: List[Tuple[str, str]] = [
    ("200", "scroll_small"),
    ("500", "scroll_medium"),
    ("800", "scroll_large"),
    ("1000", "scroll_full"),
]

# 等待時間預設
WAIT_PRESETS: List[Tuple[str, str]] = [
    ("1", "wait_quick"),
    ("2", "wait_short"),
    ("3", "wait_normal"),
    ("5", "wait_long"),
    ("10", "wait_extra"),
    ("60", "wait_minute"),
]

# 選擇器類型
SELECTOR_TYPES: List[Tuple[str, str]] = [
    ("id", "selector_id"),
    ("class", "selector_class"),
    ("tag", "selector_tag"),
    ("xpath", "selector_xpath"),
]

# 常用選擇器預設
COMMON_SELECTORS: List[Tuple[str, str]] = [
    ("#submit", "common_btn_submit"),
    (".btn-submit", "common_btn_submit"),
    ("button[type=submit]", "common_btn_submit"),
    (".btn", "common_btn_click"),
    ("button", "common_btn_click"),
    (".btn-primary", "common_btn_click"),
    ("input[type=text]", "common_input_text"),
    ("input[name]", "common_input_text"),
    ("input[type=password]", "common_input_password"),
    ("input[type=email]", "common_input_text"),
    ("a", "common_link"),
    ("a[href]", "common_link"),
    ("input[type=checkbox]", "common_checkbox"),
    ("select", "common_select"),
    ("div", "common_div"),
    ("span", "common_span"),
    ("form", "common_form"),
]

# 步驟後等待時間預設
STEP_WAIT_PRESETS: List[Tuple[str, str]] = [
    ("1", "wait_quick"),
    ("2", "wait_short"),
    ("3", "wait_normal"),
    ("5", "wait_long"),
]


def get_current_lang() -> str:
    """獲取當前語言"""
    return _current_lang


def set_language(lang: str) -> bool:
    """設置當前語言"""
    global _current_lang
    if lang in TRANSLATIONS:
        _current_lang = lang
        return True
    return False


def t(key: str, **kwargs) -> str:
    """
    翻譯函數
    用法: t("app_title") 或 t("msg_confirm_delete", name="測試任務")
    """
    lang_dict = TRANSLATIONS.get(_current_lang, TRANSLATIONS["zh_TW"])
    text = lang_dict.get(key, key)

    # 替換參數
    if kwargs:
        try:
            text = text.format(**kwargs)
        except (KeyError, ValueError):
            pass

    return text


def get_scroll_presets() -> List[Tuple[str, str]]:
    """獲取滾動量預設列表"""
    return [(val, t(key)) for val, key in SCROLL_PRESETS]


def get_wait_presets() -> List[Tuple[str, str]]:
    """獲取等待時間預設列表"""
    return [(val, t(key)) for val, key in WAIT_PRESETS]


def get_selector_types() -> List[Tuple[str, str]]:
    """獲取選擇器類型列表"""
    return [(val, t(key)) for val, key in SELECTOR_TYPES]


def get_common_selectors() -> List[Tuple[str, str]]:
    """獲取常用選擇器列表"""
    return [(val, t(key)) for val, key in COMMON_SELECTORS]


def get_step_wait_presets() -> List[Tuple[str, str]]:
    """獲取步驟後等待時間預設"""
    return [(val, t(key)) for val, key in STEP_WAIT_PRESETS]


def get_preset_custom_key() -> str:
    """獲取自訂預設的翻譯key"""
    return "preset_custom"


def get_available_languages():
    """獲取可用語言列表"""
    return list(TRANSLATIONS.keys())


def get_language_name(lang_code: str) -> str:
    """獲取語言名稱"""
    return t.lang_names.get(lang_code, lang_code)


# 語言名稱映射（用於菜單顯示）
t.lang_names = {
    "zh_TW": "繁體中文",
    "en": "English",
    "vi": "Tiếng Việt"
}


def get_all_strings() -> Dict[str, str]:
    """獲取所有翻譯字串（調試用）"""
    return TRANSLATIONS.get(_current_lang, {})
