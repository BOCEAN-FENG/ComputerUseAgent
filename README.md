# v1.7.1 安装修复（推荐使用）

**解决 Win11 首次安装 PySide6 报 Windows 长路径限制问题。** 现在仅安装 `PySide6-Essentials`，虚拟环境放到 `%LOCALAPPDATA%\AuroraStudio\venv`，并在每次启动时检查依赖是否完整。直接双击 `launch_win11.bat`。如果你曾在项目内安装失败，可以删除旧 `.venv` 文件夹。详见 `CHANGELOG_v1.7.1.md`。

---

# v1.7 更新说明

**已修复截图选区动作表达不足的问题。** 现在 Agent 可以单动作长按并拖动鼠标选择矩形区域，也可执行更多键盘与鼠标动作。详情见 `CHANGELOG_v1.7.md` 和 `SYSTEM_PROMPT_zh.txt`。

**运行方式：** Windows 11 解压后双击 `launch_win11.bat`；如需新的 EXE，双击 `build_exe.bat` 并重新构建。**更新旧项目时，必须替换 engine.py + worker.py + main.py**，仅修改提示词不会启用新动作。若旧设置保存了“最多步骤 50”，请在 GUI 手动调到 100 或适合的值（调用量会增加）。

# Aurora · Computer Use Studio

一个面向 **Windows 11** 的本地 AI Computer Use 桌面客户端。使用 PySide6 开发原生桌面 UI，支持你自己的第三方多模态 LLM API，自动执行鼠标和键盘操作。

> **注意：** 当前交付的是完整 Python 项目与用于 Windows 本机编译的脚本，不是预编译 `.exe`。制作 Windows 可执行文件需要在 Windows 环境运行 `build_exe.bat`；此处未在你的 Windows 11 机器上进行 GUI 端到端验证。

## 最新版本：v1.6 GUI-Only（请以此为准）

**Agent 不能调用专用截图保存或 TXT 文件写入工具。** 执行器仅接受鼠标、键盘、文本输入、等待；`done`/`ask_user` 是会话信号，不直接执行系统操作。任务用 PNG、TXT 文件时，Agent 必须通过 Windows 可见的截图工具、画图、记事本、资源管理器及其“另存为”对话框完成，绝不绕过图形界面。`artifacts.py` 已删除，`capture_frame` / `write_report` / `observe_video` 均为非法动作。

视频任务保持被动序号跟踪：模型可在普通键鼠动作中额外描述当前截图的 `screen_video_id`；在资源管理器桌面目录看见保存文件时可描述 `gui_file`。这些是**截图事实标注，非可执行工具**；不是实际文件系统存在性的证明。程序仍会阻止视频未到目标或没有 GUI 文件观察信息时过早 `done`。详见 `CHANGELOG_v1.6.md`。

**v1.5 的 `README_v1.5.md` 与 `CHANGELOG_v1.5.md` 仅为历史说明，其中专用工具动作现已废弃，不应依照它们开发或调用。**

## 基本功能（沿用 v1.4 功能）

- **可视化 API 配置**：Base URL/Endpoint、API Key、模型 ID、Bearer/x-api-key/无鉴权。
- **严格 JSON 输出协议（v1.4）**：中文系统提示词明确规定只能输出一个 JSON 对象、动作白名单、必要字段、数字/字符串类型、当前截图坐标范围，禁止 DSML/XML/Markdown/function_call/tool_calls，保留连续点击和 ask_user 交互。
- **DSML 有限兼容（v1.4）**：遇到模型偶然返回的**一个、完整、受支持**的 DeepSeek DSML 动作时，执行器可转换为内部 JSON；会保留原始响应并标注 `parse_mode=dsml_compat`。不能解析多个工具调用、不认识的动作、非法参数以及额外内容。此功能是兜底，不是给模型开放任意工具调用。
- **中文模型提示词**：系统规则、每步截图任务描述、动作反馈以及视觉预检文本均使用中文；JSON 协议字段名与 action 名称保持英文。
- **连接与识图测试**：向接口发送包含随机四位数的测试图片，检查是否真正支持视觉输入。
- **任务输入**：中文自然语言任务，示例模板，可配置最大步数与启动延迟。
- **独立后台执行线程**：PySide6 QThread，不会因为网络等待卡死 GUI。
- **Computer Use 控制**：截图、单击、双击、滚动、拖动、键盘、中文剪贴板输入。
- **允许正常连续点击（v1.3）**：不再以“连续点击三次”或“截图连续三次无变化”为由直接停止任务；允许点击不同位置持续操作。只有同一小区域连续至少 8 次点击、而且对应截图始终无明显变化时，才拦截下一次同处点击。该启发式机制可能误判，请结合日志检查。
- **实时运行日志与截图**：运行期间记录动作、步数、状态；任务结束后自动恢复窗口查看。
- **API 响应查看器（新增）**：正式任务与识图预检的每次 HTTP 返回在模型 JSON 解析前自动保存。GUI 中可按历史会话/步骤查看 **模型原文 / 原始 HTTP 正文 / 解析信息**，可以复制、打开本地日志目录。非 JSON 或 HTTP 报错时原始响应也会保存。
- **上下滚轮（增强）**：新增 `scroll_up` / `scroll_down` 两种明确的 Agent 动作，仍兼容 `scroll` + `direction`；滚动后重新截图观察。
- **交互式人工确认（v1.2 新增）**：模型返回 `{"action":"ask_user","message":"..."}` 时不再结束任务。自动暂停执行、恢复 Aurora 窗口并切至「用户回复」标签；用户在文本框中回复后，原执行线程保留任务和动作历史、把回复带进后续模型请求、自动最小化后继续工作。等待期间可随时停止。
- **系统托盘控制**：启动后 GUI 自动最小化，托盘右键可停止任务；另有 PyAutoGUI 左上角紧急停止。
- **密钥安全**：API Key 默认不保存；勾选后使用 `keyring` 保存到 Windows 凭据管理器。配置文件不写入 API Key。

## v1.4：解决 DeepSeek 模型输出 DSML 而非 JSON

如果模型原文类似：

```text
<｜｜DSML｜｜ calls>
<｜｜DSML｜｜ invoke name="click">
<｜｜DSML｜｜ parameter name="x" string="false">1245</｜｜DSML｜｜ parameter>
<｜｜DSML｜｜ parameter name="y" string="false">888</｜｜DSML｜｜ parameter>
</｜｜DSML｜｜ invoke>
</｜｜DSML｜｜ calls>
```

新版提示词要求模型改为**纯文本 JSON**（不要 DSML、Markdown 或解释）：

```json
{"action":"click","x":1245,"y":888}
```

如果模型偶尔仍返回上述单个 DSML 调用，兼容解析器会进行有限的结构化转换。GUI 的「API 响应」列表和解析信息将显示兼容提示。原文依旧被保存，不会偷偷更改日志。

**修改提示词的位置：** `engine.py` 文件顶部的 `SYSTEM_PROMPT`；旁边的 `SYSTEM_PROMPT_zh.txt` 是当前协议的只读参考副本。运行时以 `engine.py` 内的内容为准。第三方网关若自行强制启用工具调用模式，提示词无法从根本上改变其响应格式，应该同时在供应商端关闭强制工具模式或启用其兼容的 JSON 输出设置。

## 一键启动（Windows 11）

**前提：** Windows 11、Python 3.10 或以上、可以联网安装 Python 包，建议先在测试 VM 中运行。

1. 解压项目 zip 到本地目录，例如 `D:\AuroraStudio`。
2. **双击 `launch_win11.bat`**。
3. 首次运行会自动在 `%LOCALAPPDATA%\AuroraStudio\venv` 创建虚拟环境并安装依赖，以后直接弹出桌面界面。
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

### 模型请求确认：如何回复并继续（v1.2）

当第三方模型返回：

```json
{
  "action": "ask_user",
  "message": "正在播放的是详情页。请确认总结当前视频，还是返回列表寻找第三个视频？"
}
```

Aurora 会 **暂停 Agent 线程，不继续点击**，同时恢复被最小化的主窗口，切换到右侧 **「✉ 用户回复」** 标签。在这里：

1. 查看「Agent 的问题」中的完整问题。
2. 在「你的回复」文本框里填写，如：`返回视频列表，从上到下找到第三个视频，打开后总结内容到新建记事本。`
3. 点击 **「发送回复并继续任务」**。窗口会再次最小化，Agent 大约 2 秒后重新截图；原来的任务指令、动作历史和回复都保留，**无需重新启动任务**。
4. 若不想继续，点击「停止任务」，或者使用托盘/全局停止快捷键。等待用户回复时不会移动鼠标、发送新的模型调用。

也可以从左侧 **「用户回复 / 继续」** 入口、或托盘中的 **「查看待回复的问题」** 返回本面板。如果模型连续三次询问完全相同的问题，会保护性停止，避免循环。单次人工回复最多 4000 字符；回复正文不会写入执行日志，但会发送给你配置的第三方模型服务。

**补充：** `ask_user` 只暂停并要求澄清，它不等同于授权模型绕过系统安全规则；涉及支付、删除、发送消息等有风险操作仍应由使用者自己决定并采取必要的隔离措施。

### 手动启动

```powershell
cd D:\AuroraStudio
py -3 -m venv .venv
"%LOCALAPPDATA%\AuroraStudio\venv\Scripts\python.exe" -m pip install -r requirements.txt
.\.venv\Scripts\python.exe main.py
```

## 编译 Windows EXE

双击 `build_exe.bat`，脚本在 **Windows 上**通过 PyInstaller 打包：

```powershell
"%LOCALAPPDATA%\AuroraStudio\venv\Scripts\python.exe" -m pip install -U pyinstaller
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
├── engine.py               # 第三方 API + 截图 + JSON/DSML解析 + 鼠标键盘动作
├── response_store.py       # API 原始响应逐次本地持久化与加载
├── SYSTEM_PROMPT_zh.txt    # v1.4 中文提示词参考副本（运行时以 engine.py 为准）
├── tests/test_ask_user_resume.py  # 用户回复、恢复、取消、循环测试
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
5. 截图差异只是启发式信号：现在允许正常连续点击，但同一小区域连续至少 8 次无可见变化点击后会保护性停止。该规则不能保证正确判断所有任务是否成功。
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


## v1.8：总体任务目标与当前进度

任务启动时锁定总体目标（原始用户文字），执行过程中不允许模型修改；每一步发送到 API 时都包含锁定目标和跨轮保存的当前进度。
GUI 的任务卡片中显示只读「🔒 总体目标」和「已完成 / 正在进行 / 下一步」。模型可通过动作中的可选 `task_state` 注释提交截图观察结果，不能使用它触发操作或修改原始任务。

例子（这里还是**一次只有一个鼠标动作**）：

```json
{"action":"click","x":600,"y":500,"task_state":{"completed_now":"抖音网页版已打开","evidence":"当前浏览器界面可见抖音标识","current":"进入全屏播放","next":"识别并登记第一条视频"}}
```

屏幕观察和键鼠操作仍是唯一执行手段；状态标注来自视觉模型，可能有误，文件完成必须遵循原有可见 GUI 检查。详细修改参见 `CHANGELOG_v1.8.md`。
