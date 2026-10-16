> 历史文档：v1.5 的 capture_frame / write_report / observe_video 动作已于 v1.6 删除。请以 CHANGELOG_v1.6.md 为准。

# v1.5 — 2026-10-16

- 新增 `video_progress.py`：针对“刷到第 N 条视频”的程序侧视频计数，先切换后双重视觉确认，禁止章节计数与过早 done。
- 新增 `artifacts.py`：截图原尺寸 PNG + Unicode TXT 文件直接保存到桌面，文件名自动去重，不能由模型指定任意写入路径。
- 新增 `run_trace.py`：逐步记录截图、HTTP 请求、解析、执行及终止阶段；与原有 API 响应 JSONL 并存。
- `engine.py` 系统提示词补充稳定视频身份、独立视频识别、截图/TXT 协议与视频任务执行顺序。
- `worker.py` 增加视频状态、阶段护栏、动作执行追踪、一次请求最多两次有限重试、运行异常精确步骤反馈。
- `main.py`：GUI 视频状态回显，最大步数上限扩展到 200，新用户默认 60。
- 新增视频状态与完整离线运行测试；所有已有回归测试继续运行。
