"""Neutral native Qt theme and a single set of monochrome line icons."""
from __future__ import annotations

import json
from pathlib import Path

from PySide6.QtCore import QByteArray, Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPalette, QPixmap
from PySide6.QtSvg import QSvgRenderer

ASSETS = Path(__file__).resolve().parent / 'assets'
PALETTES = {name: json.loads((ASSETS / f'theme-{name}.json').read_text('utf-8'))['colors']
            for name in ('light', 'dark')}

PATHS = {
    'workspace': '<rect x="4" y="4" width="16" height="16" rx="3"/><path d="M4 10h16M10 10v10"/>',
    'settings': '<path d="M4 6h16M4 12h16M4 18h16"/><circle cx="9" cy="6" r="2"/><circle cx="15" cy="12" r="2"/><circle cx="9" cy="18" r="2"/>',
    'monitor': '<rect x="3" y="4" width="18" height="13" rx="2"/><path d="M8 21h8m-4-4v4"/>',
    'activity': '<path d="M4 5h16M4 12h16M4 19h10"/>',
    'reply': '<path d="M20 15a3 3 0 0 1-3 3H9l-5 3V6a3 3 0 0 1 3-3h10a3 3 0 0 1 3 3z"/>',
    'help': '<circle cx="12" cy="12" r="9"/><path d="M9.5 9a2.5 2.5 0 1 1 4 2c-1 .6-1.5 1-1.5 2M12 17h.01"/>',
    'copy': '<rect x="8" y="8" width="12" height="13" rx="2"/><path d="M16 8V4a1 1 0 0 0-1-1H4a1 1 0 0 0-1 1v11a1 1 0 0 0 1 1h4"/>',
    'eye': '<path d="M2 12s3-7 10-7 10 7 10 7-3 7-10 7S2 12 2 12z"/><circle cx="12" cy="12" r="3"/>',
    'arrow': '<path d="M12 19V5m-6 6 6-6 6 6"/>',
    'stop': '<rect x="6" y="6" width="12" height="12" rx="1" fill="currentColor"/>',
    'chevron': '<path d="m7 10 5 5 5-5"/>',
    'check': '<path d="m5 12 4 4L19 6"/>',
    'edit': '<path d="m16 3 5 5-12 12-6 1 1-6zM14 5l5 5"/>',
    'link': '<path d="m10 14 4-4m-6 6-2 2a3 3 0 0 1-4-4l5-5a3 3 0 0 1 4 0m2 6a3 3 0 0 0 4 0l5-5a3 3 0 0 0-4-4l-2 2"/>',
}


def icon(name: str, color: str, size: int = 20) -> QIcon:
    body = PATHS[name].replace('currentColor', color)
    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" '
           f'fill="none" stroke="{color}" stroke-width="1.7" stroke-linecap="round" '
           f'stroke-linejoin="round">{body}</svg>')
    renderer = QSvgRenderer(QByteArray(svg.encode()))
    pix = QPixmap(size * 2, size * 2)
    pix.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pix)
    renderer.render(painter)
    painter.end()
    pix.setDevicePixelRatio(2)
    return QIcon(pix)


def apply_theme(app, theme: str) -> dict:
    c = PALETTES[theme]
    palette = QPalette()
    for role, token in {'Window': 'canvas', 'WindowText': 'text', 'Base': 'canvas',
                        'AlternateBase': 'surface', 'Text': 'text', 'Button': 'surface',
                        'ButtonText': 'text', 'Highlight': 'selected', 'HighlightedText': 'text',
                        'ToolTipBase': 'overlay', 'ToolTipText': 'text', 'PlaceholderText': 'muted',
                        'Light': 'border', 'Mid': 'border-strong', 'Dark': 'secondary'}.items():
        palette.setColor(getattr(QPalette.ColorRole, role), QColor(c[token]))
    for role in ('Text', 'WindowText', 'ButtonText'):
        palette.setColor(QPalette.ColorGroup.Disabled, getattr(QPalette.ColorRole, role), QColor(c['disabled']))
    app.setPalette(palette)
    app.setStyleSheet(stylesheet(c))
    return c


def stylesheet(c):
    theme = 'dark' if c['canvas'] == '#212121' else 'light'
    check = (ASSETS / f'check-{theme}.svg').as_posix()
    chevron = (ASSETS / f'chevron-{theme}.svg').as_posix()
    return f"""
QWidget {{ color: {c['text']}; font-size: 14px; background: transparent; }}
QMainWindow, QDialog, QWidget#root, QWidget#page {{ background: {c['canvas']}; }}
QFrame#sidebar {{ background: {c['sidebar']}; }}
QFrame#topbar {{ border-bottom: 1px solid {c['border']}; }}
QFrame#inspector {{ background: {c['sidebar']}; border-left: 1px solid {c['border']}; }}
QFrame#panel {{ border: 0; background: transparent; }}
QFrame#dock {{ background: {c['canvas']}; border-top: 1px solid {c['border']}; }}
QFrame#composer {{ background: {c['surface']}; border-radius: 24px; }}
QFrame#previewInner {{ background: {c['surface']}; border-radius: 12px; }}
QLabel {{ border: 0; background: transparent; }}
QLabel#brandname {{ font-size: 18px; font-weight: 600; }}
QLabel#brandmark {{ font-size: 20px; font-weight: 600; border-radius: 9px; background: {c['action']}; color: {c['on-action']}; }}
QLabel#headline {{ font-size: 28px; font-weight: 600; }}
QLabel#pagetitle {{ font-size: 18px; font-weight: 600; }}
QLabel#sectitle {{ font-size: 15px; font-weight: 600; }}
QLabel#fieldlabel {{ font-size: 14px; font-weight: 500; }}
QLabel#subtitle, QLabel#muted, QLabel#tiny, QLabel#sidecaption, QLabel#kicker, QLabel#callout {{ color: {c['muted']}; font-size: 13px; }}
QLabel#good {{ color: {c['success']}; font-size: 13px; }}
QLabel#warning {{ color: {c['danger']}; font-size: 13px; }}
QLabel#accent {{ color: {c['secondary']}; font-size: 13px; }}
QLabel#badge {{ color: {c['secondary']}; background: {c['surface']}; padding: 5px 12px; border-radius: 12px; font-size: 13px; }}
QPushButton {{ min-height: 24px; padding: 7px 12px; border: 1px solid {c['border']}; border-radius: 10px; background: transparent; font-weight: 500; }}
QPushButton:hover {{ background: {c['hover']}; }}
QPushButton:pressed {{ background: {c['pressed']}; }}
QPushButton:focus {{ border-color: {c['focus']}; }}
QPushButton#primary {{ background: {c['action']}; color: {c['on-action']}; border-color: {c['action']}; }}
QPushButton#primary:hover {{ background: {c['action-hover']}; }}
QPushButton#primary:pressed {{ background: {c['action-pressed']}; }}
QPushButton#primary:focus {{ border-color: {c['focus']}; }}
QPushButton#stop {{ color: {c['danger']}; }}
QPushButton#stop:hover {{ background: {c['danger-surface']}; }}
QPushButton#nav, QPushButton#navActive {{ text-align: left; border: 1px solid transparent; padding: 8px 12px; }}
QPushButton#navActive {{ background: {c['selected']}; }}
QPushButton#nav:focus, QPushButton#navActive:focus {{ border-color: {c['focus']}; }}
QPushButton#ghost, QPushButton#eye {{ border-color: transparent; }}
QPushButton#chip {{ color: {c['secondary']}; font-size: 13px; padding: 6px 10px; }}
QPushButton:disabled, QPushButton#primary:disabled, QPushButton#stop:disabled {{ color: {c['disabled']}; background: {c['surface']}; border-color: transparent; }}
QLineEdit, QPlainTextEdit, QComboBox, QSpinBox {{ color: {c['text']}; background: {c['canvas']}; border: 1px solid {c['border-strong']}; border-radius: 10px; padding: 9px 12px; selection-background-color: {c['action']}; selection-color: {c['on-action']}; }}
QLineEdit, QComboBox, QSpinBox {{ min-height: 22px; }}
QLineEdit:focus, QPlainTextEdit:focus, QComboBox:focus, QSpinBox:focus {{ border-color: {c['focus']}; }}
QLineEdit:disabled, QPlainTextEdit:disabled, QComboBox:disabled, QSpinBox:disabled {{ color: {c['disabled']}; background: {c['surface']}; border-color: {c['border']}; }}
QPlainTextEdit#task {{ background: transparent; border: 0; font-size: 16px; padding: 4px; }}
QPlainTextEdit#task:focus {{ border: 0; }}
QFrame#composer[focused="true"] {{ border: 1px solid {c['focus']}; }}
QPlainTextEdit#console, QPlainTextEdit#responseDetail {{ background: transparent; border: 1px solid transparent; padding: 6px; font-size: 13px; }}
QPlainTextEdit#console:focus, QPlainTextEdit#responseDetail:focus {{ border-color: {c['focus']}; }}
QPlainTextEdit#console {{ font-family: 'Cascadia Code', 'Consolas', 'Noto Sans CJK SC', monospace; }}
QPlainTextEdit#responseDetail {{ selection-background-color: {c['action']}; }}
QTabWidget::pane {{ border: 0; border-top: 1px solid {c['border']}; }}
QTabBar::tab {{ color: {c['muted']}; padding: 10px 12px; border-bottom: 2px solid transparent; }}
QTabBar::tab:selected {{ color: {c['text']}; border-bottom-color: {c['text']}; }}
QTabBar::tab:hover {{ background: {c['hover']}; }}
QTabBar::tab:focus {{ background: {c['hover']}; }}
QListWidget {{ background: {c['surface']}; border: 0; border-radius: 8px; padding: 4px; }}
QListWidget::item {{ padding: 8px; border-radius: 6px; }}
QListWidget::item:selected {{ background: {c['selected']}; color: {c['text']}; }}
QListWidget::item:hover {{ background: {c['hover']}; }}
QCheckBox {{ spacing: 8px; color: {c['secondary']}; }}
QCheckBox::indicator {{ width: 16px; height: 16px; border: 1px solid {c['border-strong']}; border-radius: 4px; background: {c['canvas']}; }}
QCheckBox::indicator:checked {{ background: {c['action']}; border-color: {c['action']}; image: url("{check}"); }}
QCheckBox::indicator:disabled {{ background: {c['surface']}; border-color: {c['disabled']}; }}
QCheckBox:focus {{ color: {c['text']}; }}
QCheckBox::indicator:focus {{ border: 2px solid {c['focus']}; }}
QComboBox {{ padding-right: 30px; }}
QComboBox::drop-down {{ border: 0; width: 28px; }}
QComboBox::down-arrow {{ image: url("{chevron}"); width: 16px; height: 16px; }}
QComboBox QAbstractItemView {{ background: {c['overlay']}; color: {c['text']}; selection-background-color: {c['selected']}; selection-color: {c['text']}; border: 1px solid {c['border']}; }}
QScrollArea {{ border: 0; background: transparent; }}
QScrollBar:vertical {{ width: 8px; background: transparent; margin: 2px; }}
QScrollBar::handle:vertical {{ background: {c['border-strong']}; border-radius: 2px; min-height: 24px; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ background: transparent; }}
QScrollBar:horizontal {{ height: 8px; background: transparent; }}
QScrollBar::handle:horizontal {{ background: {c['border-strong']}; min-width: 24px; border-radius: 4px; }}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width: 0; }}
QSplitter::handle {{ background: {c['border']}; }}
QMenu, QToolTip {{ background: {c['overlay']}; color: {c['text']}; border: 1px solid {c['border']}; padding: 8px; }}
QMenu::item {{ padding: 8px 18px; border-radius: 6px; }}
QMenu::item:selected {{ background: {c['hover']}; }}
QMenu::item:disabled {{ color: {c['disabled']}; }}
QMessageBox {{ background: {c['overlay']}; }}
"""
