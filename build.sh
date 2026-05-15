#!/bin/bash
# pcauto macOS/Linux Rust 打包腳本
# 輸出：target/release/pcauto

set -e
cd "$(dirname "$0")"

echo "================================"
echo "  pcauto Rust 打包"
echo "================================"

# 確保 config.json 存在（首次使用）
if [ ! -f "config.json" ]; then
    echo "建立預設 config.json..."
    cp config.json.example config.json
fi

echo "[1/2] cargo build --release ..."
cargo build --release

echo "[2/2] 完成！"
echo ""
echo "================================"
echo "  打包完成！"
echo "  執行檔：target/release/pcauto"
echo "  設定：config.json （首次使用請填寫後端 URL 和 API Key）"
echo "================================"

# macOS: 嘗試打開 target/release 目錄
open target/release 2>/dev/null || true
