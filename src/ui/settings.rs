use crate::config::save_config;
use crate::models::AppConfig;

enum SettingsAction {
    Saved(AppConfig),
    Close,
}

/// 設定對話框狀態
pub struct SettingsPanel {
    pub open: bool,
    // 編輯中的臨時配置（未保存）
    pub draft: AppConfig,
    pub save_msg: Option<String>,
}

impl SettingsPanel {
    pub fn new(cfg: &AppConfig) -> Self {
        SettingsPanel {
            open: false,
            draft: cfg.clone(),
            save_msg: None,
        }
    }

    /// 打開設定面板，重置 draft
    pub fn open(&mut self, cfg: &AppConfig) {
        self.draft = cfg.clone();
        self.open = true;
        self.save_msg = None;
    }

    /// 渲染設定彈窗（native viewport）
    /// 返回 Some(AppConfig) 表示用戶保存了新配置
    pub fn show(&mut self, ctx: &egui::Context) -> Option<AppConfig> {
        if !self.open {
            return None;
        }

        let viewport_id = egui::ViewportId::from_hash_of("pcauto_settings_popup");
        let viewport = egui::ViewportBuilder::default()
            .with_title("設定")
            .with_inner_size([420.0, 450.0])
            .with_min_inner_size([380.0, 390.0])
            .with_resizable(false)
            .with_always_on_top()
            .with_active(true);

        let action = ctx.show_viewport_immediate(viewport_id, viewport, |ctx, class| {
            if ctx.input(|i| i.viewport().close_requested()) {
                return Some(SettingsAction::Close);
            }

            match class {
                egui::ViewportClass::Embedded => {
                    let mut window_open = true;
                    let mut action = None;
                    egui::Window::new("⚙ 設定")
                        .collapsible(false)
                        .resizable(false)
                        .min_width(360.0)
                        .open(&mut window_open)
                        .show(ctx, |ui| {
                            action = self.show_contents(ui);
                        });

                    if !window_open {
                        Some(SettingsAction::Close)
                    } else {
                        action
                    }
                }
                _ => {
                    let mut action = None;
                    egui::CentralPanel::default()
                        .frame(
                            egui::Frame::none()
                                .fill(egui::Color32::from_rgb(0xF2, 0xF2, 0xF7))
                                .inner_margin(egui::Margin::same(14.0)),
                        )
                        .show(ctx, |ui| {
                            ui.heading("⚙ 設定");
                            ui.add_space(10.0);
                            action = self.show_contents(ui);
                        });
                    action
                }
            }
        });

        match action {
            Some(SettingsAction::Saved(cfg)) => {
                self.open = false;
                ctx.send_viewport_cmd_to(viewport_id, egui::ViewportCommand::Close);
                Some(cfg)
            }
            Some(SettingsAction::Close) => {
                self.open = false;
                ctx.send_viewport_cmd_to(viewport_id, egui::ViewportCommand::Close);
                None
            }
            None => None,
        }
    }

    fn show_contents(&mut self, ui: &mut egui::Ui) -> Option<SettingsAction> {
        let mut action = None;

        egui::Grid::new("settings_grid")
            .num_columns(2)
            .spacing([12.0, 8.0])
            .show(ui, |ui| {
                ui.label("後端 URL:");
                ui.text_edit_singleline(&mut self.draft.server_url);
                ui.end_row();

                ui.label("API Key:");
                ui.add(
                    egui::TextEdit::singleline(&mut self.draft.api_key)
                        .password(true)
                        .desired_width(240.0),
                );
                ui.end_row();

                ui.label("HMAC Secret:");
                ui.add(
                    egui::TextEdit::singleline(&mut self.draft.hmac_secret)
                        .password(true)
                        .desired_width(240.0),
                );
                ui.end_row();

                ui.label("輪詢間隔 (秒):");
                let mut interval_str = self.draft.poll_interval.to_string();
                if ui.text_edit_singleline(&mut interval_str).changed() {
                    if let Ok(v) = interval_str.parse::<u64>() {
                        self.draft.poll_interval = v.max(1);
                    }
                }
                ui.end_row();

                ui.label("最大並發任務:");
                let mut max_tasks_str = self.draft.max_concurrent_tasks.to_string();
                if ui.text_edit_singleline(&mut max_tasks_str).changed() {
                    if let Ok(v) = max_tasks_str.parse::<usize>() {
                        self.draft.max_concurrent_tasks = v.max(1);
                    }
                }
                ui.end_row();

                ui.label("瀏覽器類型:");
                egui::ComboBox::from_id_salt("browser_type")
                    .selected_text(&self.draft.browser_type)
                    .show_ui(ui, |ui| {
                        ui.selectable_value(
                            &mut self.draft.browser_type,
                            "chrome".to_string(),
                            "Chrome",
                        );
                        ui.selectable_value(
                            &mut self.draft.browser_type,
                            "cloakbrowser".to_string(),
                            "CloakBrowser",
                        );
                    });
                ui.end_row();

                ui.label("打開瀏覽器:");
                ui.checkbox(&mut self.draft.show_browser, "顯示 Chrome 視窗");
                ui.end_row();

                ui.label("代理 (可選):");
                let mut proxy_str = self.draft.proxy.clone().unwrap_or_default();
                if ui.text_edit_singleline(&mut proxy_str).changed() {
                    self.draft.proxy = if proxy_str.is_empty() {
                        None
                    } else {
                        Some(proxy_str)
                    };
                }
                ui.end_row();
            });

        ui.add_space(8.0);

        if let Some(ref msg) = self.save_msg {
            ui.colored_label(egui::Color32::from_rgb(0x30, 0xD1, 0x58), msg);
            ui.add_space(4.0);
        }

        ui.horizontal(|ui| {
            if ui
                .add(
                    egui::Button::new(egui::RichText::new("保存").color(egui::Color32::WHITE))
                        .fill(egui::Color32::from_rgb(0x00, 0x7A, 0xFF)),
                )
                .clicked()
            {
                match save_config(&self.draft) {
                    Ok(()) => {
                        self.save_msg = Some("✅ 已保存".to_string());
                        action = Some(SettingsAction::Saved(self.draft.clone()));
                    }
                    Err(e) => {
                        self.save_msg = Some(format!("❌ 保存失敗: {e}"));
                    }
                }
            }

            if ui.button("取消").clicked() {
                action = Some(SettingsAction::Close);
            }
        });

        action
    }
}
