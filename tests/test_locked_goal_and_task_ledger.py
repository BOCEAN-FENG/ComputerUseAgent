# -*- coding: utf-8 -*-
"""Regression tests for pinned goal and persistent visible progress."""
from __future__ import annotations

import base64
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import engine
from task_context import TaskLedger


class FakeResponse:
    status_code = 200

    def __init__(self, model_text: str):
        self._body = {'choices': [{'message': {'role': 'assistant', 'content': model_text}}]}
        self.text = json.dumps(self._body)

    def json(self):
        return self._body

    def raise_for_status(self):
        pass


class RecordingClient:
    def __init__(self, responses):
        self.responses = list(responses)
        self.payloads = []

    def post(self, *args, **kwargs):
        self.payloads.append(kwargs['json'])
        return FakeResponse(self.responses.pop(0))


class LockedGoalLedgerTests(unittest.TestCase):
    def test_goal_property_read_only_and_context_not_truncated(self):
        goal = '打开抖音网页版，刷到第三条，截图并保存桌面 TXT'
        state = TaskLedger(goal)
        with self.assertRaises(AttributeError):
            state.goal = '只截图就结束'
        state.note_model_observation({
            'completed_now': '已打开视频播放器',
            'evidence': '界面有明显抖音标识和可播放区域',
            'current': '全屏并确认第一条',
            'next': '向下切换到第二条',
        })
        self.assertEqual(state.goal, goal)
        self.assertIn('已打开视频播放器', state.context())
        self.assertIn('向下切换到第二条', state.context())
        self.assertIn(goal, state.context())
        state.note_model_observation({'completed_now':'已打开视频播放器','evidence':'重复截图'})
        self.assertEqual(len(state.completed), 1)

    def test_no_evidence_no_completed(self):
        state = TaskLedger('原始任务目标')
        state.note_model_observation({'completed_now':'假装已保存 TXT', 'current':'继续'})
        self.assertFalse(state.completed)
        self.assertEqual(state.goal, '原始任务目标')

    def test_invalid_model_goal_override_rejected(self):
        for bad in (
            {'action':'wait','seconds':1,'goal':'修改任务'},
            {'action':'wait','seconds':1,'task_state':{'original_task':'修改原任务'}},
            {'action':'wait','seconds':1,'task_state':{'completed_now':'已保存PNG'}},
        ):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                engine.validate_action_structure(bad)

    def test_wait_stagnation_prompts_change_not_false_completion(self):
        state = TaskLedger('打开抖音并保存视频摘要')
        for kind in ('wait','keypress','wait','wait','wait'):
            state.record_execution({'action':kind, 'keys':['enter']})
        self.assertIn('停滞提醒', state.context())
        self.assertFalse(state.completed)

    def test_screenshot_stagnation_prompts_drag(self):
        state = TaskLedger('截图并保存 TXT')
        for keys in (['win','shift','s'],['escape'],['printscreen'],['enter'],['win','shift','s']):
            state.record_execution({'action':'keypress', 'keys':keys})
        self.assertIn('drag', state.context())

    def test_request_repeats_immutable_goal_and_latest_state_every_turn(self):
        goal = '任务锁定：刷到第三个视频，并通过界面保存截图和 TXT'
        state = TaskLedger(goal)
        client = RecordingClient([
            '{"action":"wait","seconds":0.2,"task_state":{"current":"观察视频","next":"截图"}}',
            '{"action":"keypress","keys":["enter"]}',
        ])
        frame = engine.Screenshot('data:image/jpeg;base64,'+base64.b64encode(b'mock').decode(),
                                  1600, 900, 1600, 900)
        base = dict(endpoint='https://example.org/chat/completions',api_key='test',auth_mode='bearer',
                    model='mock',task=goal,frame=frame,history=['a']*30)
        a = engine.request_action(client, **base, step=1, task_context=state.context())
        state.note_model_observation(a.get('task_state'))
        engine.request_action(client, **base, step=2, task_context=state.context())
        self.assertEqual(len(client.payloads), 2)
        systems = [p['messages'][0]['content'] for p in client.payloads]
        self.assertEqual(systems[0], systems[1])
        self.assertIn(goal, systems[0])
        user = client.payloads[1]['messages'][1]['content'][0]['text']
        self.assertIn(goal, user)
        self.assertIn('观察视频', user)
        self.assertIn('截图', user)
        self.assertIn('任务状态与进度', user)


if __name__ == '__main__':
    unittest.main()
