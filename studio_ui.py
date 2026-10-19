"""Native workspace layout; execution remains in main.py and worker.py."""
from __future__ import annotations

from pathlib import Path
from PySide6.QtCore import Qt, QSize, QEvent, QTimer
from PySide6.QtGui import QKeySequence, QShortcut, QPixmap
from PySide6.QtWidgets import (
    QApplication, QCheckBox, QComboBox, QDialog, QFrame, QHBoxLayout, QLabel, QLineEdit,
    QPlainTextEdit, QPushButton, QScrollArea, QSizePolicy, QSpinBox, QSplitter,
    QStackedWidget, QTabWidget, QVBoxLayout, QWidget,
)
from ui_theme import apply_theme, icon


def text(value, name='muted', wrap=False):
    w = QLabel(value)
    w.setObjectName(name)
    w.setWordWrap(wrap)
    return w


def scrollable(widget):
    scroll = QScrollArea()
    scroll.setWidgetResizable(True)
    scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
    scroll.setWidget(widget)
    return scroll


class StudioUI:
    def _button(self, title, callback, glyph=None, role='ghost'):
        btn = QPushButton(title)
        btn.setObjectName(role)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setAccessibleName(title)
        btn.setMinimumHeight(38)
        if glyph:
            btn.setProperty('glyph', glyph)
            btn.setIconSize(QSize(18, 18))
            if hasattr(self, 'theme_colors'):
                btn.setIcon(icon(glyph, self.theme_colors['on-action' if role == 'primary' else 'secondary']))
        btn.clicked.connect(callback)
        return btn

    def _make_ui(self):
        root = QWidget()
        root.setObjectName('root')
        self.setCentralWidget(root)
        row = QHBoxLayout(root)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(0)
        row.addWidget(self._make_sidebar())
        shell = QWidget()
        shell_v = QVBoxLayout(shell)
        shell_v.setContentsMargins(0, 0, 0, 0)
        shell_v.setSpacing(0)
        top = QFrame()
        top.setObjectName('topbar')
        top.setFixedHeight(64)
        top_h = QHBoxLayout(top)
        top_h.setContentsMargins(24, 0, 24, 0)
        self.page_title = text('任务工作台', 'pagetitle')
        top_h.addWidget(self.page_title)
        top_h.addStretch()
        self.task_metric = text('待命中', 'badge')
        self.task_metric.setAccessibleName('任务状态')
        self.task_metric.setFixedHeight(30)
        top_h.addWidget(self.task_metric)
        shell_v.addWidget(top)
        self.pages = QStackedWidget()
        self.workspace = self._make_workspace()
        self.pages.addWidget(self.workspace)
        self.pages.addWidget(self._make_settings_page())
        observer_page = QWidget()
        self.observer_host = QHBoxLayout(observer_page)
        self.observer_host.setContentsMargins(24, 24, 24, 24)
        self.pages.addWidget(observer_page)
        shell_v.addWidget(self.pages, 1)
        row.addWidget(shell, 1)
        self._apply_theme()
        QApplication.instance().styleHints().colorSchemeChanged.connect(self._system_theme_changed)
        self.run_shortcut = QShortcut(QKeySequence('Ctrl+Return'), self)
        self.run_shortcut.activated.connect(self._run_from_keyboard)
        self.diagnostics.currentChanged.connect(self._diagnostic_changed)
        self._navigate(0)

    def _make_sidebar(self):
        side = QFrame()
        side.setObjectName('sidebar')
        side.setFixedWidth(240)
        v = QVBoxLayout(side)
        v.setContentsMargins(12, 22, 12, 20)
        v.setSpacing(6)
        brand = QHBoxLayout()
        brand.setContentsMargins(12, 0, 0, 0)
        mark = text('A', 'brandmark')
        mark.setAlignment(Qt.AlignmentFlag.AlignCenter)
        mark.setFixedSize(32, 32)
        product_logo = QPixmap(str(Path(__file__).resolve().parent / 'assets' / 'app.png'))
        if not product_logo.isNull():
            mark.setObjectName('productLogo')
            mark.setPixmap(product_logo.scaled(32, 32, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
        brand.addWidget(mark)
        names = QVBoxLayout()
        names.setSpacing(0)
        names.addWidget(text('Aurora', 'brandname'))
        names.addWidget(text('Computer Studio', 'tiny'))
        brand.addLayout(names)
        brand.addStretch()
        v.addLayout(brand)
        v.addSpacing(30)
        self.nav = {}
        for key, title, glyph, callback in [
            ('workspace', '任务工作台', 'workspace', lambda: self._open_diagnostics(0)),
            ('observer', '屏幕观察', 'monitor', lambda: self._navigate(2)),
            ('responses', 'API 响应记录', 'activity', lambda: self._open_diagnostics(1)),
            ('reply', '用户回复', 'reply', self._show_question_panel),
        ]:
            btn = self._button(title, callback, glyph, 'nav')
            self.nav[key] = btn
            v.addWidget(btn)
        v.addSpacing(24)
        caption = text('配置', 'sidecaption')
        caption.setContentsMargins(12, 0, 0, 4)
        v.addWidget(caption)
        self.nav['settings'] = self._button('模型与连接', lambda: self._navigate(1), 'settings', 'nav')
        v.addWidget(self.nav['settings'])
        v.addWidget(self._button('使用指南', self._show_guide, 'help', 'nav'))
        v.addStretch()
        footer = QVBoxLayout()
        footer.setContentsMargins(12, 0, 12, 0)
        footer.setSpacing(8)
        footer.addWidget(text('外观', 'fieldlabel'))
        self.theme_choice = QComboBox()
        for title, value in [('浅色', 'light'), ('深色', 'dark'), ('跟随系统', 'system')]:
            self.theme_choice.addItem(title, value)
        self.theme_choice.setAccessibleName('外观主题')
        saved = str(self.settings.value('theme', 'light'))
        self.theme_choice.setCurrentIndex(max(0, self.theme_choice.findData(saved)))
        self.theme_choice.currentIndexChanged.connect(self._theme_changed)
        footer.addWidget(self.theme_choice)
        footer.addSpacing(14)
        footer.addWidget(text('本机执行', 'fieldlabel'))
        footer.addWidget(text('移至屏幕左上角可紧急停止', 'tiny', True))
        footer.addWidget(text('Aurora  ·  1.10', 'tiny'))
        v.addLayout(footer)
        return side

    def _make_workspace(self):
        page = QWidget()
        outer = QVBoxLayout(page)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        self.workspace_split = QSplitter(Qt.Orientation.Horizontal)
        self.workspace_split.setChildrenCollapsible(False)
        self.workspace_split.setHandleWidth(1)
        content = QWidget()
        content.setMinimumWidth(500)
        cv = QVBoxLayout(content)
        cv.setContentsMargins(24, 20, 24, 0)
        cv.setSpacing(20)
        self.task_area = self._make_task()
        cv.addWidget(self.task_area)
        self.diagnostics = self._make_diagnostics()
        cv.addWidget(self.diagnostics, 1)
        self.workspace_split.addWidget(content)
        self.inspector = self._make_inspector()
        self.inspector.setMinimumWidth(320)
        self.workspace_split.addWidget(self.inspector)
        self.workspace_split.setStretchFactor(0, 1)
        self.workspace_split.setStretchFactor(1, 0)
        self.workspace_split.setSizes([740, 350])
        outer.addWidget(self.workspace_split, 1)
        outer.addWidget(self._make_action_dock())
        return page

    def _make_task(self):
        w = QWidget()
        v = QVBoxLayout(w)
        v.setContentsMargins(0, 4, 0, 0)
        v.setSpacing(12)
        v.addWidget(text('你想让电脑做什么？', 'headline'))
        v.addWidget(text('描述目标，Aurora 会观察屏幕并操作鼠标与键盘。', 'subtitle', True))
        self.composer = QFrame()
        self.composer.setObjectName('composer')
        box = QVBoxLayout(self.composer)
        box.setContentsMargins(16, 14, 16, 12)
        box.setSpacing(6)
        self.task_input = QPlainTextEdit()
        self.task_input.setObjectName('task')
        self.task_input.setAccessibleName('任务描述')
        self.task_input.setPlaceholderText('例如：打开记事本，输入「你好，我是 Aurora」，\n然后检查文字是否正确。')
        self.task_input.setFixedHeight(104)
        self.task_input.installEventFilter(self)
        box.addWidget(self.task_input)
        tools = QHBoxLayout()
        self.options_btn = self._button('运行选项', self._toggle_options, 'settings')
        tools.addWidget(self.options_btn)
        tools.addStretch()
        tools.addWidget(text('Ctrl + Enter 启动', 'tiny'))
        box.addLayout(tools)
        v.addWidget(self.composer)
        examples = QHBoxLayout()
        examples.setSpacing(8)
        self.example_buttons = []
        for title, glyph, task in [
            ('记事本演示', 'edit', '打开记事本，输入「你好，我是 Aurora Computer Use」，然后检查文字是否正确。不要保存文件。'),
            ('浏览器演示', 'monitor', '打开浏览器，访问 example.com，并告诉我页面标题。不要提交任何表单。'),
        ]:
            btn = self._button(title, lambda checked=False, value=task: self.task_input.setPlainText(value), glyph, 'chip')
            self.example_buttons.append(btn)
            examples.addWidget(btn)
        examples.addStretch()
        v.addLayout(examples)
        self.run_options = QWidget()
        ov = QVBoxLayout(self.run_options)
        ov.setContentsMargins(0, 4, 0, 8)
        fields = QHBoxLayout()
        fields.addWidget(text('最多步骤', 'fieldlabel'))
        self.steps = QSpinBox()
        self.steps.setRange(1, 200)
        self.steps.setValue(100)
        self.steps.setMinimumWidth(88)
        self.steps.setAccessibleName('最多步骤')
        fields.addWidget(self.steps)
        fields.addSpacing(12)
        fields.addWidget(text('启动延迟', 'fieldlabel'))
        self.delay = QSpinBox()
        self.delay.setRange(0, 30)
        self.delay.setValue(3)
        self.delay.setSuffix(' 秒')
        self.delay.setMinimumWidth(88)
        self.delay.setAccessibleName('启动延迟秒数')
        fields.addWidget(self.delay)
        fields.addStretch()
        ov.addLayout(fields)
        self.vision_check = QCheckBox('启动前验证模型的识图能力')
        self.vision_check.setChecked(True)
        ov.addWidget(self.vision_check)
        self.run_options.hide()
        return w

    def _make_action_dock(self):
        dock = QFrame()
        dock.setObjectName('dock')
        h = QHBoxLayout(dock)
        h.setContentsMargins(24, 14, 24, 14)
        h.setSpacing(12)
        note = text('启动后自动最小化，任务结束后返回', 'tiny', True)
        note.setMinimumWidth(140)
        h.addWidget(note, 1)
        self.stop_btn = self._button('停止任务', self.stop_task, 'stop', 'stop')
        self.stop_btn.setEnabled(False)
        self.stop_btn.setMinimumWidth(110)
        self.start_btn = self._button('启动自动任务', self.start_task, 'arrow', 'primary')
        self.start_btn.setMinimumWidth(160)
        h.addWidget(self.stop_btn)
        h.addWidget(self.start_btn)
        return dock

    def _make_inspector(self):
        frame = QFrame()
        frame.setObjectName('inspector')
        v = QVBoxLayout(frame)
        v.setContentsMargins(20, 24, 20, 20)
        v.setSpacing(16)
        head = QHBoxLayout()
        head.addWidget(text('屏幕观察', 'sectitle'))
        head.addStretch()
        self.step_metric = text('00 / 100', 'tiny')
        self.step_metric.setAccessibleName('已执行步骤与上限')
        head.addWidget(self.step_metric)
        v.addLayout(head)
        preview_frame = QFrame()
        preview_frame.setObjectName('previewInner')
        preview_v = QVBoxLayout(preview_frame)
        preview_v.setContentsMargins(8, 8, 8, 8)
        self.preview = QLabel('任务开始后\n桌面画面会显示在这里')
        self.preview.setObjectName('muted')
        self.preview.setAccessibleName('桌面观察画面')
        self.preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview.setMinimumSize(0, 180)
        self.preview.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Expanding)
        preview_v.addWidget(self.preview)
        v.addWidget(preview_frame, 2)
        self.preview_info = text('尚未收到画面', 'tiny')
        v.addWidget(self.preview_info)
        self.progress_tabs = QTabWidget()
        self.progress_tabs.setDocumentMode(True)
        self.task_progress_view = QPlainTextEdit()
        self.task_progress_view.setReadOnly(True)
        self.task_progress_view.setObjectName('responseDetail')
        self.task_progress_view.setAccessibleName('执行进度')
        self.task_progress_view.setPlaceholderText('执行时显示已完成的操作、\n当前状态和下一步。')
        self.locked_goal_view = QPlainTextEdit()
        self.locked_goal_view.setReadOnly(True)
        self.locked_goal_view.setObjectName('responseDetail')
        self.locked_goal_view.setAccessibleName('锁定的总体目标，只读')
        self.locked_goal_view.setPlaceholderText('启动时锁定总体目标，\n执行过程中保持不变。')
        self.progress_tabs.addTab(self.task_progress_view, '执行进度')
        self.progress_tabs.addTab(self.locked_goal_view, '总体目标')
        v.addWidget(self.progress_tabs, 3)
        v.addWidget(text('截图会发送至你配置的模型 API。', 'tiny', True))
        return frame

    def _make_settings_page(self):
        page = QWidget()
        page.setObjectName('page')
        outer = QHBoxLayout(page)
        outer.setContentsMargins(32, 28, 32, 28)
        content = QWidget()
        content.setMaximumWidth(720)
        v = QVBoxLayout(content)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(18)
        v.addWidget(text('连接你的 AI 模型', 'headline'))
        v.addWidget(text('使用支持图片输入的 OpenAI 兼容 API。', 'subtitle', True))
        status = QHBoxLayout()
        status.addWidget(text('连接状态', 'fieldlabel'))
        status.addStretch()
        self.connection_metric = text('未验证', 'badge')
        status.addWidget(self.connection_metric)
        v.addLayout(status)
        self.endpoint = self._settings_input(v, 'API 端点 / Base URL', 'https://your-provider.com/v1')
        v.addWidget(text('填写 /v1 或完整的 /chat/completions 地址。', 'tiny', True))
        self.model = self._settings_input(v, '视觉模型名称', '输入服务商提供的 Model ID')
        field_label = text('API 密钥', 'fieldlabel')
        v.addWidget(field_label)
        secret = QHBoxLayout()
        self.api_key = QLineEdit()
        self.api_key.setAccessibleName('API 密钥')
        field_label.setBuddy(self.api_key)
        self.api_key.setEchoMode(QLineEdit.EchoMode.Password)
        self.api_key.setPlaceholderText('输入 API Key')
        secret.addWidget(self.api_key, 1)
        self.eye_btn = self._button('', self._toggle_secret, 'eye', 'eye')
        self.eye_btn.setFixedWidth(40)
        self.eye_btn.setAccessibleName('显示或隐藏 API 密钥')
        self.eye_btn.setToolTip('显示或隐藏 API 密钥')
        secret.addWidget(self.eye_btn)
        v.addLayout(secret)
        auth_row = QHBoxLayout()
        auth_row.addWidget(text('鉴权方式', 'fieldlabel'))
        auth_row.addStretch()
        self.auth = QComboBox()
        self.auth.setAccessibleName('鉴权方式')
        for name, value in [('Bearer Token', 'bearer'), ('x-api-key', 'x-api-key'), ('无鉴权 / 本地模型', 'none')]:
            self.auth.addItem(name, value)
        self.auth.setMinimumWidth(220)
        auth_row.addWidget(self.auth)
        v.addLayout(auth_row)
        self.remember = QCheckBox('使用 Windows 凭据管理器记住密钥')
        self.remember.setToolTip('密钥不写入配置文件；勾选后使用系统凭据保险库。')
        v.addWidget(self.remember)
        self.connection_info = text('密钥默认仅保存在本次运行的内存中。', 'tiny', True)
        v.addWidget(self.connection_info)
        buttons = QHBoxLayout()
        self.check_btn = self._button('测试连接 / 识图', self._check_connection, 'link')
        buttons.addWidget(self.check_btn)
        buttons.addStretch()
        self.save_btn = self._button('保存并返回工作台', self._save_and_return, 'check', 'primary')
        buttons.addWidget(self.save_btn)
        v.addLayout(buttons)
        v.addStretch()
        outer.addStretch()
        outer.addWidget(content, 1)
        outer.addStretch()
        return scrollable(page)

    def _settings_input(self, layout, title, placeholder):
        caption = text(title, 'fieldlabel')
        layout.addWidget(caption)
        edit = QLineEdit()
        edit.setPlaceholderText(placeholder)
        edit.setAccessibleName(title)
        caption.setBuddy(edit)
        layout.addWidget(edit)
        return edit

    def _save_and_return(self):
        self._save_preferences()
        self._append_log('ok', '模型配置已保存')
        self._navigate(0)

    def _navigate(self, index, nav_key=None):
        self.pages.setCurrentIndex(index)
        titles = ['任务工作台', 'API 响应记录', '用户回复']
        self.page_title.setText(titles[self.diagnostics.currentIndex()] if index == 0 else {1: '模型与连接', 2: '屏幕观察'}[index])
        active = nav_key or ({0: 'workspace', 1: 'responses', 2: 'reply'}[self.diagnostics.currentIndex()] if index == 0 else {1: 'settings', 2: 'observer'}[index])
        for key, btn in self.nav.items():
            btn.setCheckable(True)
            btn.setChecked(key == active)
            btn.setObjectName('navActive' if key == active else 'nav')
            btn.setProperty('selected', key == active)
            btn.style().unpolish(btn)
            btn.style().polish(btn)
        self._sync_observer()

    def _open_diagnostics(self, index):
        self._restore()
        self.diagnostics.setCurrentIndex(index)
        self._navigate(0, {0: 'workspace', 1: 'responses', 2: 'reply'}[index])

    def _sync_observer(self):
        if not hasattr(self, 'inspector'):
            return
        page = self.pages.currentIndex()
        if page == 2:
            self.observer_host.addWidget(self.inspector)
            self.inspector.show()
        elif page == 0:
            if self.workspace_split.indexOf(self.inspector) < 0:
                self.workspace_split.addWidget(self.inspector)
                self.workspace_split.setSizes([740, 350])
            self.inspector.setVisible(self.width() >= 1240)
        if self.current_pixmap:
            QTimer.singleShot(0, self._show_preview)

    def _toggle_options(self):
        if not hasattr(self, 'options_dialog'):
            self.options_dialog = QDialog(self)
            self.options_dialog.setWindowTitle('运行选项')
            self.options_dialog.setMinimumWidth(480)
            layout = QVBoxLayout(self.options_dialog)
            layout.setContentsMargins(24, 24, 24, 24)
            layout.setSpacing(16)
            layout.addWidget(text('运行选项', 'sectitle'))
            layout.addWidget(self.run_options)
            self.run_options.show()
            close = self._button('完成', self.options_dialog.accept, 'check', 'primary')
            layout.addWidget(close)
        self.options_dialog.open()
        self.steps.setFocus()

    def _diagnostic_changed(self, index):
        self.task_area.setVisible(index == 0)
        if self.pages.currentIndex() == 0:
            self._navigate(0)

    def _run_from_keyboard(self):
        # Native multiline editing and IME composition stay with Qt.
        if self.pages.currentIndex() == 0 and self.start_btn.isEnabled():
            self.start_task()

    def eventFilter(self, watched, event):
        if watched is getattr(self, 'task_input', None) and event.type() in (QEvent.Type.FocusIn, QEvent.Type.FocusOut):
            self.composer.setProperty('focused', event.type() == QEvent.Type.FocusIn)
            self.composer.style().unpolish(self.composer)
            self.composer.style().polish(self.composer)
        return super().eventFilter(watched, event)

    def _theme_changed(self):
        self.settings.setValue('theme', self.theme_choice.currentData())
        self._apply_theme()

    def _system_theme_changed(self, *_):
        if self.theme_choice.currentData() == 'system':
            self._apply_theme()

    def _apply_theme(self):
        pref = self.theme_choice.currentData()
        system_dark = QApplication.instance().styleHints().colorScheme() == Qt.ColorScheme.Dark
        self.theme = ('dark' if system_dark else 'light') if pref == 'system' else pref
        self.theme_colors = apply_theme(QApplication.instance(), self.theme)
        for btn in self.findChildren(QPushButton):
            glyph = btn.property('glyph')
            if glyph:
                color = self.theme_colors['on-action' if btn.objectName() == 'primary' else 'secondary']
                btn.setIcon(icon(glyph, color))
        self._dark_titlebar()
