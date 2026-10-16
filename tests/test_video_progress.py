# -*- coding: utf-8 -*-
"""Pure GUI-only progress: metadata never runs shortcut file tools."""
from __future__ import annotations
import tempfile
import unittest
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from video_progress import VideoProgress, requested_video_number, is_next_video_action
from run_trace import RunTrace
import engine

class VideoProgressTest(unittest.TestCase):
    def test_detect_video_task(self):
        goal='帮我打开抖音网页版，刷到第三个视频停下来，截取一帧，保存桌面 TXT'
        self.assertEqual(requested_video_number(goal),3)
        self.assertIsNone(requested_video_number('打开视频，记事本输入文字'))

    def test_passive_counter_never_increments_on_down_alone(self):
        v=VideoProgress(3)
        self.assertFalse(v.done_check()[0])
        self.assertTrue(v.observe('小王｜第一条猫咪玩耍')[0])
        v.after_execution({'action':'keypress','keys':['down']})
        self.assertEqual(v.index,1)
        v.observe('小王｜第一条猫咪玩耍')
        self.assertEqual(v.index,1)
        self.assertFalse(v.observe('小李｜第二条黄狗散步')[0])
        self.assertTrue(v.observe('小李｜第二条黄狗散步')[0])
        self.assertEqual(v.index,2)
        self.assertFalse(v.done_check()[0])
        v.after_execution({'action':'scroll_down','x':100,'y':100})
        self.assertFalse(v.observe('小张｜第三条公园风景')[0])
        self.assertTrue(v.observe('小张｜第三条公园风景')[0])
        self.assertTrue(v.locked)
        self.assertFalse(v.done_check()[0])
        self.assertFalse(v.note_gui_file({'kind':'txt','name':'第三条.txt'})[0])
        self.assertTrue(v.note_gui_file({'kind':'png','name':'第三条.png'})[0])
        self.assertFalse(v.done_check()[0])
        self.assertTrue(v.note_gui_file({'kind':'txt','name':'第三条.txt'})[0])
        self.assertTrue(v.done_check()[0])

    def test_no_shortcut_tools_are_accepted(self):
        for forbidden in ('capture_frame','write_report','observe_video','shell','save_file'):
            with self.subTest(forbidden=forbidden), self.assertRaises(ValueError):
                engine.parse_action('{"action":"'+forbidden+'"}')
        legal = engine.parse_action('{"action":"wait","seconds":0.5,"screen_video_id":"作者丙｜第三条演奏视频"}')
        self.assertEqual(legal['action'],'wait')
        file_observation=engine.parse_action('{"action":"wait","seconds":0.5,"gui_file":{"kind":"png","name":"第三条.png"}}')
        self.assertEqual(file_observation['gui_file']['kind'],'png')
        for invalid in ['{"action":"wait","seconds":1,"gui_file":{"kind":"png","name":"C:/secret.png"}}',
                        '{"action":"wait","seconds":1,"gui_file":{"kind":"txt","name":"abc.exe"}}',
                        '{"action":"wait","seconds":1,"screen_video_id":7}']:
            with self.assertRaises(ValueError): engine.parse_action(invalid)

    def test_trace_still_reports_execution_stage(self):
        with tempfile.TemporaryDirectory() as temp:
            trace=RunTrace(Path(temp)/'api-test.jsonl')
            trace.add('step_begin',16)
            trace.add('api_parsed',16,action='keypress')
            trace.add('execution_started',16,action='keypress')
            rows=trace.path.read_text(encoding='utf-8').splitlines()
            self.assertEqual(len(rows),3)
            self.assertIn('execution_started',rows[-1])

if __name__=='__main__':unittest.main()
