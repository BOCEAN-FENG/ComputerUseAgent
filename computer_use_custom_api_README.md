# Computer Use — 第三方 API 版 (Windows MVP)

这是一个**通过截图 + 第三方多模态大模型 + 鼠标键盘操作**控制 Windows 的最小可运行示例。

## 环境安装

```powershell
py -m pip install -U httpx pillow pyautogui pyperclip
```

## 方式 A：第三方 OpenAI 兼容 Base URL

```powershell
$env:COMPUTER_BASE_URL = "https://api.your-provider.com/v1"
$env:COMPUTER_API_KEY = "你的API密钥"
$env:COMPUTER_MODEL = "你的视觉模型ID"
python .\computer_use_custom_api.py
```

程序自动请求 `https://api.your-provider.com/v1/chat/completions`。

## 方式 B：直接指定完整请求端点

```powershell
Remove-Item Env:COMPUTER_BASE_URL -ErrorAction SilentlyContinue
$env:COMPUTER_ENDPOINT = "https://api.your-provider.com/v1/chat/completions"
$env:COMPUTER_API_KEY = "你的API密钥"
$env:COMPUTER_MODEL = "你的视觉模型ID"
python .\computer_use_custom_api.py --task "在已打开的记事本中输入你好世界"
```

命令行也支持：

```powershell
python .\computer_use_custom_api.py `
  --endpoint "https://api.your-provider.com/v1/chat/completions" `
  --model "your-vision-model" `
  --max-steps 20 --max-image-side 1600 --image-format jpeg
```

### 其他可选配置

- 默认发送 `Authorization: Bearer <API Key>`。如提供商使用 `x-api-key: <API Key>`，加 `--auth-mode x-api-key`。
- 本地无需验证的兼容接口使用 `--auth-mode none`。
- 部分提供商需要额外自定义 Headers，可设置环境变量 `COMPUTER_EXTRA_HEADERS_JSON`，例如 `'{"HTTP-Referer":"https://example.com","X-Title":"Desktop Agent"}'`。不要在这里覆盖 Authorization、x-api-key 或 Content-Type。
- 对延迟较高的模型增加 `--timeout 240`。
- 如果截图文字识别不准，尝试 `--image-format png --max-image-side 1920`；这会提高请求尺寸和费用。
- `--auto` 会跳过逐动作确认，**仅可在隔离 VM 中使用**，启用时仍需输入 AUTO 二次确认。

## API 兼容要求（重要）

第三方服务必须支持 OpenAI 风格的 **POST /v1/chat/completions**，接受如下多模态消息：

```json
{
  "model": "your-vision-model",
  "stream": false,
  "messages": [
    {"role": "system", "content": "..."},
    {"role": "user", "content": [
      {"type": "text", "text": "..."},
      {"type": "image_url", "image_url": {"url": "data:image/jpeg;base64,..."}}
    ]}
  ]
}
```

服务响应必须含 `choices[0].message.content`，内容为单个 JSON 动作：

```json
{"action":"click","x":100,"y":200,"button":"left"}
```

**并非所有第三方“OpenAI 兼容”接口都支持视觉输入或这种结构。** 纯文本模型无法识别截图。只兼容 Responses API、Anthropic Messages 等其他协议的服务，需要另写请求适配器。

## 安全与局限

- 截图会发送给你配置的 API 供应商，可能包含账号、隐私或机密数据。
- 默认每次实际操作都要用户按 `y` 批准；将鼠标移至屏幕**左上角**可以触发 PyAutoGUI failsafe 中止。
- 仅支持**主屏幕**，若截图尺寸与系统鼠标坐标系不一致则拒绝执行，避免错误点击。
- 当前没有浏览器 DOM / Windows UI Automation，没有隔离 VM，也没有防恶意页面的可靠边界。**不要用于真实支付、账号管理或敏感数据处理**。
- 文字输入会覆盖系统剪贴板。程序不运行模型生成的任意 Python / shell 代码。

建议先打开记事本，将任务设为 `在记事本里输入“你好，世界”，不要保存。`，用逐步确认验证。
