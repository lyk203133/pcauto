#![cfg_attr(target_os = "windows", windows_subsystem = "windows")]

mod browser;
mod callback;
mod config;
mod models;
mod poller;
mod template;
mod ui;

use std::sync::Arc;
use ui::app::AutoBrowserApp;

fn main() {
    tracing_subscriber::fmt()
        .with_env_filter(
            tracing_subscriber::EnvFilter::try_from_default_env()
                .unwrap_or_else(|_| tracing_subscriber::EnvFilter::new("info")),
        )
        .init();

    let rt = Arc::new(
        tokio::runtime::Builder::new_multi_thread()
            .enable_all()
            .build()
            .expect("tokio runtime"),
    );

    // 必須 enter runtime，才能讓 GUI 線程上的 tokio::spawn() 正常工作
    let _guard = rt.enter();

    let native_options = eframe::NativeOptions {
        viewport: egui::ViewportBuilder::default()
            .with_title("🤖 AutoBrowser")
            .with_always_on_top()
            .with_inner_size([300.0, 800.0]),
        ..Default::default()
    };

    let rt_clone = Arc::clone(&rt);
    eframe::run_native(
        "pcauto",
        native_options,
        Box::new(move |cc| Ok(Box::new(AutoBrowserApp::new(rt_clone, cc)))),
    )
    .expect("eframe error");
}
