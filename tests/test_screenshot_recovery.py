"""截图阶段反复热键时提醒模型拖动，而不是无限重新截图。"""
import base64
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parent))
# 复用已注入 fake qt 的 worker 测试夹具
from test_worker_offline import worker, FakePg, FakeClient, frame

class DragPG(FakePg):
    KEYBOARD_KEYS=['win','shift','s','printscreen']
    def moveTo(self, *args, **kwargs): self.calls.append(('moveTo',args,kwargs))
    def mouseDown(self, **kwargs): self.calls.append(('mouseDown',kwargs))
    def mouseUp(self, **kwargs): self.calls.append(('mouseUp',kwargs))

class ScreenshotRecovery(unittest.TestCase):
    def test_repeated_screenshots_prompt_drag_and_perform_drag(self):
        pg=DragPG()
        config=worker.RunConfig('https://test.example/v1/chat/completions','key','bearer','visual','test task',5,0,1600,False,0)
        agent=worker.AgentThread(config)
        agent._sleep=lambda _: False
        observed=[]
        sequence=[
            {'action':'keypress','keys':['printscreen']},
            {'action':'keypress','keys':['win','shift','s']},
            {'action':'drag','x':100,'y':100,'to_x':700,'to_y':600},
            {'action':'done','message':'完成测试'},
        ]
        def request(*args,**kwargs):
            observed.append(list(kwargs['history']))
            return sequence[len(observed)-1]
        with patch.multiple(worker.engine, set_windows_dpi_awareness=lambda:None,
                            capture_screenshot=lambda *a,**k:frame,
                            request_vision_preflight=lambda *a,**k:None), \
             patch.dict(sys.modules,{'pyautogui':pg}), \
             patch.object(worker.httpx,'Client', FakeClient), \
             patch.object(worker.engine,'request_action',side_effect=request), \
             patch.object(worker.engine.time,'sleep'):
            agent.run()
        self.assertEqual(agent.done.emissions[-1][0],'success')
        self.assertIn('【截图流程纠错】','\n'.join(observed[2]))
        self.assertIn('drag','\n'.join(observed[2]))
        self.assertEqual([a[0] for a in pg.calls if a[0] in ('mouseDown','mouseUp')], ['mouseDown','mouseUp'])

if __name__=='__main__': unittest.main()
