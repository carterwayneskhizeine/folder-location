#!/usr/bin/env python3
"""Folder Location + 文件预览 — 多标签页（入口 + 主窗口）"""
import sys
import ctypes
from pathlib import Path

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QSplitter, QSystemTrayIcon, QMenu, QToolButton,
)
from PySide6.QtCore import Qt, QTimer, QEvent, QSettings
from PySide6.QtGui import QIcon, QAction, QShortcut, QKeySequence

from theme import (
    apply_dark_palette, STYLESHEET, _apply_dark_titlebar, _load_icon,
)
from left_panel import LeftPanel
from preview import PreviewPane


class MainWindow(QMainWindow):
    _SETTINGS_ORG = "FolderTree"
    _SETTINGS_APP = "FolderTree"

    def __init__(self, icon: QIcon) -> None:
        super().__init__()
        self._icon = icon
        self.setWindowTitle("Folder Location")
        self.setWindowIcon(icon)
        self.resize(1280, 720)
        self.setMinimumSize(700, 500)

        central = QWidget()
        self.setCentralWidget(central)
        vl = QVBoxLayout(central)
        vl.setContentsMargins(0, 0, 0, 0)
        vl.setSpacing(0)

        # ── 主分割器 ────────────────────────────────────────────────────
        self._splitter = QSplitter(Qt.Orientation.Horizontal)
        self._splitter.setHandleWidth(1)
        self._splitter.setChildrenCollapsible(False)

        self.left_panel = LeftPanel()
        self.preview = PreviewPane()

        self._splitter.addWidget(self.left_panel)
        self._splitter.addWidget(self.preview)
        self._splitter.setSizes([432, 1040])
        vl.addWidget(self._splitter, 1)

        # ── 状态栏（含左侧面板折叠按钮） ───────────────────────────────────
        status_row = QWidget()
        status_row.setObjectName("statusBar")
        sr = QHBoxLayout(status_row)
        sr.setContentsMargins(6, 0, 12, 0)
        sr.setSpacing(6)

        self._toggle_left_btn = QToolButton()
        self._toggle_left_btn.setObjectName("sidebarToggleBtn")
        self._toggle_left_btn.setText("⮜")
        self._toggle_left_btn.setToolTip("隐藏左侧面板 (Ctrl+B)")
        self._toggle_left_btn.setFixedSize(22, 22)
        self._toggle_left_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._toggle_left_btn.clicked.connect(self.toggle_left_panel)
        sr.addWidget(self._toggle_left_btn)

        self._status = QLabel()
        self._status.setObjectName("statusBarText")
        sr.addWidget(self._status, 1)

        self._fade = QTimer(self)
        self._fade.setSingleShot(True)
        self._fade.setInterval(3000)
        self._fade.timeout.connect(lambda: self._status.setText(""))
        vl.addWidget(status_row)

        # 信号
        self.left_panel.file_selected.connect(self.preview.show_file)
        self.left_panel.path_copied.connect(self._on_copied)
        self.left_panel.folder_changed.connect(self._on_folder_changed)
        self.preview.path_copied.connect(self._on_copied)
        self.preview.file_tab_switched.connect(self._on_preview_tab_switched)

        # 快捷键
        QShortcut(QKeySequence("Ctrl+O"), self).activated.connect(
            self.left_panel.add_folder
        )
        QShortcut(QKeySequence("Ctrl+F"), self).activated.connect(
            self.preview.open_search
        )
        QShortcut(QKeySequence("Ctrl+B"), self).activated.connect(
            self.toggle_left_panel
        )

        self._left_collapsed = False
        self._saved_left_width = 432

        self._quitting = False
        self._setup_tray(icon)

    # ── 左侧面板隐藏切换 ──────────────────────────────────────────────────────

    def toggle_left_panel(self) -> None:
        sizes = self._splitter.sizes()
        if not self._left_collapsed:
            if sizes and sizes[0] > 0:
                self._saved_left_width = sizes[0]
            total = sum(sizes) or 1
            self._splitter.setSizes([0, total])
            self.left_panel.hide()
            self._left_collapsed = True
            self._toggle_left_btn.setText("⮞")
            self._toggle_left_btn.setToolTip("显示左侧面板 (Ctrl+B)")
        else:
            self.left_panel.show()
            total = sum(sizes) or 1
            right = max(200, total - self._saved_left_width)
            self._splitter.setSizes([self._saved_left_width, right])
            self._left_collapsed = False
            self._toggle_left_btn.setText("⮜")
            self._toggle_left_btn.setToolTip("隐藏左侧面板 (Ctrl+B)")

    # ── 系统托盘 ──────────────────────────────────────────────────────────────

    def _setup_tray(self, icon: QIcon) -> None:
        self._tray = QSystemTrayIcon(icon, self)
        self._tray.setToolTip("Folder Location")

        menu = QMenu()
        self._show_act = QAction("显示窗口", self)
        self._show_act.triggered.connect(self._show_window)
        menu.addAction(self._show_act)
        menu.addSeparator()
        quit_act = QAction("退出", self)
        quit_act.triggered.connect(self._quit)
        menu.addAction(quit_act)

        self._tray.setContextMenu(menu)
        self._tray.activated.connect(self._on_tray_activated)
        self._tray.show()
        self._update_tray_menu()

    def _update_tray_menu(self) -> None:
        visible = self.isVisible() and not self.isMinimized()
        self._show_act.setText("隐藏窗口" if visible else "显示窗口")

    def _on_tray_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason in (
            QSystemTrayIcon.ActivationReason.Trigger,
            QSystemTrayIcon.ActivationReason.DoubleClick,
        ):
            if self.isVisible() and not self.isMinimized():
                self.hide()
            else:
                self._show_window()
            self._update_tray_menu()

    def _show_window(self) -> None:
        self.showNormal()
        self.activateWindow()
        self.raise_()
        _apply_dark_titlebar(self)
        self._update_tray_menu()

    def showEvent(self, event) -> None:
        super().showEvent(event)
        _apply_dark_titlebar(self)
        QTimer.singleShot(0, lambda: _apply_dark_titlebar(self))
        QTimer.singleShot(200, lambda: self.setWindowIcon(self._icon))

    def changeEvent(self, event) -> None:
        super().changeEvent(event)
        if event.type() in (QEvent.Type.ActivationChange, QEvent.Type.WindowStateChange):
            QTimer.singleShot(0, lambda: _apply_dark_titlebar(self))

    def _quit(self) -> None:
        self._quitting = True
        QApplication.instance().quit()

    def closeEvent(self, event) -> None:
        if self._quitting:
            event.accept()
            return
        event.ignore()
        self.hide()
        self._update_tray_menu()
        self._tray.showMessage(
            "Folder Location",
            "已最小化到系统托盘  —  右键图标选择「退出」可关闭程序",
            QSystemTrayIcon.MessageIcon.Information,
            2500,
        )

    # ── 会话保存 / 恢复 ───────────────────────────────────────────────────────

    def save_session(self) -> None:
        s = QSettings(self._SETTINGS_ORG, self._SETTINGS_APP)
        s.setValue("session/folders",  self.left_panel.open_paths())
        s.setValue("session/last_dir", self.left_panel._last_dir)
        s.setValue("session/preview_files", self.preview.open_paths())
        s.setValue("session/browser_urls", self.preview.browser_urls())
        s.setValue("session/left_collapsed", self._left_collapsed)
        s.setValue("session/left_width", self._saved_left_width)

    def restore_session(self) -> None:
        s = QSettings(self._SETTINGS_ORG, self._SETTINGS_APP)
        last_dir = s.value("session/last_dir", "")
        if last_dir:
            self.left_panel._last_dir = last_dir

        paths = s.value("session/folders", [])
        if isinstance(paths, str):
            paths = [paths] if paths else []
        for p in paths or []:
            self.left_panel.open_path(str(p))

        preview_paths = s.value("session/preview_files", [])
        if isinstance(preview_paths, str):
            preview_paths = [preview_paths] if preview_paths else []
        if preview_paths:
            self.preview.restore_tabs(preview_paths)

        browser_urls = s.value("session/browser_urls", [])
        if isinstance(browser_urls, str):
            browser_urls = [browser_urls] if browser_urls else []
        if browser_urls:
            self.preview.restore_browser_tabs(browser_urls)

        try:
            self._saved_left_width = int(s.value("session/left_width", 432))
        except (TypeError, ValueError):
            self._saved_left_width = 432

        collapsed = s.value("session/left_collapsed", False)
        if isinstance(collapsed, str):
            collapsed = collapsed.lower() in ("true", "1", "yes")
        if collapsed:
            self.toggle_left_panel()

    # ── 状态栏 ────────────────────────────────────────────────────────────────

    def _on_copied(self, text: str) -> None:
        label = text.splitlines()[0] if "\n" in text else text
        if len(label) > 140:
            label = label[:137] + "..."
        self._status.setText(f"  ✓  已复制：{label}")
        self._fade.start()

    def _on_folder_changed(self, path: str) -> None:
        label = path.replace("\\", "/")
        if len(label) > 140:
            label = label[:137] + "..."
        self._status.setText(f"  ↻  已更新：{label}")
        self._fade.start()

    def _on_preview_tab_switched(self, path: Path) -> None:
        self.left_panel.navigate_to_file(path)
        self._status.setText("  " + path.as_posix())
        self._fade.stop()


# ── 入口 ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    if sys.platform == "win32":
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("FolderLocation.App")
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    apply_dark_palette(app)
    app.setStyleSheet(STYLESHEET)

    icon = _load_icon()
    app.setWindowIcon(icon)

    win = MainWindow(icon)
    win.winId()
    win.show()
    win.restore_session()
    app.aboutToQuit.connect(win.save_session)
    sys.exit(app.exec())
