"""离线验证 Windows 截图矩形拖动和完整键鼠动作协议。"""
import base64
import sys
import time
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import engine

FRAME=engine.Screenshot('data:image/jpeg;base64,'+base64.b64encode(b'fake').decode(), 800,450,1600,900)

class FakePG:
    KEYBOARD_KEYS=['ctrl','win','shift','s','enter','down','esc','f11','alt','tab','v','space','left']
    def __init__(self, fail_move=False):
        self.events=[]
        self.fail_move=fail_move
    def moveTo(self, *a, **kw):
        self.events.append(('move', a,kw))
        if self.fail_move and self.events[-1][1][:2] == (1200, 800):
            raise RuntimeError('move failed')
    def mouseDown(self, **kw): self.events.append(('down', kw))
    def mouseUp(self, **kw): self.events.append(('up', kw))
    def click(self, **kw): self.events.append(('click',kw))
    def doubleClick(self, **kw): self.events.append(('double',kw))
    def scroll(self,n): self.events.append(('scroll',n))
    def hscroll(self,n): self.events.append(('hscroll',n))
    def hotkey(self,*a): self.events.append(('hotkey',a))
    def keyDown(self,k): self.events.append(('key_down',k))
    def keyUp(self,k): self.events.append(('key_up',k))

class FullKeyboardMouseTests(unittest.TestCase):
    def test_drag_uses_press_move_release_with_dpi_scale_and_optional_hold(self):
        pg=FakePG()
        act={'action':'drag','x':100,'y':50,'to_x':600,'to_y':400,'duration':1.3,'hold_seconds':0.12}
        with patch.object(engine.time,'sleep'):
            out=engine.execute_action(pg,act,FRAME)
        self.assertEqual([evt[0] for evt in pg.events],['move','down','move','up'])
        self.assertEqual(pg.events[0][1],(200,100))
        self.assertEqual(pg.events[2][1],(1200,800))
        self.assertEqual(pg.events[2][2]['duration'],1.3)
        self.assertIn('drag',out)

    def test_drag_always_releases_if_move_fails(self):
        pg=FakePG(fail_move=True)
        with patch.object(engine.time,'sleep'):
            with self.assertRaisesRegex(RuntimeError,'move failed'):
                engine.execute_action(pg,{'action':'drag','x':100,'y':50,
                                         'to_x':600,'to_y':400},FRAME)
        self.assertEqual(pg.events[-1][0],'up')

    def test_mouse_hold_press_and_release(self):
        pg=FakePG()
        with patch.object(engine.time,'sleep') as pause:
            engine.execute_action(pg,{'action':'mouse_hold','x':200,'y':250,'seconds':2,'button':'right'},FRAME)
        self.assertEqual([a[0] for a in pg.events],['move','down','up'])
        self.assertEqual(pg.events[-1][1]['button'],'right')
        pause.assert_called_once_with(2.0)

    def test_mouse_down_move_mouse_up_state(self):
        pg=FakePG(); state=engine.InputState(pg,lease_seconds=8)
        with patch.object(engine.time,'sleep'):
            engine.execute_action(pg,{'action':'mouse_down','x':50,'y':50},FRAME,state)
            engine.execute_action(pg,{'action':'move','x':300,'y':320,'duration':0.8},FRAME,state)
            engine.execute_action(pg,{'action':'mouse_up','x':500,'y':400},FRAME,state)
        state.close()
        self.assertEqual([a[0] for a in pg.events],['move','down','move','move','up'])
        self.assertEqual(pg.events[-1][1]['button'],'left')

    def test_key_hold_and_key_down_up(self):
        pg=FakePG(); state=engine.InputState(pg,lease_seconds=8)
        with patch.object(engine.time,'sleep'):
            engine.execute_action(pg,{'action':'key_hold','key':'down','seconds':0.8},FRAME,state)
            engine.execute_action(pg,{'action':'key_down','key':'shift'},FRAME,state)
            engine.execute_action(pg,{'action':'keypress','keys':['enter']},FRAME,state)
            engine.execute_action(pg,{'action':'key_up','key':'shift'},FRAME,state)
        state.close()
        self.assertEqual([e[0] for e in pg.events],['key_down','key_up','key_down','hotkey','key_up'])

    def test_stop_releases_left_button_and_modifier(self):
        pg=FakePG(); state=engine.InputState(pg,lease_seconds=8)
        engine.execute_action(pg,{'action':'mouse_down','x':100,'y':200},FRAME,state)
        engine.execute_action(pg,{'action':'key_down','key':'shift'},FRAME,state)
        state.close()
        self.assertIn(('up',{'button':'left'}),pg.events)
        self.assertIn(('key_up','shift'),pg.events)

    def test_mouse_lease_watchdog_auto_releases(self):
        pg=FakePG(); state=engine.InputState(pg,lease_seconds=0.05)
        engine.execute_action(pg,{'action':'mouse_down','x':100,'y':200},FRAME,state)
        time.sleep(0.12)
        state.close()
        self.assertIn(('up',{'button':'left'}),pg.events)
        self.assertEqual(len([e for e in pg.events if e[0]=='up']),1)

    def test_horizontal_scroll_and_triple_click(self):
        pg=FakePG()
        engine.execute_action(pg,{'action':'scroll_left','x':100,'y':200,'amount':3},FRAME)
        engine.execute_action(pg,{'action':'scroll_right','x':100,'y':200,'amount':2},FRAME)
        engine.execute_action(pg,{'action':'click','x':100,'y':200,'clicks':3},FRAME)
        self.assertIn(('hscroll',-3),pg.events)
        self.assertIn(('hscroll',2),pg.events)
        self.assertEqual(pg.events[-1][1]['clicks'],3)

    def test_invalid_drag_duration_bounds_and_unknown_keys(self):
        pg=FakePG()
        for action in [
            {'action':'drag','x':1,'y':1,'to_x':4,'to_y':5,'duration':100},
            {'action':'drag','x':1,'y':1,'to_x':1,'to_y':1},
            {'action':'mouse_hold','x':1,'y':1,'seconds':9},
            {'action':'keypress','keys':['ctrl',123]},
            {'action':'click','x':1,'y':1,'clicks':99},
        ]:
            with self.subTest(action=action):
                with self.assertRaises(ValueError): engine.execute_action(pg,action,FRAME)
        with self.assertRaisesRegex(ValueError,'未知的键盘按键'):
            engine.execute_action(pg,{'action':'key_hold','key':'unrealkey','seconds':0.1},FRAME)
        self.assertEqual(pg.events,[])

    def test_prompt_enforces_gui_only_and_snipping_drag(self):
        self.assertIn('Win+Shift+S',engine.SYSTEM_PROMPT)
        self.assertIn('drag',engine.SYSTEM_PROMPT)
        self.assertIn('按住左键拖动并松开',engine.SYSTEM_PROMPT)
        for banned in ['capture_frame','write_report','observe_video']:
            with self.assertRaises(ValueError): engine.parse_action('{"action":"'+banned+'"}')

if __name__=='__main__': unittest.main()
