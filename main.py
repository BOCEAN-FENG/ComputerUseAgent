# -*- coding: utf-8 -*-
"""Aurora Computer Studio — Win11 desktop UI for a local Computer Use agent.

Run: python main.py
API protocol: OpenAI-compatible multimodal Chat Completions (image_url/data URLs).
"""
from __future__ import annotations

import ctypes
import os
import sys
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import Qt, QSettings, QTimer, QAbstractNativeEventFilter
from PySide6.QtGui import QFont, QIcon, QPixmap, QTextCursor, QCloseEvent
from PySide6.QtWidgets import (
    QApplication, QCheckBox, QComboBox, QFrame,
    QHBoxLayout, QLabel, QLineEdit, QMainWindow, QMenu, QMessageBox,
    QPlainTextEdit, QPushButton, QScrollArea, QSizePolicy, QSpinBox,
    QSystemTrayIcon, QVBoxLayout, QWidget,
)

import engine
from worker import AgentThread, RunConfig, VisionTestThread

APP_DIR = Path(__file__).resolve().parent
ICON = APP_DIR / 'assets' / 'app.ico'

COLORS = {
    'bg': '#090E19', 'panel': '#121C2D', 'panel2': '#172336',
    'stroke': '#26354B', 'text': '#F1F5FF', 'muted': '#8294AD',
    'purple': '#A28CFF', 'mint': '#51DEC4', 'danger': '#FF7888',
}

QSS = """
QWidget { color: #EDF3FF; background: transparent; font-family: 'Segoe UI', 'Microsoft YaHei UI', sans-serif; font-size: 13px; }
QMainWindow, QWidget#root { background-color: #090E19; }
QFrame#sidebar { background-color: #0C1422; border-right: 1px solid #202F44; }
QFrame#dock { background-color: #101B2D; border-top: 1px solid #2A3950; }
QFrame#panel, QFrame#metric { background-color: #111D2E; border: 1px solid #27364B; border-radius: 17px; }
QFrame#softpanel { background-color: #162338; border: 1px solid #273A51; border-radius: 13px; }
QFrame#previewInner { background-color: #090F1D; border: 1px dashed #314159; border-radius: 12px; }
QFrame#softline { background-color: #24344B; max-height: 1px; min-height: 1px; }
QLabel#brandmark { background: qlineargradient(x1:0,y1:0,x2:1,y2:1,stop:0 #B29FFF,stop:1 #6650D9); color: #FFF; border-radius: 14px; font-size: 23px; font-weight: 800; }
QLabel#brandname { font-size: 19px; color: #F4F1FF; font-weight: 800; letter-spacing: 1.6px; }
QLabel#sidecaption { color: #68809C; font-size: 10px; font-weight: 700; letter-spacing: 1.5px; }
QLabel#headline { font-size: 29px; color: #F5F7FF; font-weight: 800; }
QLabel#subtitle { font-size: 12px; color: #8294AD; }
QLabel#kicker { color: #A28CFF; font-size: 11px; font-weight: 800; letter-spacing: 1.6px; }
QLabel#sectitle { color: #F0F5FF; font-size: 15px; font-weight: 800; }
QLabel#tiny { color: #91A3BD; font-size: 11px; }
QLabel#fieldlabel { color: #C9D5E6; font-size: 12px; font-weight: 600; }
QLabel#value { color: #F2F5FF; font-size: 20px; font-weight: 800; }
QLabel#muted { color: #8495AE; font-size: 12px; }
QLabel#accent { color: #B5A7FF; font-size: 12px; font-weight: 700; }
QLabel#good { color: #54DEC5; font-size: 12px; font-weight: 700; }
QLabel#warning { color: #FEBF74; font-size: 12px; }
QLabel#callout { color: #A5B6CD; font-size: 11px; }
QPushButton { border: 1px solid #2E4058; background: #1B2A40; color: #E8EFFF; border-radius: 10px; padding: 9px 14px; font-weight: 650; }
QPushButton:hover { background: #273A55; border-color: #53688B; }
QPushButton:pressed { background: #29395B; }
QPushButton:disabled { color: #60718C; background-color: #142135; border-color: #223047; }
QPushButton#primary { color: #0E1027; font-size: 14px; font-weight: 900; border: 0; border-radius: 11px; padding: 13px 16px; background: qlineargradient(x1:0,y1:0,x2:1,y2:1,stop:0 #B6A4FF,stop:1 #7C9FFB); }
QPushButton#primary:hover { background: #C6B9FF; }
QPushButton#stop { background-color: #3D2335; border: 1px solid #92475C; color: #FFACB8; font-size: 13px; padding: 13px 14px; }
QPushButton#stop:hover { background-color: #543048; }
QPushButton#outline { color: #C5B8FF; background: #232A45; border: 1px solid #514D7B; }
QPushButton#outline:hover { background: #2B3555; }
QPushButton#nav { text-align: left; color: #899BB5; background: transparent; padding: 14px 16px; border: 0; font-size: 13px; }
QPushButton#nav:hover { color: #FFFFFF; background: #19243A; }
QPushButton#navActive { text-align: left; color: #CFC5FF; background: #211E3D; border: 1px solid #36325B; border-radius: 11px; padding: 13px 16px; font-size: 13px; }
QPushButton#chip { background-color: #1B293C; border-color: #304059; font-size: 11px; padding: 7px 12px; color: #A7BDD8; }
QPushButton#eye { padding: 6px; min-width: 34px; background: transparent; border: 0px; color: #ABB8CB; }
QLineEdit, QPlainTextEdit, QComboBox, QSpinBox { border: 1px solid #34435C; background-color: #0C1626; border-radius: 10px; color: #F0F5FF; padding: 9px 12px; selection-background-color: #6756A9; }
QLineEdit:focus, QPlainTextEdit:focus, QComboBox:focus, QSpinBox:focus { border-color: #8C83E6; background-color: #0E192C; }
QLineEdit:disabled, QPlainTextEdit:disabled, QComboBox:disabled { color: #70819A; }
QLineEdit { min-height: 23px; }
QLineEdit::placeholder, QPlainTextEdit::placeholder { color: #63738A; }
QPlainTextEdit#task { font-size: 13px; line-height: 1.5; padding: 13px; }
QPlainTextEdit#console { background: #0A1322; border: 0px; border-radius: 10px; font-family: 'Cascadia Code','Consolas',monospace; color: #B7D1E0; font-size: 11px; padding: 10px; }
QComboBox::drop-down { width: 28px; border: 0px; }
QComboBox QAbstractItemView { color: #EAF0FF; background: #111D2F; selection-background-color: #493F83; }
QSpinBox { padding-right: 4px; }
QCheckBox { color: #A7B7CC; font-size: 12px; spacing: 8px; }
QCheckBox::indicator { width: 15px; height: 15px; border: 1px solid #566584; border-radius: 4px; background: #101D2E; }
QCheckBox::indicator:checked { border: 1px solid #A18FFF; background: #9181E9; }
QScrollArea { border: none; background: transparent; }
QScrollBar:vertical { width: 9px; background: transparent; }
QScrollBar::handle:vertical { background: #30415A; border-radius: 4px; min-height: 22px; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0px; }
QScrollBar:horizontal { height: 8px; background: transparent; }
QScrollBar::handle:horizontal { background: #30415A; border-radius: 4px; }
QToolTip { background: #19263B; color: #DCE9FD; border: 1px solid #4E6481; padding: 7px; }
"""


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
    outer.setContentsMargins(20, 17, 20, 18)
    outer.setSpacing(13)
    top = QHBoxLayout()
    top.addWidget(label(eyebrow, 'kicker'))
    top.addStretch()
    outer.addLayout(top)
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


class Studio(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle('Aurora · Computer Use Studio')
        if ICON.exists():
            self.setWindowIcon(QIcon(str(ICON)))
        self.resize(1370, 880)
        self.setMinimumSize(1090, 760)
        self.settings = QSettings('AuroraStudio', 'ComputerUse')
        self.agent: AgentThread | None = None
        self.test_thread: VisionTestThread | None = None
        self.pending_quit = False
        self.current_pixmap: QPixmap | None = None
        self.busy = False
        self.step_count = 0
        self.log_plain = []
        self._make_ui()
        self._make_tray()
        self._load_preferences()
        self._set_status('idle', '待命中')
        QTimer.singleShot(0, self._dark_titlebar)

    def _dark_titlebar(self):
        if sys.platform == 'win32':
            try:
                value = ctypes.c_int(1)
                ctypes.windll.dwmapi.DwmSetWindowAttribute(int(self.winId()), 20, ctypes.byref(value), 4)
            except Exception:
                pass

    def _make_ui(self):
        root = QWidget()
        root.setObjectName('root')
        self.setCentralWidget(root)
        base = QHBoxLayout(root)
        base.setContentsMargins(0, 0, 0, 0)
        base.setSpacing(0)
        base.addWidget(self._make_sidebar())

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        inner = QWidget()
        self.main_body = QVBoxLayout(inner)
        self.main_body.setContentsMargins(29, 27, 29, 24)
        self.main_body.setSpacing(22)
        self.main_body.addLayout(self._make_header())
        self.main_body.addLayout(self._make_metrics())

        columns = QHBoxLayout()
        columns.setSpacing(18)
        left = QVBoxLayout()
        left.setSpacing(18)
        left.addWidget(self._make_connection())
        left.addWidget(self._make_task())
        left.addStretch()
        right = QVBoxLayout()
        right.setSpacing(18)
        right.addWidget(self._make_preview())
        right.addWidget(self._make_trace())
        right.addStretch()
        columns.addLayout(left, 11)
        columns.addLayout(right, 10)
        self.main_body.addLayout(columns, 1)
        self.main_body.addWidget(label('LOCAL EXECUTION   •   屏幕截图会发送至你指定的第三方 API   •   建议在隔离桌面中使用', 'sidecaption'))
        scroll.setWidget(inner)
        right_shell = QWidget()
        right_shell.setObjectName('root')
        right_v = QVBoxLayout(right_shell)
        right_v.setContentsMargins(0, 0, 0, 0)
        right_v.setSpacing(0)
        right_v.addWidget(scroll, 1)
        right_v.addWidget(self._make_action_dock())
        base.addWidget(right_shell, 1)

    def _make_sidebar(self):
        side = QFrame()
        side.setObjectName('sidebar')
        side.setFixedWidth(220)
        v = QVBoxLayout(side)
        v.setContentsMargins(18, 27, 18, 24)
        v.setSpacing(0)
        brand = QHBoxLayout()
        mark = label('✦', 'brandmark')
        mark.setAlignment(Qt.AlignmentFlag.AlignCenter)
        mark.setFixedSize(46, 46)
        brand.addWidget(mark)
        brand_labels = QVBoxLayout()
        brand_labels.setSpacing(1)
        brand_labels.addWidget(label('AURORA', 'brandname'))
        brand_labels.addWidget(label('COMPUTER STUDIO', 'sidecaption'))
        brand.addLayout(brand_labels)
        v.addLayout(brand)
        v.addSpacing(50)
        v.addWidget(label('WORKSPACE', 'sidecaption'))
        v.addSpacing(12)
        work = QPushButton('  ◈    任务工作台')
        work.setObjectName('navActive')
        work.clicked.connect(self._go_top)
        v.addWidget(work)
        v.addSpacing(9)
        guide = QPushButton('  ◷    快速使用指南')
        guide.setObjectName('nav')
        guide.clicked.connect(self._show_guide)
        v.addWidget(guide)
        v.addSpacing(6)
        sample = QPushButton('  ◫    复制日志')
        sample.setObjectName('nav')
        sample.clicked.connect(self._copy_logs)
        v.addWidget(sample)
        v.addStretch()
        v.addWidget(label('SYSTEM / LOCAL HOST', 'sidecaption'))
        v.addSpacing(11)
        sys_card = QFrame()
        sys_card.setObjectName('softpanel')
        cv = QVBoxLayout(sys_card)
        cv.setContentsMargins(14, 14, 14, 14)
        cv.setSpacing(6)
        cv.addWidget(label('●  自动执行已就绪', 'good'))
        cv.addWidget(label('鼠标移至屏幕左上角紧急停止。也可使用系统托盘菜单停止。', 'tiny', True))
        v.addWidget(sys_card)
        v.addSpacing(15)
        v.addWidget(label('AURORA  ·  v1.0  /  WINDOWS 11', 'sidecaption'))
        return side

    def _make_header(self):
        h = QHBoxLayout()
        left = QVBoxLayout()
        left.setSpacing(6)
        left.addWidget(label('AI DESKTOP AUTOMATION  /  YOUR WORKSPACE', 'kicker'))
        left.addWidget(label('让 AI 替你操作电脑', 'headline'))
        left.addWidget(label('连接视觉模型，描述任务，然后交给 Aurora。你可以随时中止。', 'subtitle'))
        h.addLayout(left)
        h.addStretch()
        badge = QFrame()
        badge.setObjectName('softpanel')
        badge_h = QHBoxLayout(badge)
        badge_h.setContentsMargins(15, 10, 15, 10)
        badge_h.addWidget(label('◉  WINDOWS 11  ·  LOCAL', 'good'))
        h.addWidget(badge)
        return h

    def _metric(self, eyebrow, value, detail):
        card = QFrame()
        card.setObjectName('metric')
        v = QVBoxLayout(card)
        v.setContentsMargins(17, 12, 17, 13)
        v.setSpacing(4)
        v.addWidget(label(eyebrow, 'sidecaption'))
        number = label(value, 'value')
        v.addWidget(number)
        v.addWidget(label(detail, 'tiny'))
        return card, number

    def _make_metrics(self):
        row = QHBoxLayout()
        row.setSpacing(14)
        a, self.connection_metric = self._metric('API CONNECTION', '未验证', '等待连接视觉模型')
        b, self.task_metric = self._metric('AGENT STATUS', '待命中', '准备运行任务')
        c, self.step_metric = self._metric('ACTION COUNT', '00 / 25', '自动执行 · 可随时停止')
        for item in (a, b, c):
            row.addWidget(item)
        return row

    def _input_with_label(self, layout, title, placeholder='', password=False):
        layout.addWidget(label(title, 'fieldlabel'))
        edit = QLineEdit()
        edit.setPlaceholderText(placeholder)
        if password:
            edit.setEchoMode(QLineEdit.EchoMode.Password)
        layout.addWidget(edit)
        return edit

    def _make_connection(self):
        f = QVBoxLayout()
        f.setSpacing(10)
        self.endpoint = self._input_with_label(f, 'API 端点 / Base URL', 'https://your-provider.com/v1')
        f.addWidget(label('支持 /v1 或完整 /chat/completions 路径', 'tiny'))
        self.model = self._input_with_label(f, '视觉模型名称', '例如：your-vision-model')
        f.addWidget(label('API 密钥', 'fieldlabel'))
        secret = QHBoxLayout()
        secret.setSpacing(5)
        self.api_key = QLineEdit()
        self.api_key.setEchoMode(QLineEdit.EchoMode.Password)
        self.api_key.setPlaceholderText('sk-••••••••••••••••••••')
        secret.addWidget(self.api_key, 1)
        eye = QPushButton('◉')
        eye.setToolTip('显示或隐藏 API Key')
        eye.setObjectName('eye')
        eye.clicked.connect(self._toggle_secret)
        secret.addWidget(eye)
        f.addLayout(secret)
        minor = QHBoxLayout()
        minor.addWidget(label('鉴权方式', 'fieldlabel'))
        self.auth = QComboBox()
        self.auth.addItem('Bearer Token', 'bearer')
        self.auth.addItem('x-api-key', 'x-api-key')
        self.auth.addItem('无鉴权 / 本地模型', 'none')
        self.auth.setMaximumWidth(210)
        minor.addWidget(self.auth)
        f.addLayout(minor)
        opts = QHBoxLayout()
        self.remember = QCheckBox('使用 Windows 凭据管理器记住密钥')
        self.remember.setToolTip('密钥不保存到配置文件；勾选时使用系统凭据保险库（keyring）。')
        opts.addWidget(self.remember)
        f.addLayout(opts)
        buttons = QHBoxLayout()
        self.check_btn = QPushButton('◎  测试连接 / 识图')
        self.check_btn.setObjectName('outline')
        self.check_btn.clicked.connect(self._check_connection)
        buttons.addWidget(self.check_btn)
        self.connection_info = label('密钥默认只保存在本次运行的内存中', 'tiny', True)
        buttons.addWidget(self.connection_info, 1)
        f.addLayout(buttons)
        return panel_layout('连接你的 AI 模型', '01  /  MODEL CONNECTION', f)

    def _make_task(self):
        v = QVBoxLayout()
        v.setSpacing(11)
        v.addWidget(label('告诉 Agent 你想做什么', 'fieldlabel'))
        self.task_input = QPlainTextEdit()
        self.task_input.setObjectName('task')
        self.task_input.setFixedHeight(114)
        self.task_input.setPlaceholderText('例如：打开记事本，输入「你好，我是 Aurora」，然后检查文本是否正确。')
        v.addWidget(self.task_input)
        chiprow = QHBoxLayout()
        chiprow.setSpacing(7)
        for text, task in [
            ('✦  记事本演示', '打开记事本，输入「你好，我是 Aurora Computer Use」，然后检查文字是否正确。不要保存文件。'),
            ('⌘  浏览器演示', '打开浏览器，访问 example.com，并告诉我页面标题。不要提交任何表单。'),
        ]:
            btn = QPushButton(text)
            btn.setObjectName('chip')
            btn.clicked.connect(lambda checked=False, txt=task: self.task_input.setPlainText(txt))
            chiprow.addWidget(btn)
        chiprow.addStretch()
        v.addLayout(chiprow)
        options = QHBoxLayout()
        options.setSpacing(9)
        options.addWidget(label('最多步骤', 'fieldlabel'))
        self.steps = QSpinBox()
        self.steps.setRange(1, 100)
        self.steps.setValue(25)
        self.steps.setFixedWidth(70)
        options.addWidget(self.steps)
        options.addSpacing(8)
        options.addWidget(label('开始延迟', 'fieldlabel'))
        self.delay = QSpinBox()
        self.delay.setRange(0, 30)
        self.delay.setSuffix(' 秒')
        self.delay.setValue(3)
        self.delay.setFixedWidth(80)
        options.addWidget(self.delay)
        options.addStretch()
        v.addLayout(options)
        self.vision_check = QCheckBox('任务启动时先验证模型能看懂图片')
        self.vision_check.setChecked(True)
        v.addWidget(self.vision_check)
        v.addWidget(label('点击窗口底部的「启动自动任务」即可开始，无需逐步审批。', 'tiny', True))
        return panel_layout('创建自动化任务', '02  /  TASK COMPOSER', v)

    def _make_action_dock(self):
        dock = QFrame()
        dock.setObjectName('dock')
        h = QHBoxLayout(dock)
        h.setContentsMargins(26, 13, 29, 13)
        h.setSpacing(12)
        v = QVBoxLayout()
        v.setSpacing(2)
        v.addWidget(label('✦  AUTO PILOT', 'accent'))
        v.addWidget(label('自动最小化 · 后台运行 · 可随时中止', 'tiny'))
        h.addLayout(v)
        h.addStretch()
        self.stop_btn = QPushButton('■  停止任务')
        self.stop_btn.setObjectName('stop')
        self.stop_btn.setMinimumWidth(132)
        self.stop_btn.setEnabled(False)
        self.stop_btn.clicked.connect(self.stop_task)
        h.addWidget(self.stop_btn)
        self.start_btn = QPushButton('✦   启动自动任务   →')
        self.start_btn.setObjectName('primary')
        self.start_btn.setMinimumWidth(190)
        self.start_btn.clicked.connect(self.start_task)
        h.addWidget(self.start_btn)
        return dock

    def _make_preview(self):
        v = QVBoxLayout()
        v.setSpacing(12)
        inner = QFrame()
        inner.setObjectName('previewInner')
        inner.setMinimumHeight(228)
        inner_v = QVBoxLayout(inner)
        inner_v.setContentsMargins(12, 12, 12, 12)
        self.preview = QLabel('')
        self.preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview.setMinimumHeight(192)
        self.preview.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.preview.setText('◉\n\n桌面观察画面将在这里显示\n等待任务开始…')
        self.preview.setStyleSheet('color: #607992; font-size: 12px; line-height: 180%;')
        inner_v.addWidget(self.preview, 1)
        v.addWidget(inner)
        foot = QHBoxLayout()
        self.preview_info = label('◌  NO SIGNAL', 'sidecaption')
        foot.addWidget(self.preview_info)
        foot.addStretch()
        foot.addWidget(label('JPEG  ·  VISION INPUT', 'sidecaption'))
        v.addLayout(foot)
        return panel_layout('实时屏幕观察', '03  /  LIVE OBSERVATION', v)

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
        return panel_layout('Execution Trace', '04  /  ACTIVITY LOG', v)

    def _make_tray(self):
        self.tray = QSystemTrayIcon(QIcon(str(ICON)) if ICON.exists() else self.windowIcon(), self)
        self.tray.setToolTip('Aurora · Computer Use Studio')
        menu = QMenu()
        open_action = menu.addAction('打开 Aurora')
        open_action.triggered.connect(self._restore)
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

    def _show_guide(self):
        QMessageBox.information(self, 'Aurora 使用指南',
            '1. 输入 OpenAI 兼容的视觉模型 API 地址、模型 ID 与密钥。\n'
            '2. 点击“测试连接 / 识图”确认模型收到图片。\n'
            '3. 输入具体任务，点击“启动自动任务”。\n'
            '4. 应用自动最小化，后台循环执行鼠标键盘动作。\n'
            '5. 任务结束后自动恢复主窗口，查看日志与截图。\n\n'
            '停止方式：托盘菜单 → 停止任务；或把鼠标移到主屏幕左上角。\n'
            '如果系统注册成功，也可按 Ctrl+Shift+F12。\n\n'
            '安全提示：第三方 API 会收到屏幕截图；仅在测试环境使用。'
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
        self.steps.setValue(int(s.value('steps', 25)))
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
        self.check_btn.setText('◌  验证中…')
        self.connection_metric.setText('连接中…')
        self._append_log('info', f'正在验证连接 · 模型 {config.model}')
        self.test_thread = VisionTestThread(config)
        self.test_thread.result.connect(self._on_test_result)
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
        self.check_btn.setText('◎  测试连接 / 识图')
        self.check_btn.setEnabled(not self.busy)
        self.test_thread = None

    def start_task(self):
        if self.busy or (self.test_thread and self.test_thread.isRunning()):
            return
        try:
            config = self._build_config()
        except ValueError as exc:
            QMessageBox.warning(self, '无法开始任务', str(exc))
            return
        self._save_preferences()
        self.step_count = 0
        self.step_metric.setText(f'00 / {config.max_steps:02d}')
        self._append_log('info', '────────────────────────────────────')
        self._append_log('ok', f'启动任务 · {config.model}')
        self._append_log('info', '执行窗口即将最小化；请勿在任务期间手动干扰鼠标键盘')
        self.busy = True
        self._set_inputs_enabled(False)
        self._set_status('running', '准备启动')
        self.agent = AgentThread(config)
        self.agent.log_line.connect(self._append_log)
        self.agent.activity.connect(self._on_activity)
        self.agent.shot.connect(self._on_shot)
        self.agent.state.connect(lambda title: self._set_status('running', title))
        self.agent.done.connect(self._on_task_done)
        self.agent.finished.connect(self._agent_finished)
        self.agent.start()
        # Hide our own GUI so that screenshots won't show/control the Aurora window.
        QTimer.singleShot(350, lambda: self.showMinimized() if self.busy else None)

    def stop_task(self):
        if self.agent and self.agent.isRunning():
            self.agent.request_stop()
            self._set_status('running', '正在停止…')
            self._append_log('warn', '停止请求已发送；当前 API 请求完成/超时后，不会执行其返回动作')

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
            self.preview_info.setText(f'●  LIVE  ·  {width} × {height}')

    def _show_preview(self):
        if self.current_pixmap and not self.current_pixmap.isNull():
            size = self.preview.size()
            scaled = self.current_pixmap.scaled(max(1, size.width() - 4), max(1, size.height() - 4),
                        Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            self.preview.setPixmap(scaled)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self.current_pixmap:
            QTimer.singleShot(0, self._show_preview)

    def _on_task_done(self, status, summary):
        labels = {'success': ('完成', 'ok'), 'stop': ('已停止', 'warn'),
                  'blocked': ('保护性停止', 'warn'), 'limit': ('达到上限', 'warn'),
                  'error': ('运行异常', 'warn')}
        human, level = labels.get(status, (status, 'info'))
        self._append_log(level, f'{human} · {summary}')
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
        self.tray_stop.setEnabled(flag == 'running')
        self.stop_btn.setEnabled(flag == 'running')
        self.start_btn.setEnabled(flag != 'running')

    def _set_inputs_enabled(self, on):
        for widget in (self.endpoint, self.model, self.api_key, self.auth,
                       self.steps, self.delay, self.vision_check,
                       self.task_input, self.remember):
            widget.setEnabled(on)
        self.check_btn.setEnabled(on)

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
            self.console.appendPlainText(line)
            self.console.moveCursor(QTextCursor.MoveOperation.End)

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
    app.setStyleSheet(QSS)
    if ICON.exists():
        app.setWindowIcon(QIcon(str(ICON)))
    font = QFont('Segoe UI', 10)
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
