# 自动化浏览器工具 v2.0

基于 CloakBrowser 的 Windows 桌面自动化程序。

**核心理念：一个网站 = 一个任务文件**

---

## 浏览器选择

程序支持两种浏览器模式：

| 浏览器 | 说明 | 适用场景 |
|--------|------|----------|
| 🕵️ **CloakBrowser** | 隐身浏览器，防检测强 | 需要绕过反爬/验证码的网站 |
| 🌐 **系统 Chrome** | 使用你电脑安装的 Chrome | 普通网站测试，开发调试 |

在「⚙️ 浏览器配置」中选择使用的浏览器。

---

## 功能特性

- 🌐 **网站任务管理** - 每个网站独立任务文件，灵活管理多个目标
- 🤖 **智能防检测** - CloakBrowser 隐身浏览器，reCAPTCHA v3 得分 0.9
- 🔐 **验证码处理** - 自动检测常见验证码，暂停等待用户填写
- ⌨️ **人类行为模拟** - 鼠标曲线、键盘延迟、滚动模式
- 📊 **详细步骤编辑** - 可视化编辑每个点击/输入操作

---

## 安装

```bash
pip install -r requirements.txt
```

## 运行

```bash
python main.py
```

## 打包 EXE

```bash
build.bat
```

---

## 使用教程

### 1. 创建网站任务

点击 **➕ 新建**，填写：

| 字段 | 说明 |
|------|------|
| 任务名称 | 例如：示例网站登录 |
| 网站域名 | 例如：https://example.com |

### 2. 添加操作步骤

支持的步骤类型：

| 类型 | 说明 | 参数 |
|------|------|------|
| 🌐 打开网址 | 导航到目标页面 | URL |
| 🖱️ 点击元素 | 点击按钮/链接 | CSS选择器 |
| 📝 填写文本 | 快速填充输入框 | 选择器 + 文本 |
| ⌨️ 逐字输入 | 模拟人工输入 | 选择器 + 文本 |
| 👆 悬停 | 鼠标悬停 | CSS选择器 |
| 📜 滚动 | 页面滚动 | 像素值 |
| 📸 截图 | 保存页面截图 | 文件名 |
| ⏱️ 等待 | 等待时间 | 秒数 |
| ⚡ 执行JS | 运行JavaScript | 代码 |

### 3. 保存任务

任务自动保存到 `tasks/` 目录，每个网站一个 JSON 文件：

```
tasks/
├── example.com.json
├── google.com.json
└── my-site.com.json
```

### 4. 执行任务

1. 在左侧列表选择任务
2. 点击 **▶ 运行任务**
3. 浏览器自动执行步骤
4. 如遇验证码 → 程序暂停 → 手动填写 → 点击 **✅ 验证码已解决**
5. 继续执行

---

## 任务文件格式

```json
{
  "name": "示例网站登录",
  "domain": "https://example.com",
  "description": "自动登录并提交表单",
  "enabled": true,
  "steps": [
    {"type": "goto", "url": "https://example.com/login", "wait": "2"},
    {"type": "fill", "selector": "#username", "value": "admin", "wait": "0.5"},
    {"type": "fill", "selector": "#password", "value": "pass123", "wait": "0.5"},
    {"type": "click", "selector": "#login-btn", "wait": "2"},
    {"type": "scroll_down", "amount": "500", "wait": "1"},
    {"type": "click", "selector": "#submit-btn", "wait": "3"}
  ]
}
```

---

## 常见问题

### Q: 启动报 "Broken pipe"？
A: 关闭代理和 geoip 功能，或检查网络连接。

### Q: 验证码检测不到？
A: 可根据目标网站自定义选择器列表。

---

## 技术栈

- Python 3.10+
- PyQt5
- CloakBrowser
- PyInstaller
