# Aurora · Computer Use Studio

一个面向 **Windows 11** 的本地 AI Computer Use 桌面客户端。使用 PySide6 开发原生桌面 UI，支持你自己的第三方多模态 LLM API，自动执行鼠标和键盘操作。

> **注意：** 当前交付的是完整 Python 项目与用于 Windows 本机编译的脚本，不是预编译 `.exe`。制作 Windows 可执行文件需要在 Windows 环境运行 `build_exe.bat`；此处未在你的 Windows 11 机器上进行 GUI 端到端验证。

## 当前功能（v1.1）

- **可视化 API 配置**：Base URL/Endpoint、API Key、模型 ID、Bearer/x-api-key/无鉴权。
- **连接与识图测试**：向接口发送包含随机四位数的测试图片，检查是否真正支持视觉输入。
- **任务输入**：中文自然语言任务，示例模板，可配置最大步数与启动延迟。
- **独立后台执行线程**：PySide6 QThread，不会因为网络等待卡死 GUI。
- **Computer Use 控制**：截图、单击、双击、滚动、拖动、键盘、中文剪贴板输入。
- **视觉反馈与反循环**：发现连续点击、反复点击同一区域或点击后无明显屏幕变化时保护性停止。
- **实时运行日志与截图**：运行期间记录动作、步数、状态；任务结束后自动恢复窗口查看。
- **API 响应查看器（新增）**：正式任务与识图预检的每次 HTTP 返回在模型 JSON 解析前自动保存。GUI 中可按历史会话/步骤查看 **模型原文 / 原始 HTTP 正文 / 解析信息**，可以复制、打开本地日志目录。非 JSON 或 HTTP 报错时原始响应也会保存。
- **上下滚轮（增强）**：新增 `scroll_up` / `scroll_down` 两种明确的 Agent 动作，仍兼容 `scroll` + `direction`；滚动后重新截图观察。
- **系统托盘控制**：启动后 GUI 自动最小化，托盘右键可停止任务；另有 PyAutoGUI 左上角紧急停止。
- **密钥安全**：API Key 默认不保存；勾选后使用 `keyring` 保存到 Windows 凭据管理器。配置文件不写入 API Key。

## 一键启动（Windows 11）

**前提：** Windows 11、Python 3.10 或以上、可以联网安装 Python 包，建议先在测试 VM 中运行。

1. 解压项目 zip 到本地目录，例如 `D:\AuroraStudio`。
2. **双击 `launch_win11.bat`**。
3. 首次运行会自动创建 `.venv` 并安装依赖，以后直接弹出桌面界面。
4. UI 中填写 **API 端点**、**模型 ID**、**API Key**；点击 **测试连接 / 识图**。
5. 输入任务，例如：`打开记事本，输入「你好，我是 Aurora」，不要保存文件。`
6. 点击 **启动自动任务**，应用会自动最小化，稍后观察目标窗口并执行动作。用户无需逐步审批。

如果电脑上没有 `py` / `python` 命令，请先安装 Windows 版本 Python 并选中 `Add python.exe to PATH`。

### 查看 API 原始响应（排查模型未返回 JSON）

在主界面右侧的 **「API 响应」** 标签页，选择最新会话（也可通过左侧导航打开），即可看到按时间顺序记录的视觉预检与每一步调用。

- 选择失败的步骤，例如 `步骤 3 · HTTP 200`，默认显示模型文本；切换 **「原始 API 响应」** 可以查看模型网关返回的完整 JSON（或非 JSON 文本）；切换 **「解析信息」** 看具体错误。
- 返回 HTTP 401 / 403 / 429 / 500 也会记录原始正文；如果根本没有收到 HTTP 响应（连接超时/断线），则没有可保存的响应正文。
- 点击 **「打开目录」** 查看实际 `.jsonl` 文件（每次任务或手动识图检测都会创建单独文件，重启程序后仍可选择历史记录）。文件默认位于：

```text
%LOCALAPPDATA%\AuroraComputerStudio\api_responses\api-*.jsonl
```

- **重要隐私说明：** 原始 API 返回可能包含模型输出的个人信息/任务内容，请在分享前检查并脱敏。程序不会主动持久化截图、请求体或认证头；如果服务端在响应里回显所配置的 API Key，会尝试遮蔽该 Key 的原样文本。此遮蔽无法保证发现所有其他敏感信息。
- 为避免恶意/异常接口写满磁盘，每个单独响应的原文最多保存 200 万字符，超出会标记为 `response_truncated=true`；一般模型回答远小于这个限制。JSONL 文件不会自动清理，可在资源管理器删除旧文件。

### 手动启动

```powershell
cd D:\AuroraStudio
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe main.py
```

## 编译 Windows EXE

双击 `build_exe.bat`，脚本在 **Windows 上**通过 PyInstaller 打包：

```powershell
.\.venv\Scripts\python.exe -m pip install -U pyinstaller
.\.venv\Scripts\python.exe -m PyInstaller --noconfirm --clean --onefile --windowed --name AuroraComputer --icon assets\app.ico --collect-submodules keyring.backends main.py
```

产物路径：`dist\AuroraComputer.exe`。首次运行的单文件 EXE 需要解包，启动可能比 Python 模式慢。如果你需要更快的启动，可以把 `--onefile` 改成 `--onedir`。

## API 兼容性

该版本使用 **OpenAI-compatible multimodal Chat Completions** 标准：

```
POST /v1/chat/completions
Authorization: Bearer <your key>
Content-Type: application/json

{
  "model": "your-vision-model",
  "stream": false,
  "messages": [
    {"role":"system", "content":"..."},
    {"role":"user", "content":[
      {"type":"text", "text":"Look at the screenshot..."},
      {"type":"image_url", "image_url":{"url":"data:image/jpeg;base64,..."}}
    ]}
  ]
}
```

必须支持图片输入和文本 JSON 输出。**纯文本模型无法使用本版本的屏幕观察功能。** 若服务商使用 Anthropic Messages、Gemini 原生或 Responses 格式，需另写适配器，不能只修改 URL。

API URL 两种写法都支持：

- Base URL：`https://example.com/v1`
- 完整 Endpoint：`https://example.com/v1/chat/completions`

为防止将密钥泄漏到明文 HTTP，远程服务必须使用 HTTPS；本机 `localhost` / `127.0.0.1` 可使用 HTTP。

## 滚轮动作协议

模型现在可以返回这两种动作（坐标相对于发给模型的截图，不是屏幕物理分辨率）：

```json
{"action":"scroll_up","x":650,"y":400,"amount":3}
{"action":"scroll_down","x":650,"y":400,"amount":4}
```

它们对应 PyAutoGUI 的 `moveTo(x,y)` 后 `scroll(+amount/-amount)`。范围为 1–10 格，实际滚动距离由目标程序与 Windows 滚轮设置决定。

同时支持旧版格式：`{"action":"scroll","x":650,"y":400,"direction":"down","amount":3}`。

## 如何停止

- 鼠标移到 **主屏幕左上角 (0,0)**（PyAutoGUI FAILSAFE）。
- 托盘右键 Aurora 图标 → **停止当前任务**。
- 打开 Aurora 主窗口 → **停止任务**。
- 如果 Windows 全局热键注册成功：**Ctrl+Shift+F12**。

> 点击停止后，如果第三方 API 请求仍在进行，可能要等该请求返回或超时。程序会在收到后检查取消标志，并不会继续执行返回的动作。切勿把 GUI 停止按钮视为操作系统安全沙箱。

## 文件说明

```
AuroraStudio/
├── main.py                 # PySide6 Win11 图形界面
├── worker.py               # 自动执行线程、停止机制、状态与日志
├── engine.py               # 第三方 API + 截图 + 具体鼠标键盘动作
├── response_store.py       # API 原始响应逐次本地持久化与加载
├── assets/
│   ├── app.ico              # 桌面窗口图标
│   └── app.png
├── requirements.txt
├── launch_win11.bat         # Windows 安装依赖并启动
├── build_exe.bat            # Windows 本机生成 EXE
└── README.md
```

## 安全与限制

1. **当前不是真正隔离的沙箱。** 视觉模型可能产生不正确或危险的操作；系统提示词不能代替 OS 权限隔离。请优先在 VM 或独立 Windows 测试账户中使用。
2. **屏幕截图会上传至你填写的第三方服务。** 不要在带有密码、Token、私人文件或重要账户的桌面上测试。
3. **使用单主显示器**。不同 DPI、多显示器、UAC、安全桌面可能有截图/坐标限制；发生坐标不匹配时会拒绝执行。
4. 模型输出是否可靠取决于模型识图、坐标定位、模型响应格式和网关是否透传 base64 图片。
5. 连续点击保护与视觉差异比较是启发式规则，只能防止某些常见循环，不能判断所有任务是否真的成功。
6. 最终成功结果仍建议你检查。Agent 自动执行并不意味着完全无风险。
7. 不支持当前版本以外的其他 API 协议；没有内置用户鉴权管理或远程桌面能力。
8. API URL 与模型等常规偏好使用 Qt QSettings 保存；默认不保存任务正文、截图或普通操作日志到磁盘；**新增的 API 响应记录会保存原始返回文本**，其内容可能间接包含任务信息。勾选保存 Key 时依赖 Windows Credential Manager。

## 技术选型

- GUI：PySide6 / Qt Widgets（Windows 11 风格暗色主题）
- Worker：QThread + `threading.Event`
- API：HTTPX
- 截图及自动操作：PyAutoGUI + Pillow
- 中文输入：Pyperclip
- 密钥保存：keyring (Windows Credentials)
- 打包：PyInstaller

设计重点是 **把 Computer Use Runtime 与 GUI 分开**。更换 API 接口协议时主要修改 `engine.request_action()` 和 `engine.request_vision_preflight()`，不必重写整个桌面 UI。
