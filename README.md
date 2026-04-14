# Clipboard AI Assistant

Windows 桌面版剪贴板 AI 助手。程序会持续监听系统剪贴板，在检测到新的文本或图片后缓存内容；按下全局热键后，调用 OpenAI 兼容接口提问，并把回答自动写回剪贴板。

## 功能

- 监听文本和图片剪贴板
- 使用全局热键触发提问，默认 `Ctrl+Shift+A`
- 支持 OpenAI 兼容 `chat/completions` 接口
- 图片以 data URL 形式发送给视觉模型
- 支持在前台设置页直接修改 `URL`、`Hotkey`、`Temperature` 和 `关键词`
- 关键词支持本地过滤，并会追加到系统提示词中
- 回答成功后自动复制到剪贴板

## 安装

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

## 运行

```bash
python app.py
```

## 打包为 EXE

```bash
pip install -r requirements.txt
pyinstaller --noconfirm --clean --onefile --windowed --name ClipboardAIAssistant app.py
```

打包完成后，可执行文件位于 `dist/ClipboardAIAssistant.exe`。

## 使用方式

1. 启动程序。
2. 在“设置”页填写接口地址、API Key 和模型名。
3. 需要时调整全局热键、Temperature 和关键词列表。
4. 复制文本或图片到系统剪贴板。
5. 按下全局热键 `Ctrl+Shift+A`。
6. 程序会调用 AI 接口，并把答案自动写回剪贴板。

## 前台设置说明

- `Base URL`：完整接口地址，例如 `https://api.openai.com/v1/chat/completions`
- `API Key`：Bearer Token
- `Model`：模型名称
- `Global Hotkey`：`keyboard` 库支持的热键字符串
- `Temperature`：回答随机度，范围 `0.0 - 2.0`
- `System Prompt`：发送给模型的系统提示词
- `关键词`：每行一个。文本未命中任一关键词时不会发送请求；命中的关键词也会加入系统提示词
- `Timeout`：请求超时秒数

配置会保存到项目根目录下的 `config.json`。

## 依赖

- `PySide6`
- `requests`
- `Pillow`
- `keyboard`

## 已知限制

- 当前版本仅支持 Windows
- 只处理单次问答，不保存历史记录
- 图片识别能力依赖你的接口是否支持视觉输入
