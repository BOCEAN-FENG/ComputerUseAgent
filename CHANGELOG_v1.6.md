# Aurora Computer Use Studio v1.6 — 严格 GUI-Only

修正 v1.5 引入的非 GUI 操作动作。此次版本将 Computer Use 的全部操作限制为鼠标、键盘与等待；`done`、`ask_user` 属于会话控制，不会直接操作系统。

- **移除** `capture_frame`、`write_report` 和 `observe_video` 三种 Agent 动作；解析器无条件拒绝这三个动作（即使来自兼容的 DSML 文本）。删除 `artifacts.py`，Worker 不直接生成 PNG/TXT，也不使用文件系统写入来代替用户的图形界面操作。
- 保存视频帧必须通过 **Windows 截图快捷键 → 画图 → 另存为 → 桌面**；生成总结必须通过 **启动记事本 → 输入文字 → 另存为 → 桌面**。鼠标坐标、窗口和保存对话框均由模型逐步观看截图后操作，没有直接的读写文件工具。
- **被动视频进度标注**：模型的键鼠动作 JSON 可选择性携带 `screen_video_id`（当前屏幕上可见的稳定视频标识），程序不执行它，仅被动计数。对新视频必须在下刷后连续两轮观察到相同、与上一条不同的稳定标识。不会把播放章节或画面切换直接算作新视频。
- **被动 GUI 文件可见性**：只有在模型看到资源管理器**桌面目录**中可见的真实文件名时，才允许在键鼠动作 JSON 中携带 `gui_file`（截图观察内容）。`done` 前要求 PNG 和 TXT 两种观察报告；这不是文件系统级验证，可能出现模型误识别，须人工复核重要内容。
- 目标视频锁定后，在播放器界面拒绝再次下刷，但允许切换到画图、记事本、资源管理器操作保存对话框。
- 保留原有 DeepSeek DSML 兼容、API 响应记录、GUI 用户回复、异常运行诊断、连续点击防卡死与取消功能。

## 示例：模型可返回的动作（仍是纯键鼠）

```json
{"action":"keypress","keys":["down"],"screen_video_id":"@示例作者｜第一条旅游视频"}
```

```json
{"action":"keypress","keys":["win","r"]}
```

```json
{"action":"type","text":"notepad"}
```

```json
{"action":"wait","seconds":0.5,"gui_file":{"kind":"txt","name":"第三条视频.txt"}}
```

`screen_video_id` 与 `gui_file` 都不是动作，不改变屏幕，不会创建文件。`gui_file` 必须由当前屏幕 GUI 中可见的文件名支持。

## 已知限制

- 模型识别视频是否真的是下一条并不能由截图像素百分百证明；在隐藏标题或画面无法区别时，可能需要 `ask_user`。
- Windows 11 的截图快捷键和另存为界面会因系统版本、焦点、语言和应用变化；模型应每步重新观察，而不是把流程看作固定脚本。
- 本环境已完成 Python 语法检查与模拟离线测试，**未在真实 Windows 11 / deepseek-flash API 上验证整个图形界面保存流程**。
