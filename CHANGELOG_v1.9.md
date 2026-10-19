# Aurora v1.9 · Screenshot Clipboard Preservation

## 本次日志的原因（2026-10-16 23:49:08 会话）

第 30-31 步 Win+Shift+S + drag 完成截图选区后，第 33 步 `type("mspaint")` 通过旧版 `pyperclip.copy` 把剪贴板图片替换成文本，导致第 35 步 Ctrl+V 无法粘贴图片；第 38-43 步重复了同一个失败循环。日志中执行器未报告截图或粘贴异常，因为模拟键盘事件本身执行成功。

## 修复

- 新增 `text_input.py`：所有 `type` 动作在 Windows 都不触碰剪贴板。可打印 ASCII 通过 `pyautogui.write`；Unicode 通过 Windows `SendInput` 键盘事件；换行和制表符通过键盘按下处理。
- Unicode 键盘事件失败时直接返回错误，不退化成覆盖剪贴板的 `pyperclip.copy`。
- 新增 `clipboard_flow.py`：根据模型使用过的截图快捷键、拖动、粘贴动作提供持续提示，提醒验证画图是否获得焦点、优先重试 Ctrl+V；不会自行截图或更改文件。
- 强化中文系统提示词，明确 Win+Shift+S、拖动、启动 mspaint、等待画图加载、单击画布、Ctrl+V 的完整过程。
- 新增 `tests/test_clipboard_paint_regression.py` 回归测试，涵盖图片剪贴板保持、Unicode、粘贴焦点提示和重复截图恢复。

## 使用

下载解压后双击 `launch_win11.bat`；如使用旧 EXE 则重新运行 `build_exe.bat`。建议先验证：打开记事本写中文 → 截图区域 → Win+R 启动画图 → Ctrl+V 粘贴 → GUI 另存为。

## 限制

- 未在真实 Windows 11 及 DeepSeek 第三方 API 上进行端到端实测。真实剪贴板内容、画图窗口焦点仍需通过截图观察确认。
- `type` 模拟键盘输入而不是瞬间粘贴，输入几百字的速度比旧版慢一些；中文键盘事件在少量不支持 VK_PACKET 的程序中可能不生效。
- 目标窗口若以更高权限运行，Windows 的输入完整性隔离可能阻止模拟输入。
