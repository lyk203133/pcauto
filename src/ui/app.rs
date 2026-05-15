use std::sync::{Arc, Mutex};
use tokio::sync::mpsc;

use crate::config::load_config;
use crate::models::{AppConfig, AppState, LogEntry};
use crate::poller::{PollEvent, Poller};
use crate::ui::settings::SettingsPanel;

/// eframe App 主體
pub struct AutoBrowserApp {
    cfg: AppConfig,
    state: Arc<Mutex<AppState>>,
    poller: Option<Poller>,
    event_rx: Option<mpsc::UnboundedReceiver<PollEvent>>,
    event_tx: mpsc::UnboundedSender<PollEvent>,
    settings: SettingsPanel,
    #[allow(dead_code)]
    rt: Arc<tokio::runtime::Runtime>,
}

impl AutoBrowserApp {
    pub fn new(rt: Arc<tokio::runtime::Runtime>, cc: &eframe::CreationContext<'_>) -> Self {
        setup_fonts(&cc.egui_ctx);

        let cfg = load_config();
        let state = Arc::new(Mutex::new(AppState::default()));
        let settings = SettingsPanel::new(&cfg);
        let (event_tx, event_rx) = mpsc::unbounded_channel();

        AutoBrowserApp {
            cfg,
            state,
            poller: None,
            event_rx: Some(event_rx),
            event_tx,
            settings,
            rt,
        }
    }

    fn is_running(&self) -> bool {
        self.poller.is_some()
    }

    fn start_poller(&mut self) {
        if self.poller.is_some() {
            return;
        }
        if self.cfg.server_url.is_empty() || self.cfg.api_key.is_empty() {
            self.state
                .lock()
                .unwrap()
                .push_log("⚠️ 後端 URL 或 API Key 未設定，請先在設定中配置");
            return;
        }

        let (tx, rx) = mpsc::unbounded_channel();
        self.event_rx = Some(rx);
        self.event_tx = tx.clone();

        let state_clone = Arc::clone(&self.state);

        // 用 catch_unwind 包裹，避免 panic 導致整個 GUI 崩潰
        let result = std::panic::catch_unwind(std::panic::AssertUnwindSafe(|| {
            Poller::start(tx, state_clone)
        }));

        match result {
            Ok(poller) => {
                self.poller = Some(poller);
                let mut s = self.state.lock().unwrap();
                s.is_running = true;
                s.status = "掃單運行中".to_string();
            }
            Err(e) => {
                let msg = e
                    .downcast_ref::<String>()
                    .cloned()
                    .or_else(|| e.downcast_ref::<&str>().map(|s| s.to_string()))
                    .unwrap_or_else(|| "未知錯誤".to_string());
                self.state
                    .lock()
                    .unwrap()
                    .push_log(format!("❌ 啟動失敗: {msg}"));
            }
        }
    }

    fn stop_poller(&mut self) {
        if let Some(p) = self.poller.take() {
            p.stop();
        }
        {
            let mut s = self.state.lock().unwrap();
            s.is_running = false;
            s.status = "已停止".to_string();
            s.countdown = 0;
            s.active_task_count = 0;
        }
    }

    fn drain_events(&mut self) {
        let rx = match self.event_rx.as_mut() {
            Some(r) => r,
            None => return,
        };
        let mut state = self.state.lock().unwrap();
        loop {
            match rx.try_recv() {
                Ok(event) => match event {
                    PollEvent::Log(msg) => state.push_log(msg),
                    PollEvent::TaskStarted(ono) => {
                        state.active_order_nos.insert(ono);
                        state.active_task_count = state.active_order_nos.len();
                    }
                    PollEvent::TaskDone(ono, _) => {
                        state.active_order_nos.remove(&ono);
                        state.active_task_count = state.active_order_nos.len();
                    }
                    PollEvent::Countdown(n) => state.countdown = n,
                    PollEvent::ActiveCount(n) => state.active_task_count = n,
                },
                Err(mpsc::error::TryRecvError::Empty) => break,
                Err(mpsc::error::TryRecvError::Disconnected) => {
                    state.is_running = false;
                    state.status = "已停止".to_string();
                    break;
                }
            }
        }
    }
}

impl eframe::App for AutoBrowserApp {
    fn update(&mut self, ctx: &egui::Context, _frame: &mut eframe::Frame) {
        self.drain_events();
        ctx.request_repaint_after(std::time::Duration::from_millis(500));

        // 擷取快照（Copy 類型，不持鎖）
        let (is_running, active_count, countdown) = {
            let s = self.state.lock().unwrap();
            (s.is_running, s.active_task_count, s.countdown)
        };
        let logs: Vec<LogEntry> = self.state.lock().unwrap().logs.iter().cloned().collect();

        egui::CentralPanel::default()
            .frame(
                egui::Frame::none()
                    .fill(egui::Color32::from_rgb(0xF2, 0xF2, 0xF7))
                    .inner_margin(egui::Margin {
                        left: 14.0,
                        right: 18.0,
                        top: 0.0,
                        bottom: 0.0,
                    }),
            )
            .show(ctx, |ui| {
                let available = ui.available_rect_before_wrap();
                let content_width = (available.width() - 12.0).max(0.0);
                egui::ScrollArea::vertical()
                    .max_width(content_width)
                    .auto_shrink([false, false])
                    .show(ui, |ui| {
                        ui.set_width(content_width);
                        ui.add_space(8.0);

                        // ── 標題 ──────────────────────────────────────────
                        ui.horizontal(|ui| {
                            ui.add_space(8.0);
                            ui.label(
                                egui::RichText::new("AutoBrowser")
                                    .size(16.0)
                                    .strong()
                                    .color(egui::Color32::from_rgb(0x1C, 0x1C, 0x1E)),
                            );
                        });
                        ui.add_space(6.0);

                        // ── 狀態卡片 ──────────────────────────────────────
                        egui::Frame::none()
                            .fill(egui::Color32::WHITE)
                            .rounding(12.0)
                            .inner_margin(egui::Margin::same(10.0))
                            .show(ui, |ui| {
                                ui.set_min_width(ui.available_width());
                                let (sc, st) = if is_running {
                                    (egui::Color32::from_rgb(0x30, 0xD1, 0x58), "🔄 掃單運行中")
                                } else {
                                    (egui::Color32::from_rgb(0x8E, 0x8E, 0x93), "⏸ 已停止")
                                };
                                let cd_text = if countdown == 0 && is_running {
                                    "⟳ 掃單中...".to_string()
                                } else if countdown > 0 {
                                    format!("{countdown}s")
                                } else {
                                    String::new()
                                };
                                let gray = egui::Color32::from_rgb(0x8E, 0x8E, 0x93);
                                ui.horizontal(|ui| {
                                    ui.colored_label(sc, st);
                                    ui.separator();
                                    ui.colored_label(gray, format!("任務: {active_count}"));
                                    if !cd_text.is_empty() {
                                        ui.separator();
                                        ui.colored_label(gray, &cd_text);
                                    }
                                });
                            });

                        ui.add_space(8.0);

                        // ── 控制按鈕 ──────────────────────────────────────
                        egui::Frame::none()
                            .fill(egui::Color32::WHITE)
                            .rounding(12.0)
                            .inner_margin(egui::Margin::same(8.0))
                            .show(ui, |ui| {
                                ui.set_min_width(ui.available_width());
                                ui.horizontal(|ui| {
                                    let bw = ((ui.available_width() - 12.0) / 3.0).max(60.0);

                                    if ui
                                        .add_enabled(
                                            !is_running,
                                            egui::Button::new(
                                                egui::RichText::new("▶ 啟動")
                                                    .color(egui::Color32::WHITE),
                                            )
                                            .fill(egui::Color32::from_rgb(0x00, 0x7A, 0xFF))
                                            .min_size(egui::vec2(bw, 36.0)),
                                        )
                                        .clicked()
                                    {
                                        self.start_poller();
                                    }

                                    ui.add_space(6.0);

                                    if ui
                                        .add_enabled(
                                            is_running,
                                            egui::Button::new(
                                                egui::RichText::new("⏹ 停止")
                                                    .color(egui::Color32::WHITE),
                                            )
                                            .fill(egui::Color32::from_rgb(0xFF, 0x3B, 0x30))
                                            .min_size(egui::vec2(bw, 36.0)),
                                        )
                                        .clicked()
                                    {
                                        self.stop_poller();
                                    }

                                    ui.add_space(6.0);

                                    if ui
                                        .add(
                                            egui::Button::new("⚙ 設定")
                                                .min_size(egui::vec2(bw, 36.0)),
                                        )
                                        .clicked()
                                    {
                                        let cfg = self.cfg.clone();
                                        self.settings.open(&cfg);
                                    }
                                });
                            });

                        ui.add_space(8.0);

                        // ── 日誌標題 ──────────────────────────────────────
                        ui.horizontal(|ui| {
                            ui.add_space(4.0);
                            ui.label(
                                egui::RichText::new("LOG")
                                    .size(10.0)
                                    .strong()
                                    .color(egui::Color32::from_rgb(0x8E, 0x8E, 0x93)),
                            );
                            ui.with_layout(
                                egui::Layout::right_to_left(egui::Align::Center),
                                |ui| {
                                    if ui.small_button("✖").clicked() {
                                        self.state.lock().unwrap().logs.clear();
                                    }
                                },
                            );
                        });

                        ui.add_space(4.0);

                        // ── 日誌面板 ──────────────────────────────────────
                        let log_height = (available.height() - 260.0).max(200.0);
                        let log_inner_height = (log_height - 16.0).max(160.0);
                        egui::Frame::none()
                            .fill(egui::Color32::from_rgb(0x1C, 0x1C, 0x1E))
                            .rounding(10.0)
                            .inner_margin(egui::Margin::same(8.0))
                            .show(ui, |ui| {
                                ui.set_min_width(ui.available_width());
                                ui.set_min_height(log_inner_height);
                                egui::ScrollArea::vertical()
                                    .id_salt("log_scroll")
                                    .max_height(log_inner_height)
                                    .min_scrolled_height(log_inner_height)
                                    .auto_shrink([false, false])
                                    .stick_to_bottom(true)
                                    .show(ui, |ui| {
                                        for entry in &logs {
                                            ui.label(
                                                egui::RichText::new(format!(
                                                    "[{}] {}",
                                                    entry.timestamp, entry.message
                                                ))
                                                .size(11.0)
                                                .monospace()
                                                .color(entry.egui_color()),
                                            );
                                        }
                                    });
                            });

                        ui.add_space(4.0);
                    });
            });

        // 設定面板
        if let Some(new_cfg) = self.settings.show(ctx) {
            let was_running = self.is_running();
            if was_running {
                self.stop_poller();
            }
            self.cfg = new_cfg;
            if was_running {
                self.start_poller();
            }
        }
    }

    fn on_exit(&mut self, _gl: Option<&eframe::glow::Context>) {
        self.stop_poller();
    }

    fn clear_color(&self, _visuals: &egui::Visuals) -> [f32; 4] {
        [0.949, 0.949, 0.969, 1.0] // #F2F2F7
    }
}

/// 載入系統 CJK 字體，支援中文顯示
fn setup_fonts(ctx: &egui::Context) {
    let mut fonts = egui::FontDefinitions::default();

    // macOS 字體路徑（按優先級）
    #[cfg(target_os = "macos")]
    let candidates = vec![
        "/System/Library/Fonts/PingFang.ttc",
        "/System/Library/Fonts/STHeiti Light.ttc",
        "/System/Library/Fonts/Hiragino Sans GB.ttc",
    ];

    #[cfg(target_os = "windows")]
    let candidates = vec![
        "C:\\Windows\\Fonts\\msyh.ttc",   // 微軟雅黑
        "C:\\Windows\\Fonts\\simsun.ttc", // 宋體
    ];

    #[cfg(target_os = "linux")]
    let candidates = vec![
        "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    ];

    #[cfg(not(any(target_os = "macos", target_os = "windows", target_os = "linux")))]
    let candidates: Vec<&str> = vec![];

    for path in &candidates {
        if let Ok(data) = std::fs::read(path) {
            fonts
                .font_data
                .insert("cjk".to_owned(), egui::FontData::from_owned(data));
            // 作為 fallback 加在預設字體後面
            for family in [egui::FontFamily::Proportional, egui::FontFamily::Monospace] {
                fonts
                    .families
                    .entry(family)
                    .or_default()
                    .push("cjk".to_owned());
            }
            tracing::info!("已載入字體: {path}");
            break;
        }
    }

    ctx.set_fonts(fonts);
}
