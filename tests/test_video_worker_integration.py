# -*- coding: utf-8 -*-
"""End-to-end mocked loop: only mouse/keyboard actions and passive observations."""
from __future__ import annotations
import base64
import tempfile
import types
import sys
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
try:
    from PySide6.QtCore import QThread
except ImportError:
    fake_qt=types.ModuleType('PySide6')
    fake_qtcore=types.ModuleType('PySide6.QtCore')
    class Sig:
        def __init__(self):self.emissions=[]
        def emit(self,*args):self.emissions.append(args)
    fake_qtcore.Signal=lambda *a:Sig()
    fake_qtcore.QThread=type('QThread', (), {'__init__':lambda self,*a,**k:None})
    with patch.dict(sys.modules,{'PySide6':fake_qt,'PySide6.QtCore':fake_qtcore}):
        import worker
else:
    import worker
import engine

FRAME=engine.Screenshot('data:image/jpeg;base64,'+base64.b64encode(b'jpg').decode(),
                        800,600,800,600,bytes([0]*90))

class PgStub(types.ModuleType):
    KEYBOARD_KEYS=['down','enter','ctrl','printscreen','win','r']
    def __init__(self):
        super().__init__('pyautogui')
        self.calls=[]
    def position(self):return (15,15)
    def hotkey(self,*keys): self.calls.append(('hotkey',keys))

class FakeClient:
    def __init__(self,*a,**kw):pass
    def __enter__(self):return self
    def __exit__(self,*a):pass

class VideoWorkerIntegration(TestCase):
    def test_third_video_then_gui_files_without_shortcut_ops(self):
        task='打开抖音网页版刷到第三个视频，截取一帧 PNG 并在桌面写 TXT'
        cfg=worker.RunConfig('https://example.org/v1/chat/completions','dummy','bearer','mock',task,30,0,1600,False,0)
        ag=worker.AgentThread(cfg)
        # Works with both native Qt signals and the offline signal stub.
        done_events=[]
        if hasattr(ag.done, 'connect'):
            ag.done.connect(lambda *args: done_events.append(args))
        else:
            done_events=ag.done.emissions
        ag._sleep=lambda *_:False
        pg=PgStub()
        actions=[
            {'action':'keypress','keys':['down']}, # first video not yet known: blocked
            {'action':'wait','seconds':0,'screen_video_id':'作者A｜第一条做蛋糕视频'},
            {'action':'keypress','keys':['down'],'screen_video_id':'作者A｜第一条做蛋糕视频'},
            {'action':'wait','seconds':0,'screen_video_id':'作者B｜第二条公园散步视频'},
            {'action':'wait','seconds':0,'screen_video_id':'作者B｜第二条公园散步视频'},
            {'action':'done','message':'模型误以为第二个已经完成'},
            {'action':'keypress','keys':['down'],'screen_video_id':'作者B｜第二条公园散步视频'},
            {'action':'wait','seconds':0,'screen_video_id':'作者C｜第三条城市夜景视频'},
            {'action':'wait','seconds':0,'screen_video_id':'作者C｜第三条城市夜景视频'},
            {'action':'keypress','keys':['down'],'screen_video_id':'作者C｜第三条城市夜景视频'}, # forbidden
            {'action':'keypress','keys':['printscreen']}, # GUI snipping only, no IO
            {'action':'keypress','keys':['win','r']},  # GUI opens Paint or Notepad
            {'action':'wait','seconds':0,'gui_file':{'kind':'png','name':'第三条.png'}},
            {'action':'wait','seconds':0,'gui_file':{'kind':'txt','name':'第三条.txt'}},
            {'action':'done','message':'两个桌面文件已在资源管理器看到'},
        ]
        contexts=[]
        def planner(*args,**kwargs):
            contexts.append(kwargs.get('progress_context',''))
            return actions.pop(0)
        with tempfile.TemporaryDirectory() as temp:
            with (patch.dict(sys.modules,{'pyautogui':pg}),
                  patch.object(engine,'set_windows_dpi_awareness',lambda:None),
                  patch.object(engine,'capture_screenshot',lambda *a,**kw:FRAME),
                  patch.object(engine,'request_action',side_effect=planner),
                  patch.object(worker.httpx,'Client',FakeClient),
                  patch.dict('os.environ',{'LOCALAPPDATA':temp})):
                ag.run()
            self.assertEqual(done_events[-1][0],'success')
            self.assertEqual(pg.calls,[('hotkey',('down',)),('hotkey',('down',)),
                                       ('hotkey',('printscreen',)),('hotkey',('win','r'))])
            self.assertTrue(any('第 2' in text for text in contexts))
            self.assertFalse(list(Path(temp).rglob('*.png')),
                             'Worker must not create the screenshot file directly')
            self.assertFalse(list(Path(temp).rglob('*.txt')),
                             'Worker must not create desktop TXT directly')
            logs=list((Path(temp)/'AuroraComputerStudio'/'api_responses').glob('run-api-*.jsonl'))
            self.assertEqual(len(logs),1)
            self.assertIn('"phase": "terminal"',logs[0].read_text(encoding='utf-8'))
