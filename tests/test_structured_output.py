# -*- coding: utf-8 -*-
"""Prompt-format and DSML compatibility tests (offline)."""
import json
import sys
import unittest
from pathlib import Path
import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import engine

DSML = '''<｜｜DSML｜｜ calls>
<｜｜DSML｜｜ invoke name="click">
<｜｜DSML｜｜ parameter name="x" string="false">1245</｜｜DSML｜｜ parameter>
<｜｜DSML｜｜ parameter name="y" string="false">888</｜｜DSML｜｜ parameter>
</｜｜DSML｜｜ invoke>
</｜｜DSML｜｜ calls>'''

class StructuredOutputTests(unittest.TestCase):
    def test_prompt_requires_pure_json_and_prohibits_dsml(self):
        p = engine.SYSTEM_PROMPT
        for phrase in ('第一个非空字符必须是 {', 'DSML', '禁止', '只能是',
                       'action', 'scroll_up', 'scroll_down', 'ask_user', '允许连续多次点击'):
            self.assertIn(phrase, p)

    def test_json_output_still_works(self):
        self.assertEqual(engine.parse_action('{"action":"click","x":1245,"y":888}'),
                         {'action':'click','x':1245,'y':888})

    def test_actual_user_dsml_sample_normalizes_to_click(self):
        self.assertEqual(engine.parse_action(DSML),
                         {'action':'click', 'x':1245, 'y':888})

    def test_dsml_from_response_is_archived_with_original_text(self):
        body={'choices':[{'message':{'content':DSML}}]}
        events=[]
        def mock(req):
            parsed=json.loads(req.content)
            self.assertEqual(len(parsed['messages']),2)
            self.assertIn('禁止 DSML',parsed['messages'][1]['content'][0]['text'])
            return httpx.Response(200,json=body)
        screenshot=engine.Screenshot('data:image/png;base64,aW1n',1280,960,1920,1080)
        with httpx.Client(transport=httpx.MockTransport(mock)) as client:
            result=engine.request_action(client,endpoint='https://example.com/v1/chat/completions',
                        api_key='test',auth_mode='bearer',model='deepseek-flash',task='点击',
                        frame=screenshot,history=[],on_response=events.append)
        self.assertEqual(result['x'],1245)
        self.assertEqual(events[0]['parse_status'],'ok')
        self.assertEqual(events[0]['parse_mode'],'dsml_compat')
        self.assertEqual(events[0]['model_content'],DSML)

    def test_disallow_multiple_calls_or_unknown_tools(self):
        with self.assertRaises(ValueError):
            engine.parse_action(DSML.replace('</｜｜DSML｜｜ calls>',
                        '<｜｜DSML｜｜ invoke name="click"></｜｜DSML｜｜ invoke></｜｜DSML｜｜ calls>'))
        with self.assertRaises(ValueError):
            engine.parse_action(DSML.replace('invoke name="click"','invoke name="shell"'))

    def test_reject_extra_fields_and_quoted_numeric(self):
        with self.assertRaises(ValueError):
            engine.parse_action('{"action":"click","x":10,"y":10,"shell":"hi"}')
        with self.assertRaises(ValueError):
            engine.parse_action(DSML.replace('string="false">1245','string="true">1245'))

    def test_dsml_ask_user_supported(self):
        text=('''<｜｜DSML｜｜ calls><｜｜DSML｜｜ invoke name="ask_user">'''
              '''<｜｜DSML｜｜ parameter name="message" string="true">请确认视频</｜｜DSML｜｜ parameter>'''
              '''</｜｜DSML｜｜ invoke></｜｜DSML｜｜ calls>''')
        self.assertEqual(engine.parse_action(text), {'action':'ask_user','message':'请确认视频'})

if __name__=='__main__': unittest.main()
