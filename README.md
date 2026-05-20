# Clipboard AI Assistant

Windows 桌面版剪贴板 AI 助手。程序会持续监听系统剪贴板，在检测到新的文本或图片后自动调用 OpenAI 兼容接口提问，并把回答自动写回剪贴板。

## 功能

- 监听文本和图片剪贴板
- 复制到剪贴板后自动发送请求，不需要额外按键或点击
- 默认后台静默启动，不主动显示主窗口
- 使用独立的显示窗口热键恢复主窗口，默认 `Ctrl+Shift+S`
- 点击窗口右上角关闭按钮时只隐藏到后台，不退出程序
- 支持自定义 OpenAI 兼容接口
- 支持在页面内一键切换到 DeepSeek / Gemini / Kimi / 豆包 预设
- 支持在页面中修改显示窗口快捷键
- 支持在页面内测试 API 连接
- 设置项会自动记忆，退出程序后无需重新填写
- 回答成功后自动复制到剪贴板
- 单实例运行，再次启动时会唤起已运行的窗口

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

1. 启动程序后，应用会默认在后台静默运行。
2. 通过 `Ctrl+Shift+S` 打开主窗口。
3. 在“设置”页选择服务商：
   - `自定义 / OpenAI 兼容`
   - `DeepSeek`
   - `Gemini`
   - `Kimi`
   - `豆包`
4. 如需使用 DeepSeek、Gemini、Kimi 或豆包，点击“应用服务商预设”，会自动填入官方兼容地址和推荐模型。
5. 填写 `API Key`，必要时修改 `Model`、`Temperature`、`关键词` 和 `显示窗口热键`。
6. 点击“测试 API 连接”验证当前配置。
7. 复制文本或图片到系统剪贴板，程序会自动调用 AI 接口，并把答案自动写回剪贴板。

## 前台设置说明

- `服务商`：选择自定义兼容接口、DeepSeek、Gemini、Kimi 或 豆包
- `Base URL`：完整接口地址
- `API Key`：Bearer Token
- `Model`：模型名称
- `显示窗口热键`：从后台恢复主窗口
- `Temperature`：回答随机度，范围 `0.0 - 2.0`
- `System Prompt`：发送给模型的系统提示词
- `关键词`：每行一个。文本未命中任一关键词时不会发送请求；命中的关键词也会加入系统提示词
- `Timeout`：请求超时秒数

配置会保存到项目根目录下的 `config.json`。

## 已知限制

- 当前版本仅支持 Windows
- 只处理单次问答，不保存历史记录
- 图片识别能力依赖你的接口是否支持视觉输入
- 真正退出程序需要先显示主窗口，再点击“退出程序”
