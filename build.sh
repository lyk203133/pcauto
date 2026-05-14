#!/bin/bash
# pcauto macOS 打包腳本
# 輸出：dist/pcauto.app

set -e
cd "$(dirname "$0")"

echo "================================"
echo "  pcauto macOS 打包"
echo "================================"

# 1. 檢查 Python 環境
echo "[1/4] 檢查環境..."
python3 --version
pip3 show pyinstaller > /dev/null 2>&1 || {
    echo "  安裝 PyInstaller..."
    pip3 install pyinstaller -q
}

# 2. 安裝/更新依賴
echo "[2/4] 安裝依賴..."
pip3 install -r requirements.txt -q

# 3. 確保 config.json 有預設值（不打包進去，留在 dist 旁邊）
if [ ! -f "config.json" ]; then
    echo "  建立預設 config.json..."
    cat > config.json << 'EOF'
{
  "server_url": "http://localhost:8088",
  "api_key": "",
  "hmac_secret": "",
  "poll_interval": 5
}
EOF
fi

# 4. 打包
echo "[3/4] 打包中（可能需要 1-3 分鐘）..."
pyinstaller pcauto.spec --clean --noconfirm

# 5. 把 config.json 複製到 .app 旁（用戶首次運行需要設定）
echo "[4/4] 複製 config.json..."
cp config.json dist/config.json 2>/dev/null || true

echo ""
echo "================================"
echo "  打包完成！"
echo "  應用：dist/pcauto.app"
echo "  設定：dist/config.json （首次使用請填寫）"
echo "================================"

# 嘗試打開 dist 目錄
open dist 2>/dev/null || true
