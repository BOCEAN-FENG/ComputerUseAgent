# -*- coding: utf-8 -*-
"""Advisory GUI-only screenshot-to-Paint workflow tracking.

This does not inspect the OS clipboard or operate files/windows. Only keyboard
and mouse activity reported by the agent is tracked, providing context that
helps the model avoid repeatedly restarting a successful snip.
"""
from __future__ import annotations


class ClipboardFlow:
    def __init__(self):
        self.stage = 'idle'
        self.recaptures = 0
        self.paste_attempts = 0

    @staticmethod
    def _keys(action: dict) -> set[str]:
        return {str(k).lower() for k in action.get('keys', [])}

    def record(self, action: dict) -> str | None:
        kind = action.get('action')
        keys = self._keys(action) if kind == 'keypress' else set()
        if kind == 'keypress' and (keys == {'win', 'shift', 's'} or 'printscreen' in keys):
            if self.stage in {'clipboard_image', 'paste_attempt'}:
                self.recaptures += 1
            self.stage = 'selecting'
            self.paste_attempts = 0
            return '已启动截图界面；看到矩形覆盖层后用 drag 框选，不要再按截图快捷键。'
        if kind == 'drag' and self.stage == 'selecting':
            self.stage = 'clipboard_image'
            self.paste_attempts = 0
            return '已通过拖动尝试矩形截图；截图应在剪贴板。后续 type 使用键盘输入，不会覆盖图片。'
        if kind == 'type' and self.stage in {'clipboard_image', 'paste_attempt'}:
            return '输入内容已通过键盘事件发送；不会覆盖截图剪贴板。请继续聚焦目标应用并尝试 Ctrl+V。'
        if kind == 'keypress' and keys == {'ctrl', 'v'} and self.stage in {'clipboard_image', 'paste_attempt'}:
            self.stage = 'paste_attempt'
            self.paste_attempts += 1
            return '已向当前焦点窗口发送 Ctrl+V；还不能断定粘贴成功。下一张截图检查画布。'
        if kind == 'keypress' and keys in ({'ctrl', 'c'}, {'ctrl', 'x'}):
            if self.stage in {'clipboard_image', 'paste_attempt'}:
                self.stage = 'clipboard_replaced'
                return 'Ctrl+C/X 可能改写截图剪贴板。'
        return None

    def screenshot_prompt(self) -> str:
        if self.stage == 'selecting':
            return ('【截图流程状态】已按截图快捷键。检查当前屏幕是否为矩形截图遮罩；'
                    '若已出现，用一次 drag 完成选区，不要反复重新启动截图。')
        if self.stage == 'clipboard_image':
            return ('【截图流程状态】上一步已拖动矩形选区，截图可能已进入剪贴板。'
                    'type 动作不会修改剪贴板。请通过键盘或鼠标切换到画图，确认其获得焦点后 Ctrl+V。'
                    '不要在没有证据时重做截图。')
        if self.stage == 'paste_attempt':
            return ('【截图粘贴待验证】Ctrl+V 仅已发送，尚未证明粘贴成功。'
                    '请看当前截图：如果画图画布出现图片，继续 GUI 另存为。'
                    '如果画布为空，先等待画图加载、点击画布使其获得焦点，然后再次 Ctrl+V；'
                    '不要立刻重新截图或重复启动画图。'
                    + ('若两次仍失败，可 ask_user 说明窗口状态。' if self.paste_attempts >= 2 else ''))
        if self.stage == 'clipboard_replaced':
            return '【截图流程状态】截图后执行了复制/剪切键，剪贴板图片可能已被覆盖；确有必要时重新截图。'
        return ''

    def confirmed_file(self, kind: str):
        if kind == 'png':
            self.stage = 'idle'
            self.paste_attempts = 0
            self.recaptures = 0
