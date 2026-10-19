# -*- coding: utf-8 -*-
"""Aurora Computer Studio — Win11 desktop UI for a local Computer Use agent.

Run: python main.py
API protocol: OpenAI-compatible multimodal Chat Completions (image_url/data URLs).
"""
from __future__ import annotations

import ctypes
import json
import os
import sys
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import Qt, QSettings, QTimer, QAbstractNativeEventFilter, QUrl
from PySide6.QtGui import QFont, QIcon, QPixmap, QTextCursor, QCloseEvent, QDesktopServices
from PySide6.QtWidgets import (
    QApplication, QCheckBox, QComboBox, QFrame,
    QHBoxLayout, QLabel, QLineEdit, QMainWindow, QMenu, QMessageBox,
    QPlainTextEdit, QPushButton, QScrollArea, QSizePolicy, QSpinBox,
    QSystemTrayIcon, QVBoxLayout, QWidget, QListWidget, QListWidgetItem, QTabWidget,
)

import engine
from response_store import list_sessions, read_records, response_directory
from worker import AgentThread, RunConfig, VisionTestThread
from studio_ui import StudioUI, scrollable

APP_DIR = Path(__file__).resolve().parent
ICON = APP_DIR / 'assets' / 'app.ico'


def label(text: str, name: str = 'muted', wrap: bool = False) -> QLabel:
    w = QLabel(text)
    w.setObjectName(name)
    w.setWordWrap(wrap)
    return w


def panel_layout(title: str, eyebrow: str, layout: QVBoxLayout) -> QFrame:
    frame = QFrame()
    frame.setObjectName('panel')
    frame.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
    outer = QVBoxLayout(frame)
    outer.setContentsMargins(0, 14, 0, 12)
    outer.setSpacing(12)
    if title:
        outer.addWidget(label(title, 'sectitle'))
    outer.addLayout(layout)
    return frame


class GlobalStopFilter(QAbstractNativeEventFilter):
    """Optional Windows Ctrl+Shift+F12 emergency stop when RegisterHotKey succeeds."""
    HOTKEY_ID = 0xAAB1

    def __init__(self, window):
        super().__init__()
        self.window = window
        self.registered = False
        if sys.platform == 'win32':
            try:
                self.registered = bool(ctypes.windll.user32.RegisterHotKey(None, self.HOTKEY_ID, 0x2 | 0x4, 0x7B))
            except Exception:
                pass

    def nativeEventFilter(self, event_type, message):
        if sys.platform == 'win32':
            try:
                import ctypes.wintypes
                msg = ctypes.wintypes.MSG.from_address(int(message))
                if msg.message == 0x0312 and msg.wParam == self.HOTKEY_ID:
                    self.window.stop_task()
                    return True, 0
            except Exception:
                pass
        return False, 0

    def release(self):
        if self.registered and sys.platform == 'win32':
            try:
                ctypes.windll.user32.UnregisterHotKey(None, self.HOTKEY_ID)
            except Exception:
                pass


class Studio(StudioUI, QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle('Aurora · Computer Use Studio')
        if ICON.exists():
            self.setWindowIcon(QIcon(str(ICON)))
        self.resize(1440, 900)
        self.setMinimumSize(980, 700)
        self.settings = QSettings('AuroraStudio', 'ComputerUse')
        self.agent: AgentThread | None = None
        self.test_thread: VisionTestThread | None = None
        self.pending_quit = False
        self.current_pixmap: QPixmap | None = None
        self.busy = False
        self.step_count = 0
        self.log_plain = []
        self.response_records = []
        self.response_session = None
        self.pending_question_step: int | None = None
        self._make_ui()
        self._make_tray()
        self._load_preferences()
        self._set_status('idle', '待命中')
        QTimer.singleShot(0, self._dark_titlebar)

    def _dark_titlebar(self):
        if sys.platform == 'win32':
            try:
                value = ctypes.c_int(1 if getattr(self, 'theme', 'light') == 'dark' else 0)
                ctypes.windll.dwmapi.DwmSetWindowAttribute(int(self.winId()), 20, ctypes.byref(value), 4)
            except Exception:
                pass


    def _make_diagnostics(self):
        self.diagnostics = QTabWidget()
        self.diagnostics.setDocumentMode(True)
        self.diagnostics.addTab(scrollable(self._make_trace()), '执行日志')
        self.diagnostics.addTab(scrollable(self._make_api_responses()), 'API 响应')
        self.diagnostics.addTab(scrollable(self._make_question_panel()), '用户回复')
        return self.diagnostics

    def _make_question_panel(self):
        v = QVBoxLayout()
        v.setSpacing(10)
        self.question_status = label('当前没有需要回复的问题', 'good', True)
        v.addWidget(self.question_status)
        v.addWidget(label('Agent 的问题', 'fieldlabel'))
        self.question_view = QPlainTextEdit()
        self.question_view.setObjectName('responseDetail')
        self.question_view.setReadOnly(True)
        self.question_view.setPlaceholderText('需要确认时，模型的问题将完整显示在这里…')
        self.question_view.setFixedHeight(110)
        self.question_view.setAccessibleName('Agent 的问题')
        v.addWidget(self.question_view)
        v.addWidget(label('你的回复', 'fieldlabel'))
        self.reply_editor = QPlainTextEdit()
        self.reply_editor.setObjectName('reply')
        self.reply_editor.setPlaceholderText('例如：选择第 2 项，请返回首页，找出列表里的第三个视频，然后继续原来的任务。')
        self.reply_editor.setFixedHeight(100)
        self.reply_editor.setAccessibleName('你的回复')
        self.reply_editor.setEnabled(False)
        v.addWidget(self.reply_editor)
        actions = QHBoxLayout()
        self.send_reply_btn = QPushButton('发送回复并继续任务')
        self.send_reply_btn.setObjectName('primary')
        self.send_reply_btn.setEnabled(False)
        self.send_reply_btn.clicked.connect(self._submit_user_reply)
        actions.addWidget(self.send_reply_btn, 1)
        self.stop_question_btn = QPushButton('停止任务')
        self.stop_question_btn.setObjectName('stop')
        self.stop_question_btn.setEnabled(False)
        self.stop_question_btn.clicked.connect(self.stop_task)
        actions.addWidget(self.stop_question_btn)
        v.addLayout(actions)
        self.reply_tip = label('提交后 Aurora 会自动最小化，然后继续观察之前的桌面。', 'tiny', True)
        v.addWidget(self.reply_tip)
        panel = panel_layout('', '06  /  HUMAN-IN-THE-LOOP', v)
        panel.layout().addStretch()
        return panel

    def _make_api_responses(self):
        v = QVBoxLayout()
        v.setSpacing(9)
        v.addWidget(label('模型每次返回的 HTTP 正文都会保存；解析失败也可查看原文。', 'tiny', True))

        session_row = QHBoxLayout()
        session_row.addWidget(label('历史会话', 'fieldlabel'))
        self.response_sessions = QComboBox()
        self.response_sessions.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.response_sessions.currentIndexChanged.connect(self._on_response_session_changed)
        session_row.addWidget(self.response_sessions, 1)
        folder = QPushButton('打开目录')
        folder.setObjectName('chip')
        folder.clicked.connect(self._open_response_folder)
        session_row.addWidget(folder)
        v.addLayout(session_row)

        self.response_items = QListWidget()
        self.response_items.setMinimumHeight(95)
        self.response_items.setMaximumHeight(125)
        self.response_items.currentItemChanged.connect(self._render_response)
        v.addWidget(self.response_items)

        actions = QHBoxLayout()
        self.response_summary = label('暂无响应记录', 'tiny', True)
        actions.addWidget(self.response_summary, 1)
        self.response_mode = QComboBox()
        self.response_mode.addItem('模型输出', 'content')
        self.response_mode.addItem('原始 API 响应', 'raw')
        self.response_mode.addItem('解析信息', 'meta')
        self.response_mode.currentIndexChanged.connect(self._render_response)
        self.response_mode.setMinimumWidth(130)
        actions.addWidget(self.response_mode)
        copy = QPushButton('复制响应')
        copy.setObjectName('chip')
        copy.clicked.connect(self._copy_response)
        actions.addWidget(copy)
        v.addLayout(actions)

        self.response_detail = QPlainTextEdit()
        self.response_detail.setObjectName('responseDetail')
        self.response_detail.setReadOnly(True)
        self.response_detail.setPlaceholderText('任务开始后，这里会显示每次请求返回的模型原文…')
        self.response_detail.setMinimumHeight(180)
        v.addWidget(self.response_detail)
        v.addWidget(label('本地自动保存为 JSONL；响应可能包含隐私信息，请勿公开分享。API Key 会尝试按原文遮蔽。', 'tiny', True))
        panel = panel_layout('API 响应查看器', '05  /  RAW RESPONSE INSPECTOR', v)
        self._refresh_response_sessions()
        return panel

    def _refresh_response_sessions(self, select_path=None):
        current = str(select_path) if select_path else self.response_sessions.currentData()
        self.response_sessions.blockSignals(True)
        self.response_sessions.clear()
        sessions = list_sessions()
        for path in sessions[:150]:
            self.response_sessions.addItem(path.stem.removeprefix('api-'), str(path))
        self.response_sessions.blockSignals(False)
        if not sessions:
            self.response_records = []
            self.response_items.clear()
            self.response_detail.clear()
            self.response_summary.setText('暂无响应记录')
            return
        idx = self.response_sessions.findData(current) if current else -1
        self.response_sessions.setCurrentIndex(max(idx, 0))
        self._on_response_session_changed()

    def _on_response_session_changed(self, *args):
        raw_path = self.response_sessions.currentData()
        self.response_items.clear()
        self.response_detail.clear()
        self.response_records = []
        if not raw_path:
            return
        try:
            self.response_records = read_records(Path(raw_path))
        except (OSError, ValueError) as exc:
            self.response_summary.setText('读取失败：' + str(exc)[:90])
            return
        for index, record in enumerate(self.response_records):
            stamp = str(record.get('time', ''))[11:19]
            phase = '识图测试' if record.get('phase') == 'vision-check' else f'步骤 {record.get("step") or "?"}'
            status = '✓' if record.get('parse_status') == 'ok' else '!'
            compat = ' · DSML 已兼容' if record.get('parse_mode') == 'dsml_compat' else ''
            item = QListWidgetItem(f'{status}  {stamp}  ·  {phase}  ·  HTTP {record.get("http_status", "?")}{compat}')
            item.setData(Qt.ItemDataRole.UserRole, index)
            self.response_items.addItem(item)
        self.response_summary.setText(f'共 {len(self.response_records)} 条 API 响应')
        if self.response_records:
            self.response_items.setCurrentRow(len(self.response_records) - 1)

    def _render_response(self, *args):
        item = self.response_items.currentItem()
        if item is None:
            self.response_detail.clear()
            return
        index = item.data(Qt.ItemDataRole.UserRole)
        if not isinstance(index, int) or index >= len(self.response_records):
            return
        record = self.response_records[index]
        mode = self.response_mode.currentData()
        if mode == 'content':
            text = record.get('model_content') or '(该响应中没有提取到文本 content；请切换至「原始 API 响应」)'
        elif mode == 'raw':
            raw = record.get('raw_body') or ''
            try:
                text = json.dumps(json.loads(raw), ensure_ascii=False, indent=2)
            except (ValueError, TypeError):
                text = raw or '(空响应)'
        else:
            text = json.dumps({key: value for key, value in record.items()
                               if key not in ('raw_body', 'model_content', 'session_path')},
                              ensure_ascii=False, indent=2)
        if record.get('response_truncated') and mode == 'raw':
            text += '\n\n[警告：响应超过单条 200 万字符存储上限，已截断]'
        self.response_detail.setPlainText(str(text))
        self.response_detail.moveCursor(QTextCursor.MoveOperation.Start)
        if record.get('parse_status') != 'ok':
            self.response_summary.setText('⚠  解析失败：' + str(record.get('parse_error') or '未知原因')[:85])
        elif record.get('parse_mode') == 'dsml_compat':
            self.response_summary.setText('✓  模型返回 DSML，已安全转换为单个动作；建议检查模型输出协议')
        else:
            self.response_summary.setText(f'✓  已记录 {len(self.response_records)} 条')

    def _on_api_response(self, record):
        # The agent thread writes the journal before emitting this signal.
        path = record.get('session_path')
        if path:
            self._refresh_response_sessions(select_path=path)
        if record.get('parse_status') != 'ok':
            self._append_log('warn', 'API 原文已保存，可在「API 响应」中检查失败步骤')

    def _copy_response(self):
        if self.response_detail.toPlainText().strip():
            QApplication.clipboard().setText(self.response_detail.toPlainText())
            self._append_log('ok', '所选 API 响应已复制到剪贴板')

    def _open_response_folder(self):
        folder = response_directory()
        folder.mkdir(parents=True, exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(folder)))

    def _make_trace(self):
        v = QVBoxLayout()
        v.setSpacing(9)
        controls = QHBoxLayout()
        controls.addWidget(label('操作日志实时记录模型动作和执行状态', 'tiny'))
        controls.addStretch()
        copy = QPushButton('复制')
        copy.setObjectName('chip')
        copy.clicked.connect(self._copy_logs)
        controls.addWidget(copy)
        clear = QPushButton('清空')
        clear.setObjectName('chip')
        clear.clicked.connect(self._clear_logs)
        controls.addWidget(clear)
        v.addLayout(controls)
        self.console = QPlainTextEdit()
        self.console.setObjectName('console')
        self.console.setReadOnly(True)
        self.console.setMinimumHeight(205)
        self.console.setMaximumBlockCount(280)
        v.addWidget(self.console)
        self._append_log('info', 'Aurora Engine 已就绪，等待连接和任务')
        v.addWidget(label('敏感输入内容不写入日志；中止任务请用托盘、停止按钮或鼠标左上角。', 'tiny', True))
        return panel_layout('', '04  /  ACTIVITY LOG', v)

    def _make_tray(self):
        self.tray = QSystemTrayIcon(QIcon(str(ICON)) if ICON.exists() else self.windowIcon(), self)
        self.tray.setToolTip('Aurora · Computer Use Studio')
        menu = QMenu()
        open_action = menu.addAction('打开 Aurora')
        open_action.triggered.connect(self._restore)
        self.tray_question = menu.addAction('✉  查看待回复的问题')
        self.tray_question.setEnabled(False)
        self.tray_question.triggered.connect(self._show_question_panel)
        self.tray_stop = menu.addAction('■  停止当前任务')
        self.tray_stop.setEnabled(False)
        self.tray_stop.triggered.connect(self.stop_task)
        menu.addSeparator()
        quit_action = menu.addAction('退出')
        quit_action.triggered.connect(self._quit_from_tray)
        self.tray.setContextMenu(menu)
        self.tray.activated.connect(self._on_tray_activated)
        if QSystemTrayIcon.isSystemTrayAvailable():
            self.tray.show()

    def _on_tray_activated(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self._restore()

    def _restore(self):
        self.showNormal()
        self.raise_()
        self.activateWindow()

    def _go_top(self):
        self._restore()
        self._navigate(0)

    def _show_question_panel(self):
        self._open_diagnostics(2)
        if self.pending_question_step is not None:
            self.reply_editor.setFocus(Qt.FocusReason.OtherFocusReason)

    def _on_user_question(self, step: int, question: str):
        if not self.busy or self.agent is None:
            return
        self.pending_question_step = step
        self.question_view.setPlainText(question)
        self.question_view.moveCursor(QTextCursor.MoveOperation.Start)
        self.reply_editor.clear()
        self.reply_editor.setEnabled(True)
        self.send_reply_btn.setEnabled(True)
        self.stop_question_btn.setEnabled(True)
        self.tray_question.setEnabled(True)
        self.question_status.setText(f'◉  已暂停 · 第 {step} 步正在等待你的回复')
        self.reply_tip.setText('输入你希望 Agent 如何继续。回复会连同任务上下文发给模型。')
        self._set_status('waiting', '等待你的回复')
        self._show_question_panel()
        if self.tray.isVisible():
            self.tray.showMessage('Aurora 需要你的确认', 'Agent 已暂停，请在“用户回复”标签中回答。',
                                  QSystemTrayIcon.MessageIcon.Information, 5000)

    def _submit_user_reply(self):
        step = self.pending_question_step
        agent = self.agent
        if step is None or agent is None or not self.busy:
            return
        answer = self.reply_editor.toPlainText().strip()
        if not answer:
            self.reply_tip.setText('请先填写回复内容。')
            self.reply_editor.setFocus(Qt.FocusReason.OtherFocusReason)
            return
        if len(answer) > 4000:
            self.reply_tip.setText('回复最多 4000 字符，请精简后发送。')
            return
        # Minimize before unblocking the worker. It also waits >=1.8s before
        # taking the next screenshot to prevent the Aurora UI occluding the desktop.
        self.showMinimized()
        if not agent.submit_reply(step, answer):
            self._restore()
            self.reply_tip.setText('发送失败：该问题已失效，或者任务已停止。')
            return
        self.pending_question_step = None
        self.reply_editor.setEnabled(False)
        self.send_reply_btn.setEnabled(False)
        self.stop_question_btn.setEnabled(False)
        self.tray_question.setEnabled(False)
        self.question_status.setText('✓  已回复，正在继续原来的任务')
        self.reply_tip.setText('已发送。应用已最小化；后续若需要确认会再次弹出。')
        self._append_log('ok', f'第 {step} 步已提交人工回复 · {len(answer)} 字符（正文不写入日志）')
        self._set_status('running', '恢复自动执行')

    def _clear_pending_question(self):
        self.pending_question_step = None
        self.reply_editor.setEnabled(False)
        self.send_reply_btn.setEnabled(False)
        self.stop_question_btn.setEnabled(False)
        self.tray_question.setEnabled(False)

    def _show_guide(self):
        QMessageBox.information(self, 'Aurora 使用指南',
            '1. 输入 OpenAI 兼容的视觉模型 API 地址、模型 ID 与密钥。\n'
            '2. 点击“测试连接 / 识图”确认模型收到图片。\n'
            '3. 输入具体任务，点击“启动自动任务”。\n'
            '4. 应用自动最小化，后台循环执行鼠标键盘动作。\n'
            '5. 任务结束后自动恢复主窗口，查看日志与截图。\n\n'
            '停止方式：托盘菜单 → 停止任务；或把鼠标移到主屏幕左上角。\n'
            '如果系统注册成功，也可按 Ctrl+Shift+F12。\n\n'
            '模型返回的原始内容保存在「API 响应」标签，并会写入本地 JSONL。\n'
            '当模型输出非 JSON 时，选择报错步骤查看完整返回。\n'
            '允许模型自动向上或向下滚动页面。\n'
            '模型返回 ask_user 时会暂停操作并自动打开“用户回复”标签。\n'
            '填写回复点击“发送回复并继续任务”，无需重新启动。\n\n'
            '安全提示：第三方 API 会收到屏幕截图，响应可能含隐私信息；仅在测试环境使用。'
        )

    def _toggle_secret(self):
        mode = self.api_key.echoMode()
        self.api_key.setEchoMode(QLineEdit.EchoMode.Normal if mode == QLineEdit.EchoMode.Password
                                  else QLineEdit.EchoMode.Password)

    def _load_preferences(self):
        s = self.settings
        self.endpoint.setText(str(s.value('endpoint', os.getenv('COMPUTER_ENDPOINT')
                                             or os.getenv('COMPUTER_BASE_URL', ''))))
        self.model.setText(str(s.value('model', os.getenv('COMPUTER_MODEL', ''))))
        auth = str(s.value('auth', os.getenv('COMPUTER_AUTH_MODE', 'bearer')))
        self.auth.setCurrentIndex(max(0, self.auth.findData(auth)))
        self.steps.setValue(int(s.value('steps', 100)))
        self.delay.setValue(int(s.value('delay', 3)))
        saved = str(s.value('rememberKey', 'false')).lower() == 'true'
        self.remember.setChecked(saved)
        if saved:
            try:
                import keyring
                self.api_key.setText(keyring.get_password('AuroraComputerStudio', 'default') or '')
            except Exception:
                self.remember.setChecked(False)
        else:
            self.api_key.setText(os.getenv('COMPUTER_API_KEY', ''))

    def _save_preferences(self):
        s = self.settings
        s.setValue('endpoint', self.endpoint.text().strip())
        s.setValue('model', self.model.text().strip())
        s.setValue('auth', self.auth.currentData())
        s.setValue('steps', self.steps.value())
        s.setValue('delay', self.delay.value())
        if self.remember.isChecked():
            try:
                import keyring
                keyring.set_password('AuroraComputerStudio', 'default', self.api_key.text())
                s.setValue('rememberKey', True)
                return
            except Exception:
                self._append_log('warn', '无法写入 Windows 凭据保险库；密钥仅保留在内存中')
                self.remember.setChecked(False)
        try:
            import keyring
            keyring.delete_password('AuroraComputerStudio', 'default')
        except Exception:
            pass
        s.setValue('rememberKey', False)

    def _build_config(self, require_task: bool = True):
        raw = self.endpoint.text().strip()
        model = self.model.text().strip()
        key = self.api_key.text().strip()
        auth = self.auth.currentData()
        task = self.task_input.toPlainText().strip()
        try:
            endpoint = engine.resolve_endpoint(raw, None)
        except ValueError as exc:
            raise ValueError('API 端点无效：' + str(exc)) from exc
        # If a Base URL was entered, append the documented Chat Completions suffix.
        # When an endpoint ends in /chat/completions, use as-is.
        if not model:
            raise ValueError('请填写视觉模型的 Model ID')
        if auth != 'none' and not key:
            raise ValueError('请填写 API Key，或选择“无鉴权 / 本地模型”')
        if not task and require_task:
            raise ValueError('请填写需要执行的任务')
        if not task:
            task = '视觉能力预检'
        return RunConfig(endpoint, key, auth, model, task, self.steps.value(),
                         self.delay.value(), 1600, self.vision_check.isChecked())

    def _check_connection(self):
        if self.busy or (self.test_thread and self.test_thread.isRunning()):
            return
        try:
            # Connection testing does not alter the user's task field.
            config = self._build_config(require_task=False)
        except ValueError as exc:
            QMessageBox.warning(self, '请检查配置', str(exc))
            return
        self._save_preferences()
        self.check_btn.setEnabled(False)
        self.check_btn.setText('验证中…')
        self.connection_metric.setText('连接中…')
        self._append_log('info', f'正在验证连接 · 模型 {config.model}')
        self.test_thread = VisionTestThread(config)
        self.test_thread.result.connect(self._on_test_result)
        self.test_thread.response_record.connect(self._on_api_response)
        self.test_thread.finished.connect(self._test_finished)
        self.test_thread.start()

    def _on_test_result(self, ok, message):
        self.connection_metric.setText('已连接' if ok else '连接失败')
        self.connection_info.setText('识图预检通过' if ok else '请检查 API 或模型')
        self.connection_info.setObjectName('good' if ok else 'warning')
        self.connection_info.style().unpolish(self.connection_info)
        self.connection_info.style().polish(self.connection_info)
        self._append_log('ok' if ok else 'warn', message)

    def _test_finished(self):
        self.check_btn.setText('测试连接 / 识图')
        self.check_btn.setEnabled(not self.busy)
        self.test_thread = None

    def start_task(self):
        if self.busy or (self.test_thread and self.test_thread.isRunning()):
            return
        try:
            config = self._build_config()
        except ValueError as exc:
            self._navigate(1 if not self.endpoint.text().strip() or not self.model.text().strip() or (self.auth.currentData() != 'none' and not self.api_key.text().strip()) else 0)
            QMessageBox.warning(self, '无法开始任务', str(exc))
            return
        self._save_preferences()
        self.step_count = 0
        self._clear_pending_question()
        self.question_view.clear()
        self.reply_editor.clear()
        self.question_status.setText('运行中 · 暂无待回复问题')
        self.step_metric.setText(f'00 / {config.max_steps:02d}')
        self.locked_goal_view.setPlainText(config.task)
        self.task_progress_view.setPlainText('已完成：暂无\n正在进行：观察桌面\n下一步：根据用户目标选择动作')
        self._append_log('info', '────────────────────────────────────')
        self._append_log('ok', f'启动任务 · {config.model}')
        self._append_log('info', '执行窗口即将最小化；请勿在任务期间手动干扰鼠标键盘')
        self.busy = True
        self._set_inputs_enabled(False)
        self._set_status('running', '准备启动')
        self.agent = AgentThread(config)
        self.agent.log_line.connect(self._append_log)
        self.agent.response_record.connect(self._on_api_response)
        self.agent.activity.connect(self._on_activity)
        self.agent.progress.connect(self._on_video_progress)
        self.agent.task_snapshot.connect(self._on_task_snapshot)
        self.agent.shot.connect(self._on_shot)
        self.agent.user_question.connect(self._on_user_question)
        self.agent.state.connect(lambda title: self._set_status(
            'waiting' if title == '等待你的回复' else 'running', title))
        self.agent.done.connect(self._on_task_done)
        self.agent.finished.connect(self._agent_finished)
        self.agent.start()
        # Hide our own GUI so that screenshots won't show/control the Aurora window.
        QTimer.singleShot(350, lambda: self.showMinimized()
                          if self.busy and self.pending_question_step is None else None)

    def stop_task(self):
        if self.agent and self.agent.isRunning():
            self.agent.request_stop()
            if self.pending_question_step is not None:
                self.question_status.setText('已中止 · 等待回复已取消')
                self._clear_pending_question()
            self._set_status('running', '正在停止…')
            self._append_log('warn', '停止请求已发送；当前 API 请求完成/超时后，不会执行其返回动作')

    def _on_video_progress(self, progress: str):
        self.task_metric.setText(progress.split(' · ', 1)[0])
        self._append_log('info', f'视频任务进度 · {progress}')

    def _on_task_snapshot(self, info: dict):
        if not isinstance(info, dict):
            return
        # Always display what the worker locked at task start, not a model-made goal.
        self.locked_goal_view.setPlainText(str(info.get('goal', '')))
        completed = info.get('completed', [])
        lines = ['已完成（模型截图观察，尚非独立验证）：']
        lines.extend('✓ ' + str(item) for item in completed) if completed else lines.append('暂无')
        lines += ['', '正在进行：' + str(info.get('current', '')),
                  '下一步：' + str(info.get('next', ''))]
        if info.get('video'):
            lines.extend(['', '程序维护的视频进度：', str(info['video'])])
        if info.get('remediation'):
            lines.extend(['', str(info['remediation'])])
        self.task_progress_view.setPlainText('\n'.join(lines))

    def _on_activity(self, step, detail):
        self.step_count = step
        max_steps = self.steps.value()
        self.step_metric.setText(f'{step:02d} / {max_steps:02d}')
        self.tray.setToolTip(f'Aurora · 第 {step}/{max_steps} 步 · {detail[:60]}')

    def _on_shot(self, data, width, height):
        pix = QPixmap()
        if pix.loadFromData(data):
            self.current_pixmap = pix
            self._show_preview()
            self.preview_info.setText(f'最近观察  ·  {width} × {height}')

    def _show_preview(self):
        if self.current_pixmap and not self.current_pixmap.isNull():
            size = self.preview.size()
            scaled = self.current_pixmap.scaled(max(1, size.width() - 4), max(1, size.height() - 4),
                        Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            self.preview.setPixmap(scaled)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._sync_observer()
        if self.current_pixmap:
            QTimer.singleShot(0, self._show_preview)

    def _on_task_done(self, status, summary):
        self._clear_pending_question()
        labels = {'success': ('完成', 'ok'), 'stop': ('已停止', 'warn'),
                  'blocked': ('保护性停止', 'warn'), 'limit': ('达到上限', 'warn'),
                  'error': ('运行异常', 'warn')}
        human, level = labels.get(status, (status, 'info'))
        self._append_log(level, f'{human} · {summary}')
        self._navigate(0)
        if status == 'error':
            self.diagnostics.setCurrentIndex(1)  # show the preserved response on failure
        self._set_status('idle', human)
        self.busy = False
        self._set_inputs_enabled(True)
        self.tray.setToolTip('Aurora · Computer Use Studio')
        self._restore()
        if self.pending_quit:
            QTimer.singleShot(200, self.close)

    def _agent_finished(self):
        if self.agent and not self.agent.isRunning():
            self.agent = None

    def _set_status(self, flag, name):
        self.task_metric.setText(name)
        active = flag in ('running', 'waiting')
        self.tray_stop.setEnabled(active)
        self.stop_btn.setEnabled(active)
        self.start_btn.setEnabled(not active)

    def _set_inputs_enabled(self, on):
        for widget in (self.endpoint, self.model, self.api_key, self.auth,
                       self.steps, self.delay, self.vision_check,
                       self.task_input, self.remember):
            widget.setEnabled(on)
        self.check_btn.setEnabled(on)
        for widget in self.example_buttons:
            widget.setEnabled(on)

    def _append_log(self, level, message):
        stamp = datetime.now().strftime('%H:%M:%S')
        icons = {'info': '·', 'ok': '✓', 'warn': '!', 'action': '→'}
        line = f'[{stamp}] {icons.get(level, "·")}  {message}'
        if not hasattr(self, 'log_plain'):
            self.log_plain = []
        self.log_plain.append(line)
        if len(self.log_plain) > 450:
            self.log_plain = self.log_plain[-450:]
        if hasattr(self, 'console'):
            bar = self.console.verticalScrollBar()
            follow = bar.value() >= bar.maximum() - 24
            before = bar.value()
            self.console.appendPlainText(line)
            bar.setValue(bar.maximum() if follow else before)

    def _copy_logs(self):
        QApplication.clipboard().setText('\n'.join(self.log_plain))
        self._append_log('ok', '日志已复制到剪贴板')

    def _clear_logs(self):
        self.log_plain.clear()
        self.console.clear()
        self._append_log('info', '日志已清空')

    def _quit_from_tray(self):
        if self.busy:
            self.pending_quit = True
            self.stop_task()
            self._append_log('info', '任务结束后将退出程序')
        else:
            QApplication.instance().quit()

    def closeEvent(self, event: QCloseEvent):
        if self.busy:
            event.ignore()
            self.hide()
            if self.tray.isVisible():
                self.tray.showMessage('Aurora 在后台运行', '任务仍在执行。右键系统托盘图标可以停止。',
                    QSystemTrayIcon.MessageIcon.Information, 2800)
        else:
            self._save_preferences()
            event.accept()


def main():
    if sys.platform == 'win32':
        try:
            engine.set_windows_dpi_awareness()
        except Exception:
            pass
    app = QApplication(sys.argv)
    app.setApplicationName('Aurora Computer Studio')
    app.setOrganizationName('AuroraStudio')
    app.setQuitOnLastWindowClosed(True)
    app.setStyle('Fusion')
    if ICON.exists():
        app.setWindowIcon(QIcon(str(ICON)))
    if sys.platform == 'win32':
        font = QFont('Segoe UI', 10)
        font.setFamilies(['Segoe UI', 'Microsoft YaHei UI', 'Microsoft YaHei'])
        app.setFont(font)
    window = Studio()
    window.show()
    stop_filter = GlobalStopFilter(window)
    if stop_filter.registered:
        app.installNativeEventFilter(stop_filter)
    app.aboutToQuit.connect(stop_filter.release)
    return app.exec()


if __name__ == '__main__':
    raise SystemExit(main())
