# Aurora Computer Use Studio · v1.1

## 新增 · API 响应记录

- 每次来自 API 的 HTTP 响应在尝试解析模型动作之前写入本地 JSONL，包含识图预检、每步行动、HTTP 错误及无法解析的文本。
- GUI 新增 **API 响应** 标签：历史会话下拉列表、逐步记录、查看模型文本/完整 HTTP 响应/解析错误、复制当前查看内容、打开存储目录。
- 在执行报错后自动切换到「API 响应」标签，便于直接定位返回非 JSON 的那一步。
- 保存位置：`%LOCALAPPDATA%\AuroraComputerStudio\api_responses\api-*.jsonl`。本地日志重启后保留。
- 只保存收到的响应，不保存出站请求图片和认证头。对配置的 API Key 原文进行替换遮蔽；其他敏感内容请自行检查。每条返回上限 200 万字符。

## 新增 · 鼠标上下滚动

支持：

```json
{"action":"scroll_up","x":450,"y":330,"amount":3}
{"action":"scroll_down","x":450,"y":330,"amount":3}
```

仍然兼容旧协议：

```json
{"action":"scroll","x":450,"y":330,"direction":"down","amount":3}
```

`amount` 为 1–10 格；本地 PyAutoGUI 执行，并在下一步再次截图。

## 已知限制

- 第三方模型如果真正没有返回合法动作 JSON，依然会停止任务；但现在能在 GUI 中查看究竟返回了什么，不会再丢失调试线索。
- 模型能否自主正确滚动取决于截图识别和模型能力；滚轮实际像素距离依赖于被操作软件和 Windows 系统设置。
- Windows GUI/EXE 尚未在本构建环境完成端到端验证，已通过 Python 语法检查及 10 项离线单元测试。
