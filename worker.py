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
from collections import deque
from dataclasses import dataclass

import httpx
from PySide6.QtCore import QThread, Signal

import engine
from response_store import ResponseStore


@dataclass(frozen=True)
class RunConfig:
    endpoint: str
    api_key: str
    auth_mode: str
    model: str
    task: str
    max_steps: int = 25
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


class AgentThread(QThread):
    log_line = Signal(str, str)  # level, text
    activity = Signal(int, str)  # current step, sanitized short text
    shot = Signal(bytes, int, int)  # image bytes, picture width, picture height
    state = Signal(str)
    done = Signal(str, str)  # status: success/stop/blocked/error/limit, summary
    response_record = Signal(object)  # persisted response including raw provider body

    def __init__(self, config: RunConfig):
        super().__init__()
        self.config = config
        self.stop_event = threading.Event()

    def request_stop(self):
        self.stop_event.set()

    def _sleep(self, duration: float):
        return self.stop_event.wait(max(0, duration))

    def _check_stop(self):
        if self.stop_event.is_set():
            raise Stopped()

    def run(self):
        try:
            self._run_agent()
        except Stopped:
            self.done.emit('stop', '已停止任务，没有执行后续动作')
        except Exception as error:
            if type(error).__name__ == 'FailSafeException':
                self.done.emit('stop', '检测到 PyAutoGUI 紧急停止（鼠标左上角）')
            else:
                self.done.emit('error', safe_error(error))

    def _run_agent(self):
        c = self.config
        url = engine.resolve_endpoint(None, c.endpoint)
        engine.set_windows_dpi_awareness()
        import pyautogui as pg
        pg.FAILSAFE = True
        pg.PAUSE = 0.18

        store = ResponseStore(label='task')
        self.log_line.emit('info', f'本次 API 响应将自动记录于 {store.path.name}')
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
            last_frame = None
            last_kind = None
            consecutive_clicks = 0
            unchanged_clicks = 0
            recent_clicks = deque(maxlen=4)
            self.state.emit('正在执行任务')

            for step in range(1, c.max_steps + 1):
                self._check_stop()
                if pg.position() == (0, 0):
                    raise Stopped()

                frame = engine.capture_screenshot(pg, max_side=c.max_image_side,
                                                  image_format='jpeg')
                self.shot.emit(base64.b64decode(frame.data_url.partition(',')[2]),
                               frame.image_width, frame.image_height)

                if last_frame is not None:
                    diff = engine.screenshot_difference(last_frame, frame)
                    if diff is not None:
                        unchanged = diff < 0.002
                        if last_kind in ('click', 'double_click'):
                            unchanged_clicks = unchanged_clicks + 1 if unchanged else 0
                        else:
                            unchanged_clicks = 0
                        history.append(
                            f'After previous action ({last_kind}), visual difference={diff*100:.3f}%. '
                            + ('NO meaningful visual change; avoid random clicks.' if unchanged
                               else 'Screen changed; verify goal from this screenshot.')
                        )
                        if unchanged_clicks >= 3:
                            self.done.emit('blocked', '连续点击后屏幕无明显变化，已保护性停止')
                            return
                if consecutive_clicks >= 2:
                    history.append('Several consecutive clicks detected. Stop guessing coordinates. '
                                   'If in a text editor, perform type action next; otherwise ask_user.')

                self.log_line.emit('info', f'步骤 {step} / {c.max_steps} · 请求模型分析屏幕')
                action = engine.request_action(client, endpoint=url, api_key=c.api_key,
                                               auth_mode=c.auth_mode, model=c.model,
                                               task=c.task, frame=frame, history=history,
                                               step=step, on_response=on_api_response)
                self._check_stop()  # cancel while request in flight BEFORE moving the mouse
                kind = action['action']
                line = format_action(action)
                self.activity.emit(step, line)
                self.log_line.emit('action', f'[{step:02d}] {line}')

                if kind == 'done':
                    self.done.emit('success', str(action.get('message') or '模型认为任务已完成，请确认实际结果'))
                    return
                if kind == 'ask_user':
                    self.done.emit('blocked', str(action.get('message') or '模型需要人工处理'))
                    return

                if kind in ('click', 'double_click'):
                    if consecutive_clicks >= 3:
                        self.done.emit('blocked', '检测到连续点击循环，已拒绝继续点击')
                        return
                    x, y = engine.image_to_screen(action, frame)
                    if sum(abs(a-x) <= 55 and abs(b-y) <= 55 for a,b in recent_clicks) >= 2:
                        self.done.emit('blocked', '反复点击同一位置，已保护性停止')
                        return

                # No background executor threads here; all input actions are executed serially.
                result = engine.execute_action(pg, action, frame)
                history.append(f'step {step}: executed {result}; next screenshot verifies effect.')
                history = history[-14:]
                last_frame, last_kind = frame, kind
                if kind in ('click', 'double_click'):
                    consecutive_clicks += 1
                    recent_clicks.append(engine.image_to_screen(action, frame))
                else:
                    consecutive_clicks = 0
                    recent_clicks.clear()
                settle = max(c.settle_time,
                             1.5 if kind == 'keypress' and action.get('keys') == ['enter'] else 0)
                if self._sleep(settle):
                    raise Stopped()

            self.done.emit('limit', f'已达到最大操作步数 {c.max_steps}，请检查桌面是否完成任务')


def record_response(store: ResponseStore, event: dict, api_key: str, emit) -> None:
    """Fail a run rather than silently dropping a required response log."""
    record = store.append(event, api_key=api_key)
    emit(record)


class Stopped(Exception):
    pass


def format_action(action: dict) -> str:
    kind = action.get('action', '')
    if kind == 'type':
        return f'输入文字 · {len(str(action.get("text", "")))} 字符（内容不写入日志）'
    if kind == 'keypress':
        return '快捷键 · ' + '+'.join(str(key) for key in action.get('keys', []))
    if kind in ('click', 'double_click', 'move'):
        return f'{kind} · ({action.get("x")}, {action.get("y")})'
    if kind in ('scroll', 'scroll_up', 'scroll_down'):
        direction = kind.removeprefix('scroll_') if kind != 'scroll' else action.get('direction', '')
        return f'鼠标{"上" if direction == "up" else "下"}滚 · {action.get("amount", 3)} 格 · ({action.get("x")}, {action.get("y")})'
    if kind == 'drag':
        return f'拖动 · ({action.get("x")}, {action.get("y")}) → ({action.get("to_x")}, {action.get("to_y")})'
    if kind == 'wait':
        return f'等待 · {action.get("seconds", 1)} 秒'
    if kind in ('done', 'ask_user'):
        return f'{kind} · {str(action.get("message", ""))[:140]}'
    return f'未知动作 · {str(kind)[:80]}'
