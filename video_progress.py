# -*- coding: utf-8 -*-
"""Passive progress ledger. Never controls OS or creates/reads task artifacts.

A vision model may describe the *current screenshot* using optional metadata
in an ordinary mouse/keyboard action. Such metadata is NOT an executable tool.
Counters remain tentative because neither screenshots nor a VLM prove a stable
video identity; two consistent observations after a navigation are required.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

NUMBERS = {'一': 1, '二': 2, '两': 2, '三': 3, '四': 4, '五': 5,
           '六': 6, '七': 7, '八': 8, '九': 9, '十': 10}


def requested_video_number(task: str) -> int | None:
    if not ('视频' in task and any(k in task for k in ('抖音', '刷视频', '刷到', '第'))):
        return None
    match = re.search(r'第\s*(\d{1,2}|[一二两三四五六七八九十])\s*个?\s*视频', task)
    if not match:
        return None
    digits = match.group(1)
    value = int(digits) if digits.isascii() and digits.isdigit() else NUMBERS.get(digits)
    return value if value is not None and 1 <= value <= 20 else None


def is_next_video_action(action: dict) -> bool:
    if action['action'] == 'keypress':
        return [str(k).lower() for k in action.get('keys', [])] in (['down'], ['pagedown'])
    if action['action'] == 'scroll_down':
        return True
    return action['action'] == 'scroll' and action.get('direction') == 'down'


@dataclass
class VideoProgress:
    target: int
    index: int = 0
    identities: list[str] = field(default_factory=list)
    pending_next: bool = False
    candidate_identity: str | None = None
    attempts_without_change: int = 0
    desktop_png_name: str | None = None
    desktop_txt_name: str | None = None

    @property
    def locked(self) -> bool:
        return self.index >= self.target

    @property
    def stage(self) -> str:
        if not self.locked:
            return ('等待确认第一个视频' if self.index == 0
                    else '等待切换后确认新视频' if self.pending_next else '可以继续浏览')
        if not self.desktop_png_name:
            return '目标已到达：通过截图快捷键、画图和另存为在桌面保存 PNG'
        if not self.desktop_txt_name:
            return 'PNG 已在桌面界面确认：通过记事本保存 TXT'
        return '两份文件已通过桌面界面观察：可结束'

    def observe(self, identifier: str) -> tuple[bool, str]:
        token = identifier.strip()
        if not (5 <= len(token) <= 160) or token.lower() in {'未知视频', '当前视频', '视频内容', '视频画面'}:
            return False, '可见视频标识不够具体，不能凭章节号或动态画面猜测序号。'
        if self.index == 0:
            self.index = 1
            self.identities.append(token)
            self.pending_next = False
            return True, f'从截图确认第 1/{self.target} 条视频：{token[:70]}'
        if token == self.identities[-1]:
            if self.pending_next:
                self.attempts_without_change += 1
                self.candidate_identity = None  # Two matching *consecutive* screenshots required.
                return False, '下刷后仍是原视频，暂不增加计数。'
            return False, f'视频仍是第 {self.index}/{self.target} 条。'
        if self.locked:
            return False, '目标视频已确认，后续不能再计数。'
        if not self.pending_next:
            return False, '视频标识变化，但此前没有下一条视频操作；不自动增加计数。'
        if token in self.identities:
            self.candidate_identity = None
            return False, '截图与曾见过的视频一致，不能算新的一条。'
        if self.candidate_identity != token:
            self.candidate_identity = token
            return False, '疑似切换了视频，下一次截图仍需看到相同的作者/标题才能确认。'
        self.candidate_identity = None
        self.index += 1
        self.identities.append(token)
        self.pending_next = False
        self.attempts_without_change = 0
        return True, f'确认到第 {self.index}/{self.target} 条视频：{token[:70]}'

    def after_execution(self, action: dict) -> str | None:
        if not is_next_video_action(action):
            return None
        if self.index == 0:
            return '第一个视频尚未确认，暂不计数；等待新的截图。'
        if self.locked:
            return '已经到达目标视频；请勿继续切换视频。'
        self.pending_next = True
        self.candidate_identity = None
        return (f'已执行可能切换视频的键鼠动作。保持第 {self.index} 条计数，'
                '只有后续两张截图识别为同一条新视频才增加计数。')

    def note_gui_file(self, gui_file: dict) -> tuple[bool, str]:
        """Record a *model-reported visible Desktop GUI filename*, not filesystem I/O."""
        if not self.locked:
            return False, '目标视频尚未到达，暂不记录桌面文件。'
        kind, name = gui_file['kind'], gui_file['name']
        if kind == 'png':
            self.desktop_png_name = name
            return True, f'模型通过桌面界面报告看到 PNG：{name}'
        if kind == 'txt':
            if not self.desktop_png_name:
                return False, '还没通过桌面界面确认 PNG，先完成截图保存。'
            self.desktop_txt_name = name
            return True, f'模型通过桌面界面报告看到 TXT：{name}'
        return False, '不支持的文件类型。'

    def done_check(self) -> tuple[bool, str]:
        if not self.locked:
            return False, f'当前仅确认第 {self.index}/{self.target} 条视频。'
        if not self.desktop_png_name:
            return False, '请用 Windows 图形界面保存桌面 PNG，并在资源管理器中确认可见。'
        if not self.desktop_txt_name:
            return False, '请用记事本通过 GUI 创建桌面 TXT，并在资源管理器中确认可见。'
        return True, ('模型已从桌面 GUI 截图报告看到两个文件；'
                      '这不是文件系统级验证，若有疑问请人工确认。')

    def context(self) -> str:
        current = ('尚未登记第一条视频；看到稳定作者/标题后，在下一步动作中填 screen_video_id。'
                   if self.index == 0 else f'已确认第 {self.index}/{self.target} 条：{self.identities[-1]}。')
        next_note = ('刚向下切换，请在连续两轮动作响应中用 screen_video_id 提供相同的独立新视频标识；'
                     '未确认前不继续下刷。') if self.pending_next else ''
        final = ('【已到目标】不能继续下刷。只能用鼠标/键盘通过 Windows 图形界面保存一帧 PNG 到桌面、'
                 '在记事本中编辑文字并“另存为”桌面 TXT。不要要求程序直接创建文件。'
                 '使用资源管理器实际显示桌面文件后，才在普通键鼠动作 JSON 中附加 gui_file；'
                 '之后才能 done。') if self.locked else ''
        return (f'【只读进度提示：不提供专用操作工具】\n目标第 {self.target} 条独立视频，'
                f'当前状态：{current}\n阶段：{self.stage}。{next_note}{final}\n'
                f'历史视频标识：{self.identities[-5:]!r}。\n'
                '请勿混淆视频“第2章”和第二条视频。screen_video_id/gui_file 只是对当前截图的文字标注，'
                '不触发系统操作；真正操作必须是键盘或鼠标。')
