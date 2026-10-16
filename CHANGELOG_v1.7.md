# Aurora Computer Use Studio v1.7 — 完整键鼠动作与截图矩形选择

## 这次日志中真正发生了什么
用户提供的 `api-20261016-224813-task-215f78.jsonl` 共 51 行（视觉预检 1 + 动作 50）。所有动作 `parse_status=ok`；模型在第 37 步抵达第三个视频并暂停，随后第 38-50 步反复 PrintScreen / Win+Shift+S / 点击截图工具栏；从未发出拖动选区，也未执行后续画图/记事本保存。达到最大执行步数不是模型返回 `done`。

## 修复

1. 原有 drag 升级为明确、可控的原子长按拖动：`moveTo -> mouseDown -> sleep(hold_seconds) -> moveTo(duration) -> mouseUp`，即使拖动中报错也尝试释放鼠标。默认 duration 0.95s / hold_seconds 0.18s。支持 left/right/middle。
2. 新增：`mouse_hold`、`mouse_down`、`mouse_up`、`key_hold`、`key_down`、`key_up`、`scroll_left`、`scroll_right`，以及单击 `clicks=1..3`、移动 `duration`。原有 click/double_click/move/scroll_up/scroll_down/type/keypress/wait/ask_user/done 继续可用。
3. `mouse_down` / `key_down` 跨模型步骤的按住状态会在 8 秒后自动释放；模型输出 `mouse_up` 或 `key_up` 仍可提前释放；任务停止或异常时也会释放。截图选区强烈推荐单个 `drag`，避免慢速网络中途松手。
4. 中文提示词增加 Windows 截图覆盖层操作流程：Win+Shift+S -> 识别矩形模式 -> **drag 从左上角到右下角** -> 打开画图 Ctrl+V -> GUI 另存为 PNG。若模型重复按截图快捷键，下一轮上下文自动增加拖动纠错提示，不会强制结束。
5. GUI 默认最大步数调整为 100（旧用户保存过的偏好不自动覆盖，需在界面手动调整）。原有限额仍是硬上限，以控制 API 成本与风险。
6. 完全保留 GUI-Only，不增加特殊截图/文件写入/浏览器/脚本工具，观察截图仅供模型分析。

## 示例：Windows 截图区域拖动

```json
{"action":"keypress","keys":["win","shift","s"]}
```

下一轮看到矩形覆盖层之后：

```json
{"action":"drag","x":250,"y":150,"to_x":1350,"to_y":800,"button":"left","hold_seconds":0.2,"duration":1.2}
```

这里的坐标是**本轮发送给模型的缩放后截图尺寸**，不是原始桌面像素。端点通过 `COMPUTER_BASE_URL` / GUI 的 API 设置配置，不受影响。

## 说明
- Win11 在“使用 Print Screen 键打开屏幕截图”设置打开时，PrintScreen 本身也可能唤起截图工具；因此不能假设按 PrintScreen 已经复制截图，必须观察截图工具状态。
- GUI 端进行的单轮矩形拖动仍可能因弹窗、焦点、遮罩模式或者模型选点不准而失败。本版解决动作表达/执行及循环引导，无法保证第三方模型每次都能正确完成截图任务。
- 实测范围是 Python 语法检查及纯模拟的键鼠/执行线程离线测试。当前环境不是 Win11，没有完成真实桌面端端到端验证。
