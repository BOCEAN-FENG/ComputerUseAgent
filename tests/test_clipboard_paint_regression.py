# -*- coding: utf-8 -*-
"""Regression: screenshots must survive launching Paint via Win+R -> type mspaint."""
import base64
import sys
import unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import clipboard_flow
import engine
import text_input

FRAME = engine.Screenshot('data:image/jpeg;base64,'+base64.b64encode(b'fake').decode(),
                          800, 450, 1600, 900)

class KeyboardStub:
    KEYBOARD_KEYS = ['win', 'r', 'shift', 's', 'enter', 'ctrl', 'v']
    def __init__(self):
        self.events=[]
        self.clipboard='[binary PNG image clipboard, 87KB]'
    def hotkey(self,*keys): self.events.append(('hotkey', keys))
    def write(self, text, interval=0): self.events.append(('write',text))
    def press(self,k): self.events.append(('press',k))

class ClipboardPaintRegression(unittest.TestCase):
    def test_launch_paint_and_paste_does_not_replace_image_clipboard(self):
        pg=KeyboardStub()
        engine.execute_action(pg,{'action':'keypress','keys':['win','r']}, FRAME)
        engine.execute_action(pg,{'action':'type','text':'mspaint'}, FRAME)
        engine.execute_action(pg,{'action':'keypress','keys':['enter']}, FRAME)
        engine.execute_action(pg,{'action':'keypress','keys':['ctrl','v']}, FRAME)
        self.assertEqual(pg.clipboard, '[binary PNG image clipboard, 87KB]')
        self.assertEqual(pg.events,[('hotkey',('win','r')),('write','mspaint'),
                                    ('hotkey',('enter',)),('hotkey',('ctrl','v'))])

    def test_unicode_uses_keyboard_input_without_clipboard(self):
        pg=KeyboardStub()
        out=[]
        with patch.object(text_input.sys, 'platform', 'win32'):
            result=text_input.type_text(pg,'桌面截图：abc\n画图 😀',unicode_sender=out.append)
        self.assertIn('keyboard-only',result)
        self.assertEqual(out,['桌面截图：','画图','😀'])
        self.assertIn(('write','abc'),pg.events)
        self.assertIn(('press','enter'),pg.events)
        self.assertEqual(pg.clipboard,'[binary PNG image clipboard, 87KB]')

    def test_unicode_utf16_surrogate_pair(self):
        self.assertEqual(text_input.unicode_units('A😀'),[65,0xD83D,0xDE00])

    def test_no_silent_clipboard_fallback(self):
        pg=KeyboardStub()
        with self.assertRaisesRegex(RuntimeError,'无剪贴板'):
            text_input.type_text(pg,'中文',platform='linux')
        self.assertEqual(pg.clipboard,'[binary PNG image clipboard, 87KB]')

    def test_paste_window_focus_recovery_prompt(self):
        flow=clipboard_flow.ClipboardFlow()
        flow.record({'action':'keypress','keys':['win','shift','s']})
        flow.record({'action':'drag','x':20,'y':20,'to_x':500,'to_y':400})
        self.assertEqual(flow.stage,'clipboard_image')
        flow.record({'action':'type','text':'mspaint'})
        self.assertEqual(flow.stage,'clipboard_image')
        flow.record({'action':'keypress','keys':['ctrl','v']})
        self.assertEqual(flow.stage,'paste_attempt')
        self.assertIn('画布',flow.screenshot_prompt())
        self.assertIn('焦点',flow.screenshot_prompt())
        flow.record({'action':'keypress','keys':['ctrl','v']})
        self.assertEqual(flow.paste_attempts,2)
        self.assertIn('ask_user',flow.screenshot_prompt())

    def test_relaunch_screenshot_does_not_erase_recovery_history(self):
        flow=clipboard_flow.ClipboardFlow()
        actions=[{'action':'keypress','keys':['win','shift','s']},
                 {'action':'drag'},
                 {'action':'keypress','keys':['ctrl','v']},
                 {'action':'keypress','keys':['win','shift','s']}]
        for a in actions: flow.record(a)
        self.assertEqual(flow.recaptures,1)
        flow.confirmed_file('png')
        self.assertEqual(flow.recaptures,0)
        self.assertEqual(flow.stage,'idle')

    def test_prompt_requires_clipboard_preservation_and_focusing_paint(self):
        self.assertIn('不会覆盖截图剪贴板', engine.SYSTEM_PROMPT)
        self.assertIn('单击画图画布', engine.SYSTEM_PROMPT)

if __name__=='__main__': unittest.main()
