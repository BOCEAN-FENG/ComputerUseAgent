# -*- coding: utf-8 -*-
"""Offline worker tests that do not require PySide6, a physical monitor or API access."""
from __future__ import annotations

import base64
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

qt = types.ModuleType('PySide6')
qt_core = types.ModuleType('PySide6.QtCore')

class TestSignal:
    def __init__(self):
        self.emissions = []
    def emit(self, *args):
        self.emissions.append(args)

class FakeThread:
    def __init__(self, *a, **k):
        pass

qt_core.Signal = lambda *args: TestSignal()
qt_core.QThread = FakeThread
with patch.dict(sys.modules, {'PySide6': qt, 'PySide6.QtCore': qt_core}):
    import worker

engine = worker.engine

class FakePg(types.ModuleType):
    KEYBOARD_KEYS = ['ctrl', 'v', 'win', 'r', 'enter']
    def __init__(self):
        super().__init__('pyautogui')
        self.calls = []
    def position(self):
        return (5, 5)
    def click(self, **kw):
        self.calls.append(('click', kw))
    def hotkey(self, *keys):
        self.calls.append(('hotkey', keys))

class FakeClient:
    def __init__(self, *args, **kwargs):
        pass
    def __enter__(self):
        return self
    def __exit__(self, *args):
        pass

frame = engine.Screenshot('data:image/jpeg;base64,'+base64.b64encode(b'fakejpg').decode(),
                          1024, 768, 1024, 768, bytes([0] * 60))

class WorkerOfflineTests(unittest.TestCase):
    def config(self):
        return worker.RunConfig('https://example.com/v1/chat/completions', 'secret', 'bearer',
                                'vision', 'Write hello', 12, 0, 1600, False, 0)

    def mock_resources(self, pg):
        return patch.multiple(engine,
            set_windows_dpi_awareness=lambda: None,
            capture_screenshot=lambda *a, **k: frame,
            request_vision_preflight=lambda *a, **k: None), \
            patch.dict(sys.modules, {'pyautogui': pg}), \
            patch.object(worker.httpx, 'Client', FakeClient)

    def test_stop_cancels_action_that_just_returned_from_api(self):
        pg = FakePg()
        agent = worker.AgentThread(self.config())
        def request(*a, **k):
            agent.request_stop()  # user pressed stop while API request was running
            return {'action': 'click', 'x': 200, 'y': 100}
        patches = self.mock_resources(pg)
        with patches[0], patches[1], patches[2], patch.object(engine, 'request_action', side_effect=request):
            agent.run()
        self.assertEqual(pg.calls, [])
        self.assertEqual(agent.done.emissions[-1][0], 'stop')

    def test_click_loop_stops_without_30_blind_clicks(self):
        pg = FakePg()
        agent = worker.AgentThread(self.config())
        positions = iter([100, 200, 300, 400, 500, 600])
        def req(*a, **k):
            return {'action': 'click', 'x': next(positions), 'y': 150}
        patches = self.mock_resources(pg)
        with patches[0], patches[1], patches[2], patch.object(engine, 'request_action', side_effect=req):
            agent.run()
        self.assertLessEqual(len(pg.calls), 3)
        self.assertEqual(agent.done.emissions[-1][0], 'blocked')

    def test_type_content_not_present_in_log_action(self):
        action = {'action': 'type', 'text': 'sensitive text password'}
        s = worker.format_action(action)
        self.assertNotIn('sensitive', s)
        self.assertIn(str(len(action['text'])), s)

    def test_https_enforced_by_endpoint_validator(self):
        with self.assertRaises(ValueError):
            engine.resolve_endpoint('http://not-local.example/v1', None)
        self.assertEqual(engine.resolve_endpoint('https://x.example/v1', None),
                         'https://x.example/v1/chat/completions')

if __name__ == '__main__':
    unittest.main()
