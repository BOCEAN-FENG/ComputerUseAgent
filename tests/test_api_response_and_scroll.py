# -*- coding: utf-8 -*-
"""New regressions: every HTTP reply is recorded even when parsing fails."""
import base64
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import httpx

import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import engine
import response_store


FRAME = engine.Screenshot('data:image/jpeg;base64,' + base64.b64encode(b'jpeg').decode(),
                          1000, 700, 1000, 700)


class FakePyAutoGUI:
    def __init__(self):
        self.events = []
    def moveTo(self, x, y):
        self.events.append(('move', x, y))
    def scroll(self, amount):
        self.events.append(('scroll', amount))


class ResponseTests(unittest.TestCase):
    def request(self, client, events):
        return engine.request_action(
            client, endpoint='https://provider.test/v1/chat/completions',
            api_key='private-key', auth_mode='bearer', model='vision', task='test',
            frame=FRAME, history=[], step=3, on_response=events.append)

    def client(self, status, response_body):
        return httpx.Client(transport=httpx.MockTransport(
            lambda req: httpx.Response(status_code=status, content=response_body.encode('utf-8'))))

    def test_bad_json_action_still_preserves_every_response(self):
        body = json.dumps({'id': 'abc', 'choices': [{'message': {'content': 'I cannot tell what is on screen'}}]})
        events = []
        with self.client(200, body) as client:
            with self.assertRaisesRegex(ValueError, '模型未返回 JSON'):
                self.request(client, events)
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]['step'], 3)
        self.assertEqual(events[0]['http_status'], 200)
        self.assertEqual(events[0]['raw_body'], body)
        self.assertEqual(events[0]['model_content'], 'I cannot tell what is on screen')
        self.assertEqual(events[0]['parse_status'], 'error')

    def test_http_error_body_is_preserved(self):
        events = []
        with self.client(403, '{"error":"insufficient credits"}') as client:
            with self.assertRaisesRegex(RuntimeError, 'HTTP 403'):
                self.request(client, events)
        self.assertEqual(len(events), 1)
        self.assertIn('insufficient credits', events[0]['raw_body'])
        self.assertEqual(events[0]['parse_error'], 'HTTP 403')

    def test_normal_response_is_preserved(self):
        events = []
        with self.client(200, json.dumps({'choices': [{'message': {
            'content': '{"action":"scroll_down","x":300,"y":200,"amount":4}'}}]})) as client:
            result = self.request(client, events)
        self.assertEqual(result['action'], 'scroll_down')
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]['parse_status'], 'ok')

    def test_vision_preflight_error_is_recorded(self):
        events = []
        with self.client(200, json.dumps({'choices': [{'message': {'content': 'no digits'}}]})) as client:
            with self.assertRaisesRegex(RuntimeError, '预检失败'):
                engine.request_vision_preflight(client,
                    endpoint='https://provider.test/v1/chat/completions',
                    api_key='private-key', auth_mode='bearer', model='vision', on_response=events.append)
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]['phase'], 'vision-check')
        self.assertEqual(events[0]['parse_status'], 'error')

    def test_journal_survives_reload_and_redacts_key(self):
        with tempfile.TemporaryDirectory() as dir:
            folder = Path(dir)
            store = response_store.ResponseStore(folder, label='task')
            event = {'phase':'action', 'step': 3, 'model': 'vision', 'http_status':200,
                     'raw_body':'secret = my-api-key ; not JSON', 'model_content':'my-api-key',
                     'parse_status':'error', 'parse_error':'not JSON'}
            stored = store.append(event, api_key='my-api-key')
            self.assertEqual(stored['raw_body'], 'secret = [REDACTED_API_KEY] ; not JSON')
            with patch.object(response_store, 'response_directory', return_value=folder):
                items = response_store.read_records(store.path)
                self.assertEqual(len(response_store.list_sessions()), 1)
            self.assertEqual(items[0]['raw_body'], stored['raw_body'])
            self.assertNotIn('my-api-key', store.path.read_text(encoding='utf-8'))

    def test_scroll_up_and_down_and_legacy_direction(self):
        pg = FakePyAutoGUI()
        a = engine.execute_action(pg, {'action': 'scroll_up', 'x': 400, 'y': 300, 'amount': 2}, FRAME)
        b = engine.execute_action(pg, {'action': 'scroll_down', 'x': 400, 'y': 300, 'amount': 5}, FRAME)
        c = engine.execute_action(pg, {'action': 'scroll', 'x': 400, 'y': 300, 'direction': 'up', 'amount':3}, FRAME)
        self.assertEqual([e for e in pg.events if e[0] == 'scroll'], [('scroll', 2), ('scroll', -5), ('scroll', 3)])
        self.assertIn('scroll up', a)
        self.assertIn('scroll down', b)
        self.assertIn('scroll up', c)
        with self.assertRaisesRegex(ValueError, 'amount'):
            engine.execute_action(pg, {'action':'scroll_down', 'x':400, 'y':300, 'amount':100}, FRAME)

if __name__ == '__main__':
    unittest.main()
