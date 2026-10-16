# -*- coding: utf-8 -*-
"""Persistent task objective and observable progress notes for GUI-only computer use.

The user objective is locked for the entire run. Model output may annotate the
visible GUI, but it cannot modify the objective or claim verified deliverables.
Only the OS input executor issues mouse/keyboard events.
"""
from __future__ import annotations

from collections import deque


class TaskLedger:
    __slots__ = ('_goal', '_completed', '_current', '_next', '_pending_notes', '_recent_actions', '_last_observation')

    def __init__(self, goal: str):
        if not isinstance(goal, str) or not goal.strip():
            raise ValueError('任务目标不能为空')
        self._goal = goal.strip()
        self._completed: list[str] = []
        self._current = '观察当前桌面，确定第一个可执行操作'
        self._next = '根据实际界面逐步完成用户目标'
        self._pending_notes: list[str] = []
        self._recent_actions: deque[str] = deque(maxlen=8)
        self._last_observation = '尚无已核实的操作结果'

    @property
    def goal(self) -> str:
        """Read-only: never assigned from model output or user clarifications."""
        return self._goal

    @property
    def completed(self) -> tuple[str, ...]:
        return tuple(self._completed)

    def note_model_observation(self, update: dict | None):
        """Accept only limited model-reported, screenshot-based progress annotations.

        This is NOT external verification. The GUI deliberately labels these as
        model observations. No special action may be triggered by this metadata.
        """
        if not update:
            return
        evidence = update.get('evidence', '').strip()
        observed = update.get('completed_now', '').strip()
        if observed and evidence:
            text = observed[:160]
            if text not in self._completed:
                self._completed.append(text)
                self._completed = self._completed[-12:]
                self._last_observation = evidence[:180]
        current = update.get('current', '').strip()
        following = update.get('next', '').strip()
        if current:
            self._current = current[:180]
        if following:
            self._next = following[:180]

    def record_execution(self, action: dict):
        kind = str(action.get('action', ''))
        if kind in ('done', 'ask_user'):
            return
        if kind == 'keypress':
            name = kind + ':' + '+'.join(str(s).lower() for s in action.get('keys', []))
        elif kind in ('click', 'double_click'):
            name = kind + ':' + str(round(action.get('x', 0) / 40)) + ',' + str(round(action.get('y', 0) / 40))
        else:
            name = kind
        self._recent_actions.append(name)
        if self._current == '观察当前桌面，确定第一个可执行操作':
            self._current = f'已执行 {kind}，等待下一张截图确认结果'

    def remediation(self) -> str:
        recent = list(self._recent_actions)
        if len(recent) >= 5 and recent[-5:].count('wait') >= 4:
            return ('【停滞提醒】连续四步等待，没有明确进展。不要再原地 wait；'
                    '重新分析截图，采取推进当前子任务的不同键鼠动作。')
        screenshot_keys = {'keypress:win+shift+s', 'keypress:printscreen'}
        if sum(x in screenshot_keys for x in recent[-6:]) >= 3:
            return ('【截图循环提醒】近期已多次启动截图。先确认截图遮罩是否已出现；'
                    '如果已经出现，使用 drag 选区，切勿重新打开截图工具。'
                    '如果已截取到剪贴板，直接打开画图并 Ctrl+V。')
        return ''

    def context(self, *, video_context: str = '') -> str:
        completed = ('\n'.join(f'{i}. {x}' for i, x in enumerate(self._completed, 1))
                     if self._completed else '暂无（不要虚构已完成事项）')
        block = [
            '【锁定的总体任务目标｜不可修改、不可覆盖、不可重新解释】',
            self._goal,
            '【当前任务进度｜程序跨轮保存，完成项为模型截图观察而非文件系统证明】',
            f'已完成事项（模型观察）：\n{completed}',
            f'当前正在完成：{self._current}',
            f'下一步预期：{self._next}',
            f'最近进展证据：{self._last_observation}',
        ]
        if video_context:
            block.extend(('【程序维护的视频/交付物进度｜优先于模型自述】', video_context))
        fix = self.remediation()
        if fix:
            block.append(fix)
        block.append('每轮先对照原始目标，继续尚未完成的子任务。不要把重复截图/等待误认为任务进展。'
                     '遇到新信息时只更新当前进度，永远不得修改总体目标。')
        return '\n'.join(block)

    def display(self, *, video_context: str = '') -> dict[str, object]:
        return {
            'goal': self._goal,
            'completed': list(self._completed),
            'current': self._current,
            'next': self._next,
            'observation': self._last_observation,
            'video': video_context,
            'remediation': self.remediation(),
        }
