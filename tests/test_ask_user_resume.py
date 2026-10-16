# -*- coding: utf-8 -*-
"""Human-in-the-loop regression tests; no Windows GUI, network, or monitor required."""
from __future__ import annotations

import base64
import json
import sys
import threading
import types
import unittest
from pathlib import Path
from unittest.mock import patch

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

if 'worker' not in sys.modules:
    qt = types.ModuleType('PySide6')
    qtcore = types.ModuleType('PySide6.QtCore')

    class SignalStub:
        def __init__(self):
            self.emissions = []
            self.event = threading.Event()
        def emit(self, *args):
            self.emissions.append(args)
            self.event.set()

    class FakeQThread:
        def __init__(self, *a, **k):
            pass

    qtcore.Signal = lambda *args: SignalStub()
    qtcore.QThread = FakeQThread
    with patch.dict(sys.modules, {'PySide6': qt, 'PySide6.QtCore': qtcore}):
        import worker
else:
    import worker

engine = worker.engine

FRAME = engine.Screenshot('data:image/jpeg;base64,'+base64.b64encode(b'jpg').decode(),
                          1000, 800, 1000, 800, bytes([0]*90))

class FakePyAutoGUI(types.ModuleType):
    def __init__(self):
        super().__init__('pyautogui')
        self.calls = []
    def position(self):
        return (10, 10)
    def click(self, **kwargs):
        self.calls.append(('click', kwargs))

class FakeClient:
    def __init__(self, *args, **kwargs):
        pass
    def __enter__(self):
        return self
    def __exit__(self, *args):
        pass

class AskUserTests(unittest.TestCase):
    def cfg(self):
        return worker.RunConfig('https://example.org/v1/chat/completions', 'topsecret',
                                'bearer', 'vision', 'Open third video', 9, 0, 1600, False, 0.0)

    def run_agent(self, agent, pyauto, planner):
        # replace settle waits, still retain reply event's blocking behavior
        agent._sleep = lambda _: False
        return (
            patch.dict(sys.modules, {'pyautogui': pyauto}),
            patch.object(engine, 'set_windows_dpi_awareness', lambda: None),
            patch.object(engine, 'capture_screenshot', lambda *a, **k: FRAME),
            patch.object(engine, 'request_action', side_effect=planner),
            patch.object(worker.httpx, 'Client', FakeClient),
        )

    def test_pauses_then_continues_same_task_with_human_reply(self):
        pg = FakePyAutoGUI()
        agent = worker.AgentThread(self.cfg())
        agent.user_question.emissions.clear()
        agent.user_question.event.clear()
        agent.done.emissions.clear()
        questions = []
        samples = []
        original_emit = agent.user_question.emit
        def question_emit(step, question):
            questions.append((step, question))
            original_emit(step, question)
        agent.user_question.emit = question_emit
        actions = iter([
            {'action':'ask_user', 'message':'当前视频还是第三个？'},
            {'action':'click', 'x':300, 'y':240},
            {'action':'done', 'message':'ok'},
        ])
        def request(*args, **kwargs):
            samples.append(kwargs)
            return next(actions)
        patches = self.run_agent(agent, pg, request)
        with patches[0], patches[1], patches[2], patches[3], patches[4]:
            thread = threading.Thread(target=agent.run)
            thread.start()
            self.assertTrue(agent.user_question.event.wait(2))
            self.assertEqual(pg.calls, [])
            self.assertTrue(thread.is_alive())
            self.assertFalse(agent.submit_reply(999, 'bad step'))
            self.assertFalse(agent.submit_reply(1, '  '))
            self.assertTrue(agent.submit_reply(1, '返回列表，打开第三个视频'))
            self.assertFalse(agent.submit_reply(1, 'second response'))
            thread.join(timeout=4)
        self.assertFalse(thread.is_alive())
        self.assertEqual(questions, [(1, '当前视频还是第三个？')])
        self.assertEqual(agent.done.emissions[-1][0], 'success')
        self.assertEqual(pg.calls[0][0], 'click')
        self.assertEqual(samples[1]['task'], samples[0]['task'])
        self.assertEqual(samples[1]['clarifications'], [('当前视频还是第三个？', '返回列表，打开第三个视频')])

    def test_stop_during_wait_never_executes_follow_up_actions(self):
        pg = FakePyAutoGUI()
        agent = worker.AgentThread(self.cfg())
        agent.user_question.emissions.clear()
        agent.user_question.event.clear()
        agent.done.emissions.clear()
        def ask(*args, **kwargs):
            return {'action':'ask_user','message':'需要确认'}
        patches = self.run_agent(agent, pg, ask)
        with patches[0], patches[1], patches[2], patches[3], patches[4]:
            thread = threading.Thread(target=agent.run)
            thread.start()
            self.assertTrue(agent.user_question.event.wait(2))
            agent.request_stop()
            self.assertFalse(agent.submit_reply(1, '太晚的回复'))
            thread.join(timeout=3)
        self.assertFalse(thread.is_alive())
        self.assertEqual(pg.calls, [])
        self.assertEqual(agent.done.emissions[-1][0], 'stop')

    def test_prompt_contains_human_reply_and_original_task(self):
        received = []
        def transport(req):
            received.append(json.loads(req.content.decode('utf-8')))
            return httpx.Response(200, json={'choices':[{'message':{'content':'{"action":"done","message":"ok"}'}}]})
        with httpx.Client(transport=httpx.MockTransport(transport)) as client:
            engine.request_action(client,
                endpoint='https://example.org/v1/chat/completions', api_key='key',
                auth_mode='bearer', model='vision', task='Find third video',
                frame=FRAME, history=['step 1 previous action'],
                clarifications=[('current video or third?', 'Go back to list and open third')])
        prompt = received[0]['messages'][1]['content'][0]['text']
        self.assertIn('Find third video', prompt)
        self.assertIn('current video or third?', prompt)
        self.assertIn('Go back to list and open third', prompt)
        self.assertIn('【当前任务】', prompt)
        self.assertIn('【前序动作与反馈】', prompt)
        self.assertIn('允许连续多次点击', received[0]['messages'][0]['content'])

    def test_duplicate_question_stops_after_three_identical_attempts(self):
        pg = FakePyAutoGUI()
        agent = worker.AgentThread(self.cfg())
        agent.user_question.emissions.clear()
        agent.user_question.event.clear()
        agent.done.emissions.clear()
        def ask(*a, **k):
            return {'action':'ask_user', 'message':'same question'}
        patches = self.run_agent(agent, pg, ask)
        with patches[0], patches[1], patches[2], patches[3], patches[4]:
            t = threading.Thread(target=agent.run)
            t.start()
            for step in (1, 2):
                # deterministic polling without assuming shared stub signal reset
                import time
                end = time.monotonic() + 3
                while len(agent.user_question.emissions) < step and time.monotonic() < end:
                    time.sleep(0.01)
                self.assertGreaterEqual(len(agent.user_question.emissions), step)
                self.assertTrue(agent.submit_reply(step, f'answer {step}'))
            t.join(timeout=3)
        self.assertFalse(t.is_alive())
        self.assertEqual(agent.done.emissions[-1][0], 'blocked')
        self.assertEqual(pg.calls, [])

if __name__ == '__main__':
    unittest.main()
