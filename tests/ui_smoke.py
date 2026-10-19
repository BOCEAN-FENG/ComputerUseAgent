"""Native Qt UI checks, run separately from tests using fake Qt modules.

QT_QPA_PLATFORM=offscreen python tests/ui_smoke.py
No provider calls, screenshots of the user's desktop, or real keyboard input.
"""
from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PySide6.QtCore import QObject, QSettings, Signal, QBuffer, QIODevice, Qt
from PySide6.QtGui import QColor, QImage
from PySide6.QtWidgets import QApplication, QLineEdit

import main


class FakeAgent(QObject):
    log_line = Signal(str, str)
    response_record = Signal(object)
    activity = Signal(int, str)
    progress = Signal(str)
    task_snapshot = Signal(dict)
    shot = Signal(bytes, int, int)
    user_question = Signal(int, str)
    state = Signal(str)
    done = Signal(str, str)
    finished = Signal()

    def __init__(self, config):
        super().__init__()
        self.config = config
        self.running = False
        self.replies = []

    def start(self):
        self.running = True

    def isRunning(self):
        return self.running

    def submit_reply(self, step, answer):
        self.replies.append((step, answer))
        return True

    def request_stop(self):
        self.running = False
        self.done.emit('stop', '测试停止')
        self.finished.emit()


class NativeUI(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        cls.app.setStyle('Fusion')

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.env_patch = patch.dict(os.environ, {'LOCALAPPDATA': self.temp.name})
        self.env_patch.start()
        settings = QSettings(str(Path(self.temp.name) / 'prefs.ini'), QSettings.Format.IniFormat)
        self.settings_patch = patch.object(main, 'QSettings', return_value=settings)
        self.settings_patch.start()
        self.window = main.Studio()
        self.window.show()
        self.pump()

    def tearDown(self):
        self.window.busy = False
        self.window.agent = None
        if hasattr(self.window, 'options_dialog'):
            self.window.options_dialog.close()
        self.window.tray.hide()
        self.window.hide()
        self.window.deleteLater()
        self.pump()
        self.settings_patch.stop()
        self.env_patch.stop()
        self.temp.cleanup()

    def pump(self):
        for _ in range(3):
            self.app.processEvents()

    def fill_config(self):
        w = self.window
        w.endpoint.setText('https://example.org/v1')
        w.model.setText('test-vision')
        w.auth.setCurrentIndex(w.auth.findData('none'))
        w.task_input.setPlainText('打开记事本，输入中文，然后检查结果。')

    def test_theme_and_navigation_preserve_draft(self):
        w = self.window
        w.task_input.setPlainText('一个较长的中文任务 ' * 100)
        for mode in ('dark', 'light', 'system'):
            w.theme_choice.setCurrentIndex(w.theme_choice.findData(mode))
            self.pump()
            self.assertEqual(w.settings.value('theme'), mode)
            self.assertIn(w.theme, ('light', 'dark'))
        for page in (1, 2, 0):
            w._navigate(page)
            self.pump()
            self.assertEqual(w.pages.currentIndex(), page)
        self.assertEqual(w.task_input.toPlainText(), '一个较长的中文任务 ' * 100)
        w._open_diagnostics(1)
        self.pump()
        self.assertFalse(w.task_area.isVisible())
        self.assertTrue(w.nav['responses'].property('selected'))

    def test_minimum_window_and_observer_reparent(self):
        w = self.window
        for size in ((1440, 900), (1024, 768), (980, 700)):
            w.resize(*size)
            w._open_diagnostics(0)
            self.pump()
            self.assertEqual(w.size().toTuple(), size)
            self.assertEqual(w.inspector.isVisible(), size[0] >= 1240)
            self.assertTrue(w.start_btn.isVisible())
            self.assertGreaterEqual(w.diagnostics.height(), 180)
            self.assertLessEqual(w.start_btn.mapTo(w, w.start_btn.rect().bottomRight()).y(), w.height())
            for tab in (1, 2):
                w._open_diagnostics(tab)
                self.pump()
                scroll = w.diagnostics.widget(tab)
                self.assertEqual(scroll.horizontalScrollBar().maximum(), 0)
        w._navigate(2)
        self.pump()
        self.assertTrue(w.inspector.isVisible())
        w.resize(1440, 900)
        w._navigate(0)
        self.pump()
        self.assertEqual(w.workspace_split.indexOf(w.inspector), 1)

    def test_options_and_secret(self):
        w = self.window
        w._navigate(1)
        w.api_key.setText('private-test-value')
        self.assertEqual(w.api_key.echoMode(), QLineEdit.EchoMode.Password)
        w.eye_btn.click()
        self.assertEqual(w.api_key.echoMode(), QLineEdit.EchoMode.Normal)
        w.eye_btn.click()
        self.assertEqual(w.api_key.echoMode(), QLineEdit.EchoMode.Password)
        w._navigate(0)
        w.options_btn.click()
        self.pump()
        self.assertTrue(w.options_dialog.isVisible())
        w.steps.setValue(17)
        w.options_dialog.accept()
        self.fill_config()
        self.assertEqual(w._build_config().max_steps, 17)

    def test_run_question_reply_stop_and_completion(self):
        w = self.window
        self.fill_config()
        with patch.object(main, 'AgentThread', FakeAgent), patch.object(w, '_save_preferences'):
            w.start_btn.click()
            agent = w.agent
            self.assertTrue(w.busy)
            self.assertFalse(w.task_input.isEnabled())
            self.assertFalse(w.example_buttons[0].isEnabled())
            self.assertTrue(w.stop_btn.isEnabled())
            self.assertEqual(w.locked_goal_view.toPlainText(), agent.config.task)
            agent.user_question.emit(3, '请选择接下来操作哪个窗口？')
            self.pump()
            self.assertEqual(w.diagnostics.currentIndex(), 2)
            self.assertTrue(w.reply_editor.isEnabled())
            w.reply_editor.setPlainText('选择第二个窗口，并继续原任务。')
            w.send_reply_btn.click()
            self.assertEqual(agent.replies, [(3, '选择第二个窗口，并继续原任务。')])
            self.assertIsNone(w.pending_question_step)
            agent.running = False
            agent.done.emit('success', '已完成界面状态测试')
            agent.finished.emit()
            self.pump()
            self.assertFalse(w.busy)
            self.assertTrue(w.start_btn.isEnabled())
            self.assertFalse(w.stop_btn.isEnabled())
            w.start_btn.click()
            w.stop_btn.click()
            self.pump()
            self.assertFalse(w.busy)
            self.assertTrue(w.task_input.isEnabled())

    def test_preview_scaling_and_log_scroll(self):
        w = self.window
        image = QImage(1600, 900, QImage.Format.Format_RGB32)
        image.fill(QColor('#808080'))
        buffer = QBuffer()
        buffer.open(QIODevice.OpenModeFlag.WriteOnly)
        image.save(buffer, 'PNG')
        w._on_shot(bytes(buffer.data()), 1600, 900)
        self.pump()
        pix = w.preview.pixmap()
        self.assertLessEqual(pix.width(), w.preview.width())
        self.assertLessEqual(pix.height(), w.preview.height())
        for i in range(100):
            w._append_log('info', f'第 {i} 条可滚动的测试日志')
        self.pump()
        bar = w.console.verticalScrollBar()
        bar.setValue(0)
        w._append_log('info', '新日志不能打断向上阅读')
        self.assertEqual(bar.value(), 0)
        bar.setValue(bar.maximum())
        w._append_log('info', '底部继续自动跟随')
        self.assertEqual(bar.value(), bar.maximum())


if __name__ == '__main__':
    unittest.main(verbosity=2)
