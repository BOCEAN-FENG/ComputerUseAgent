# -*- coding: utf-8 -*-
"""Runs the actual Computer Use loop outside the Qt GUI thread.

The worker deliberately uses an Event rather than QThread.terminate(): callers can
request cancellation while an HTTP request is underway, and the request result will
never be executed after cancellation. A blocking HTTP call may finish or time out first.
"""
from __future__ import annotations

import base64
import json
import threading
from pathlib import Path
from dataclasses import dataclass

import httpx
from PySide6.QtCore import QThread, Signal

import engine
from response_store import ResponseStore
from clipboard_flow import ClipboardFlow
from run_trace import RunTrace
from video_progress import VideoProgress, requested_video_number, is_next_video_action
from task_context import TaskLedger


@dataclass(frozen=True)
class RunConfig:
    endpoint: str
    api_key: str
    auth_mode: str
    model: str
    task: str
    max_steps: int = 100
    start_delay: int = 3
    max_image_side: int = 1600
    vision_check: bool = True
    settle_time: float = 1.0
    request_timeout: int = 60


class VisionTestThread(QThread):
    result = Signal(bool, str)
    response_record = Signal(object)

    def __init__(self, config: RunConfig):
        super().__init__()
        self.config = config

    def run(self):
        c = self.config
        try:
            url = engine.resolve_endpoint(None, c.endpoint)
            store = ResponseStore(label='connection')
            with httpx.Client(timeout=httpx.Timeout(45, connect=12), follow_redirects=False) as http:
                engine.request_vision_preflight(http, endpoint=url, api_key=c.api_key,
                                                auth_mode=c.auth_mode, model=c.model,
                                                on_response=lambda e: record_response(
                                                    store, e, c.api_key, self.response_record.emit))
            self.result.emit(True, '连接成功，模型可以读取图片内容')
        except Exception as error:
            self.result.emit(False, safe_error(error))


def safe_error(error: Exception) -> str:
    """Do not surface provider response bodies, headers or API keys in the UI."""
    if isinstance(error, httpx.HTTPStatusError):
        return f'API 返回 HTTP {error.response.status_code}，请检查端点、密钥和模型名称'
    if isinstance(error, httpx.RequestError):
        return f'无法连接到 API：{type(error).__name__}（检查网络、地址和代理）'
    value = str(error).replace('\n', ' ')[:260]
    return value or type(error).__name__


class ClickStagnationGuard:
    """仅拦截长时间点同一个小区域且画面不变的明显卡死循环。

    在不同位置正常连续点击（包括超过十次）不触发任何限制。
    图像相似度只是启发式指标：聚焦输入框等合法操作可以没有明显变化。
    """

    def __init__(self, *, max_stagnant_same_spot: int = 8, radius_px: int = 20):
        self.max_stagnant_same_spot = max_stagnant_same_spot
        self.radius_px = radius_px
        self.reset()

    def reset(self):
        self._last_position: tuple[int, int] | None = None
        self._stagnant_repeats = 0

    def _near(self, a: tuple[int, int], b: tuple[int, int]) -> bool:
        return abs(a[0] - b[0]) <= self.radius_px and abs(a[1] - b[1]) <= self.radius_px

    def observe(self, kind: str | None, position: tuple[int, int] | None,
                visual_change: float | None) -> int:
        """在点击后的下一张截图上更新观察结果。返回当前停滞重复次数。"""
        if kind not in ('click', 'double_click') or position is None or visual_change is None:
            self.reset()
            return 0
        if visual_change >= 0.002:
            self.reset()
            return 0
        if self._last_position is not None and self._near(self._last_position, position):
            self._stagnant_repeats += 1
        else:
            self._stagnant_repeats = 1
        self._last_position = position
        return self._stagnant_repeats

    def should_block(self, kind: str, position: tuple[int, int]) -> bool:
        return (kind in ('click', 'double_click')
                and self._last_position is not None
                and self._stagnant_repeats >= self.max_stagnant_same_spot
                and self._near(self._last_position, position))


class AgentThread(QThread):
    log_line = Signal(str, str)  # level, text
    activity = Signal(int, str)  # current step, sanitized short text
    shot = Signal(bytes, int, int)  # image bytes, picture width, picture height
    state = Signal(str)
    done = Signal(str, str)  # status: success/stop/blocked/error/limit, summary
    response_record = Signal(object)
    progress = Signal(str)  # specific video progress
    task_snapshot = Signal(object)  # frozen objective + persistent task state
    user_question = Signal(int, str)  # step, question; GUI supplies reply asynchronously

    def __init__(self, config: RunConfig):
        super().__init__()
        self.config = config
        self.stop_event = threading.Event()
        self._reply_lock = threading.Lock()
        self._reply_event = threading.Event()
        self._waiting_step: int | None = None
        self._reply_text: str | None = None
        self._trace_log: RunTrace | None = None
        self._current_step = 0
        self._last_action = 'none'
        self._input_state: engine.InputState | None = None

    def request_stop(self):
        self.stop_event.set()
        # 任务停止时不要留住鼠标或 Shift/Ctrl 等按键。
        if self._input_state is not None:
            self._input_state.release_all()
        # Unblock an outstanding ask_user wait without accepting any late reply.
        self._reply_event.set()

    def submit_reply(self, step: int, text: str) -> bool:
        """GUI-thread safe handoff; reject stale, empty, or unsolicited messages."""
        answer = text.strip()
        if not answer or len(answer) > 4000 or self.stop_event.is_set():
            return False
        with self._reply_lock:
            if self._waiting_step != step or self._reply_text is not None:
                return False
            self._reply_text = answer
            self._reply_event.set()
            return True

    def _await_user_reply(self, step: int, question: str) -> str:
        """Pause the worker, not the Qt UI; task and action history remain live."""
        with self._reply_lock:
            self._waiting_step = step
            self._reply_text = None
            self._reply_event.clear()
        self.state.emit('等待你的回复')
        self.user_question.emit(step, question)
        while not self._reply_event.wait(0.15):
            self._check_stop()
        self._check_stop()
        with self._reply_lock:
            reply = self._reply_text
            self._waiting_step = None
            self._reply_text = None
            self._reply_event.clear()
        if not reply:
            raise Stopped()
        self.state.emit('继续执行任务')
        return reply

    def _sleep(self, duration: float):
        return self.stop_event.wait(max(0, duration))

    def _check_stop(self):
        if self.stop_event.is_set():
            raise Stopped()

    def _trace(self, phase: str, **metadata):
        if self._trace_log is not None:
            self._trace_log.add(phase, self._current_step or None, **metadata)

    def _finish(self, status: str, summary: str):
        if self._input_state is not None:
            self._input_state.close()
        self._trace('terminal', status=status)
        self.done.emit(status, summary)

    def run(self):
        try:
            self._run_agent()
        except Stopped:
            self._finish('stop', f'第 {self._current_step} 步收到停止请求，没有执行后续动作')
        except Exception as error:
            if type(error).__name__ == 'FailSafeException':
                self._finish('stop', f'第 {self._current_step} 步检测到 PyAutoGUI 紧急停止（鼠标左上角）')
            else:
                self._trace('exception', error_type=type(error).__name__, action=self._last_action)
                self._finish('error', f'第 {self._current_step} 步、动作 {self._last_action} 后异常：{safe_error(error)}；请查看运行事件记录。')

    def _run_agent(self):
        c = self.config
        url = engine.resolve_endpoint(None, c.endpoint)
        engine.set_windows_dpi_awareness()
        import pyautogui as pg
        pg.FAILSAFE = True
        pg.PAUSE = 0.18
        self._input_state = engine.InputState(pg)

        store = ResponseStore(label='task')
        self._trace_log = RunTrace(store.path)
        self._trace('start', state='task')
        self.log_line.emit('info', f'API 响应：{store.path.name}')
        self.log_line.emit('info', f'运行事件诊断：{self._trace_log.path.name}（同一目录）')
        def on_api_response(event):
            record_response(store, event, c.api_key, self.response_record.emit)

        with httpx.Client(timeout=httpx.Timeout(c.request_timeout, connect=15),
                          follow_redirects=False, trust_env=True) as client:
            if c.vision_check:
                self.state.emit('正在验证视觉 API')
                self.log_line.emit('info', '正在进行视觉能力预检，确认模型真正接收图片…')
                engine.request_vision_preflight(client, endpoint=url, api_key=c.api_key,
                                                auth_mode=c.auth_mode, model=c.model,
                                                on_response=on_api_response)
                self._check_stop()
                self.log_line.emit('ok', '视觉能力预检通过')
            if c.start_delay:
                self.state.emit('正在准备桌面')
                self.log_line.emit('info', f'{c.start_delay} 秒后开始观察桌面（窗口已自动最小化）')
                if self._sleep(c.start_delay):
                    raise Stopped()

            history = []
            ledger = TaskLedger(c.task)
            self.task_snapshot.emit(ledger.display())
            clarifications: list[tuple[str, str]] = []
            last_question: str | None = None
            repeated_question_count = 0
            last_frame = None
            last_kind = None
            last_click_position: tuple[int, int] | None = None
            click_guard = ClickStagnationGuard()
            target_number = requested_video_number(c.task)
            video = VideoProgress(target_number) if target_number else None
            invalid_done_count = 0
            screenshot_retry_count = 0
            screenshot_flow = ClipboardFlow()
            if video:
                self.log_line.emit('info', f'检测到目标：第 {video.target} 个视频。启用被动视频计数；截图和 TXT 必须经由 Windows 图形界面保存。')
                self.progress.emit(f'视频 0/{video.target}')
            self.state.emit('正在执行任务')

            for step in range(1, c.max_steps + 1):
                self._current_step = step
                self._trace('step_begin', video_index=video.index if video else None,
                            video_target=video.target if video else None)
                self.task_snapshot.emit(ledger.display(video_context=video.context() if video else ''))
                self._check_stop()
                if pg.position() == (0, 0):
                    raise Stopped()

                frame = engine.capture_screenshot(pg, max_side=c.max_image_side,
                                                  image_format='jpeg')
                self._trace('screenshot_ok')
                self.shot.emit(base64.b64decode(frame.data_url.partition(',')[2]),
                               frame.image_width, frame.image_height)

                if last_frame is not None:
                    diff = engine.screenshot_difference(last_frame, frame)
                    if diff is not None:
                        history.append(
                            f'上一步操作：{last_kind}；新截图与上一步前相比，亮度变化约 {diff*100:.3f}%。'
                            + (' 画面变化较小，可能是获得焦点、正在加载，也可能没有生效；'
                               '请结合当前截图判断。' if diff < 0.002
                               else ' 画面已变化，请根据当前截图判断进展。')
                        )
                    repeated = click_guard.observe(last_kind, last_click_position, diff)
                    if repeated >= 3:
                        history.append(
                            f'提示：已连续 {repeated} 次点击近似同一位置且画面变化很小。'
                            '若确实无进展，请考虑等待、滚动或使用 ask_user。'
                            '不同位置的正常连续点击不受限制。'
                        )

                # 旧日志显示模型在第38-50步反复调用截图键，实际缺的是框选拖动。
                # 这里只注入文本反馈，不代替模型执行，也不新增非 GUI 工具。
                if screenshot_retry_count >= 2 and not any(
                    '【截图流程纠错】' in line for line in history[-14:]
                ):
                    history.append(
                        '【截图流程纠错】最近反复使用 PrintScreen / Win+Shift+S 却未看到保存结果。'
                        '若截图覆盖层已出现，别再按截图快捷键！'
                        '矩形截图应一次执行 drag：'
                        '{"action":"drag","x":200,"y":180,"to_x":1300,"to_y":780,'
                        '"duration":1.1,"hold_seconds":0.15}（坐标按当前截图调整），'
                        '然后启动画图 Ctrl+V 粘贴并通过可见 GUI 保存。'
                        '如果当前没有覆盖层，则先 Esc 并仅重新 Win+Shift+S 一次。'
                    )
                    history = history[-14:]
                    if screenshot_retry_count == 2:
                        self.log_line.emit('warn','检测到重复尝试截图：已提醒 Agent 改用长按拖动选区，不会强制终止。')
                flow_prompt = screenshot_flow.screenshot_prompt()
                if flow_prompt:
                    history.append(flow_prompt)
                    history = history[-14:]
                self.log_line.emit('info', f'步骤 {step} / {c.max_steps} · 请求模型分析屏幕')
                # Retry only transient / malformed responses, not arbitrary HTTP 4xx or
                # action-executor exceptions. Record each attempt in the API journal.
                for attempt in range(1, 4):
                    self._check_stop()
                    self._trace('api_request', attempt=attempt)
                    try:
                        action = engine.request_action(client, endpoint=url, api_key=c.api_key,
                                                       auth_mode=c.auth_mode, model=c.model,
                                                       task=c.task, frame=frame,
                                                       history=history + ([
                                                           '【格式纠正】上一响应无合法动作。请直接返回一个纯 JSON 对象；不要解释或输出 DSML。'
                                                       ] if attempt > 1 else []),
                                                       step=step, on_response=on_api_response,
                                                       clarifications=clarifications,
                                                       progress_context=video.context() if video else '',
                                                       task_context=ledger.context(video_context=video.context() if video else ''))
                        self._trace('api_parsed', attempt=attempt, action=action.get('action', '?'),
                                    keys=action.get('keys') if action.get('action') == 'keypress' else None)
                        break
                    except (ValueError, httpx.RequestError) as ex:
                        self._trace('api_retry', attempt=attempt, error_type=type(ex).__name__)
                        if attempt == 3:
                            raise
                        self.log_line.emit('warn', f'步骤 {step} · API 输出格式或网络异常，安全重试 {attempt}/2（未执行任何动作）')
                        if self._sleep(0.7 * attempt):
                            raise Stopped()
                self._check_stop()  # cancel while request in flight BEFORE moving the mouse
                kind = action['action']
                self._last_action = kind
                line = format_action(action)
                self.activity.emit(step, line)
                self.log_line.emit('action', f'[{step:02d}] {line}')

                # Passive annotations about THIS screenshot.  They do not execute
                # any special operation, save a frame, or write a file.
                if video and 'screen_video_id' in action:
                    changed, note = video.observe(action['screen_video_id'])
                    if changed:
                        self._trace('video_observed', video_index=video.index,
                                    video_target=video.target, state='new')
                        self.log_line.emit('ok', note)
                        self.progress.emit(f'视频 {video.index}/{video.target} · {video.stage}')
                        history.append(note)
                    elif video.pending_next:
                        history.append(note)
                    history = history[-14:]
                if video and 'gui_file' in action:
                    accepted, note = video.note_gui_file(action['gui_file'])
                    self._trace('gui_file_seen', video_index=video.index,
                                gui_kind=action['gui_file']['kind'], accepted=accepted)
                    self.log_line.emit('info' if accepted else 'warn', note)
                    history.append(note)
                    if accepted:
                        screenshot_flow.confirmed_file(action['gui_file']['kind'])
                    history = history[-14:]
                    self.progress.emit(f'视频 {video.index}/{video.target} · {video.stage}')

                if kind == 'done':
                    if video:
                        verified, reason = video.done_check()
                        if not verified:
                            invalid_done_count += 1
                            self.log_line.emit('warn', f'拒绝提前 done（{invalid_done_count} 次）：{reason}')
                            history.append('执行器拒绝 done：' + reason + '。请继续按程序进度完成，而不是再次宣称完成。')
                            history = history[-14:]
                            if invalid_done_count >= 4:
                                self._finish('blocked', '模型连续尝试提前结束，但视频或交付物未完成：' + reason)
                                return
                            continue
                        self.log_line.emit('ok', f'目标达成 · {reason}')
                        self.log_line.emit('ok', f'界面观察到 PNG：{video.desktop_png_name}')
                        self.log_line.emit('ok', f'界面观察到 TXT：{video.desktop_txt_name}')
                    ledger.note_model_observation(action.get('task_state'))
                    self.task_snapshot.emit(ledger.display(video_context=video.context() if video else ''))
                    self._finish('success', str(action.get('message') or '模型认为任务完成'))
                    return
                if kind == 'ask_user':
                    question = str(action.get('message') or '请说明接下来应该如何继续').strip()[:6000]
                    if question == last_question:
                        repeated_question_count += 1
                    else:
                        last_question = question
                        repeated_question_count = 1
                    if repeated_question_count >= 3:
                        self._finish('blocked', '模型连续重复询问同一问题，已保护性停止')
                        return
                    self.log_line.emit('info', f'步骤 {step} · 需要你的进一步确认，自动操作已暂停')
                    reply = self._await_user_reply(step, question)
                    self._check_stop()
                    clarifications.append((question, reply))
                    self.log_line.emit('ok', '已收到用户回复，将带着原任务上下文继续执行（回复内容不记入日志）')
                    # GUI minimizes before submitting the answer. Wait long enough for
                    # the window to disappear, otherwise the next screenshot sees Aurora.
                    if self._sleep(max(1.8, c.settle_time)):
                        raise Stopped()
                    last_frame, last_kind = None, None
                    last_click_position = None
                    click_guard.reset()
                    continue

                if video and video.index == 0 and is_next_video_action(action):
                    self.log_line.emit('warn', '尚未确认第一个视频，拒绝下刷，防止视频序号偏移。')
                    history.append('程序拒绝向下切换：请先根据当前截图填写 screen_video_id，登记第一条视频，然后再下刷。')
                    history = history[-14:]
                    continue
                if (video and video.locked and is_next_video_action(action)
                        and action.get('screen_video_id') == video.identities[-1]):
                    # Block switching away from the target in the video player,
                    # but let keyboard navigation work normally in Save As, Paint,
                    # Notepad, and File Explorer after the model leaves the video.
                    self.log_line.emit('warn', '已经到达目标视频，拒绝在播放器中继续下刷。请用 Windows 截图与保存界面继续。')
                    history.append('播放器处于第 N 条目标视频。不要再下刷，请通过键盘和鼠标截图、另存 PNG 和 TXT。')
                    history = history[-14:]
                    continue

                # 允许连续点击任意多个不同目标：仅对同一小区域反复点击且
                # 多次后截图始终不变的极端情形进行保护。
                next_click_position = None
                if kind in ('click', 'double_click'):
                    next_click_position = engine.image_to_screen(action, frame)
                    if click_guard.should_block(kind, next_click_position):
                        self._finish('blocked',
                                       '同一位置已反复点击且画面长期无变化，已停止以防卡死。'
                                       '正常连续点击不受次数限制。')
                        return

                # No background executor threads here; all input actions are executed serially.
                self._trace('execution_started', action=kind,
                            keys=action.get('keys') if kind == 'keypress' else None)
                result = engine.execute_action(pg, action, frame, state=self._input_state)
                clip_note = screenshot_flow.record(action)
                if clip_note:
                    self._trace('clipboard_flow', stage=screenshot_flow.stage,
                                recaptures=screenshot_flow.recaptures, paste_attempts=screenshot_flow.paste_attempts)
                    history.append(clip_note)
                    self.log_line.emit('info', '截图剪贴板流程 · ' + clip_note)
                self._trace('execution_ok', action=kind,
                            keys=action.get('keys') if kind == 'keypress' else None)
                ledger.note_model_observation(action.get('task_state'))
                ledger.record_execution(action)
                self.task_snapshot.emit(ledger.display(video_context=video.context() if video else ''))
                if kind == 'keypress' and (
                    'printscreen' in [str(k).lower() for k in action.get('keys', [])]
                    or set(str(k).lower() for k in action.get('keys', [])) == {'win','shift','s'}
                ):
                    screenshot_retry_count += 1
                elif kind in {'drag', 'mouse_up', 'type', 'keypress'}:
                    screenshot_retry_count = 0
                if video:
                    nav_note = video.after_execution(action)
                    if nav_note:
                        history.append(nav_note)
                        self.log_line.emit('info', nav_note)
                history.append(f'第 {step} 步：已执行 {result}；请在下一张截图中核实执行结果。')
                history = history[-14:]
                last_frame, last_kind = frame, kind
                last_click_position = next_click_position
                settle = max(c.settle_time,
                             1.5 if kind == 'keypress' and action.get('keys') == ['enter'] else 0)
                if self._sleep(settle):
                    raise Stopped()

            note = f'；当前仅确认视频 {video.index}/{video.target}，阶段：{video.stage}' if video else ''
            self._finish('limit', f'已达到最大操作步数 {c.max_steps}{note}；可以增大最大步数后重试')


def record_response(store: ResponseStore, event: dict, api_key: str, emit) -> None:
    """Fail a run rather than silently dropping a required response log."""
    record = store.append(event, api_key=api_key)
    emit(record)


class Stopped(Exception):
    pass


def format_action(action: dict) -> str:
    kind = action.get('action', '')
    if kind == 'ask_user':
        return f'请求人工确认 · {len(str(action.get("message", "")))} 字符'
    if kind == 'type':
        return f'输入文字 · {len(str(action.get("text", "")))} 字符（内容不写入日志）'
    if kind == 'keypress':
        return '快捷键 · ' + '+'.join(str(key) for key in action.get('keys', []))
    if kind in ('click', 'double_click', 'move','mouse_hold','mouse_down','mouse_up'):
        return f'{kind} · ({action.get("x")}, {action.get("y")})'
    if kind in ('scroll', 'scroll_up', 'scroll_down','scroll_left','scroll_right'):
        direction = kind.removeprefix('scroll_') if kind != 'scroll' else action.get('direction', '')
        direction_cn = {'up':'上','down':'下','left':'左','right':'右'}.get(direction,direction)
        return f'鼠标{direction_cn}滚 · {action.get("amount", 3)} 格 · ({action.get("x")}, {action.get("y")})'
    if kind == 'drag':
        return f'拖动 · ({action.get("x")}, {action.get("y")}) → ({action.get("to_x")}, {action.get("to_y")})'
    if kind in ('key_down','key_up','key_hold'):
        return f'{kind} · {action.get("key")}'+ (' · ' + str(action.get('seconds')) + ' 秒' if 'seconds' in action else '')
    if kind == 'wait':
        return f'等待 · {action.get("seconds", 1)} 秒'
    if kind in ('done', 'ask_user'):
        return f'{kind} · {str(action.get("message", ""))[:140]}'
    return f'未知动作 · {str(kind)[:80]}'
