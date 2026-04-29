"""文件夹树及多文件夹标签页。"""
import subprocess
from pathlib import Path

from PySide6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QTreeWidget, QTreeWidgetItem, QTabBar,
    QFileDialog, QStackedWidget, QToolButton, QScrollBar,
)
from PySide6.QtCore import (
    Qt, QTimer, QEvent, Signal, QSize, QFileSystemWatcher,
)
from PySide6.QtGui import QColor, QShortcut, QKeySequence

from theme import _file_icon, HiddenTabScrollButtonStyle


_DIR_ROLE   = Qt.ItemDataRole.UserRole
_IS_DIR     = Qt.ItemDataRole.UserRole + 1
_PATH_ROLE  = Qt.ItemDataRole.UserRole + 2
_PLACEHOLDER = "__pending__"
_ADD_FOLDER_TAB = "__add_folder_tab__"


# ── FolderTree ────────────────────────────────────────────────────────────────

class FolderTree(QTreeWidget):
    path_copied       = Signal(str)
    file_selected     = Signal(Path)
    folder_changed    = Signal(str)
    file_change_event = Signal(str, str)

    _BTN_H = 22
    _BTN_GAP = 4

    def __init__(self) -> None:
        super().__init__()
        self.setHeaderHidden(True)
        self.setIndentation(16)
        self.setUniformRowHeights(True)
        self.setAnimated(True)
        self.setMouseTracking(True)
        self.viewport().setMouseTracking(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)

        self._hovered: QTreeWidgetItem | None = None
        self._root_path: Path | None = None
        self._root_parent: Path | None = None
        self._root_exists = False
        self._pending_refresh: set[str] = set()
        self._pending_file_modified: set[str] = set()

        self._watcher = QFileSystemWatcher(self)
        self._watcher.directoryChanged.connect(self._on_directory_changed)
        self._watcher.fileChanged.connect(self._on_tree_file_changed)

        self._refresh_timer = QTimer(self)
        self._refresh_timer.setSingleShot(True)
        self._refresh_timer.setInterval(120)
        self._refresh_timer.timeout.connect(self._flush_refreshes)

        self._copy_btn = QPushButton("Copy", self.viewport())
        self._copy_btn.setObjectName("treeActionBtn")
        self._copy_btn.setFixedHeight(self._BTN_H)
        self._copy_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._copy_btn.setToolTip("复制路径")
        self._copy_btn.hide()
        self._copy_btn.clicked.connect(self._do_copy)

        self._explorer_btn = QPushButton("Open", self.viewport())
        self._explorer_btn.setObjectName("treeActionBtn")
        self._explorer_btn.setFixedHeight(self._BTN_H)
        self._explorer_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._explorer_btn.setToolTip("在资源管理器中打开")
        self._explorer_btn.hide()
        self._explorer_btn.clicked.connect(self._do_open_explorer)

        self._hide_timer = QTimer(self)
        self._hide_timer.setSingleShot(True)
        self._hide_timer.setInterval(90)
        self._hide_timer.timeout.connect(self._hide_action_btns)

        self.viewport().installEventFilter(self)
        self._copy_btn.installEventFilter(self)
        self._explorer_btn.installEventFilter(self)
        self.itemExpanded.connect(self._on_expanded)
        self.itemClicked.connect(self._on_item_clicked)

    def _hide_action_btns(self) -> None:
        self._copy_btn.hide()
        self._explorer_btn.hide()

    def eventFilter(self, obj, event) -> bool:
        if obj is self.viewport():
            t = event.type()
            if t == QEvent.Type.MouseMove:
                item = self.itemAt(event.position().toPoint())
                if item is not self._hovered:
                    self._hovered = item
                    if item:
                        self._reposition()
                        self._hide_timer.stop()
                        self._copy_btn.show()
                        self._explorer_btn.show()
                    else:
                        self._hide_timer.start()
            elif t == QEvent.Type.Leave:
                self._hide_timer.start()
        elif obj in (self._copy_btn, self._explorer_btn):
            t = event.type()
            if t == QEvent.Type.Enter:
                self._hide_timer.stop()
                self._copy_btn.show()
                self._explorer_btn.show()
            elif t == QEvent.Type.Leave:
                self._hovered = None
                self._hide_timer.start()
        return super().eventFilter(obj, event)

    def _reposition(self) -> None:
        if not self._hovered:
            return
        rect = self.visualItemRect(self._hovered)
        right = self.viewport().width() - 6
        y = rect.top() + (rect.height() - self._BTN_H) // 2
        ex_w = self._explorer_btn.width()
        cp_w = self._copy_btn.width()
        self._explorer_btn.move(right - ex_w, y)
        self._explorer_btn.raise_()
        self._copy_btn.move(right - ex_w - self._BTN_GAP - cp_w, y)
        self._copy_btn.raise_()

    def _do_copy(self) -> None:
        item = self._hovered
        if not item:
            return
        raw: str = item.data(0, _DIR_ROLE) or ""
        if raw:
            text = "@" + raw.replace("\\", "/")
            QApplication.clipboard().setText(text)
            self.path_copied.emit(text)
            self._copy_btn.setText("OK")
            QTimer.singleShot(900, lambda: self._copy_btn.setText("Copy"))

    def _do_open_explorer(self) -> None:
        item = self._hovered
        if not item:
            return
        p: Path | None = item.data(0, _PATH_ROLE)
        if p and p.exists():
            subprocess.Popen(f'explorer /select,"{p}"')
        else:
            raw: str = item.data(0, _DIR_ROLE) or ""
            if raw:
                folder = Path(raw)
                if folder.exists():
                    subprocess.Popen(f'explorer "{folder}"')

    def _on_item_clicked(self, item: QTreeWidgetItem, _col: int) -> None:
        if not item.data(0, _IS_DIR):
            p: Path | None = item.data(0, _PATH_ROLE)
            if p and p.is_file():
                self.file_selected.emit(p)

    def load_folder(self, folder: Path, display_root: str) -> None:
        self.clear()
        self._copy_btn.hide()
        self._explorer_btn.hide()
        self._hovered = None
        self._root_path = folder
        self._root_parent = folder.parent
        self._root_exists = folder.is_dir()
        self._reset_watcher()

        root = QTreeWidgetItem(self)
        root.setText(0, "📂  " + folder.name)
        root.setData(0, _DIR_ROLE, display_root)
        root.setData(0, _IS_DIR, True)
        root.setData(0, _PATH_ROLE, folder)
        root.setForeground(0, QColor("#ffffff"))
        f = root.font(0)
        f.setBold(True)
        root.setFont(0, f)

        self._fill(root, folder, display_root)
        root.setExpanded(True)
        self._watch_dir(folder)
        self._watch_dir(folder.parent)

    def _fill(self, parent: QTreeWidgetItem, folder: Path, parent_disp: str) -> None:
        if not folder.is_dir():
            return
        self._watch_dir(folder)
        try:
            entries = sorted(folder.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower()))
        except OSError:
            return
        for entry in entries:
            disp = parent_disp + "/" + entry.name
            child = QTreeWidgetItem(parent)
            child.setData(0, _DIR_ROLE, disp)
            child.setData(0, _PATH_ROLE, entry)
            if entry.is_dir():
                self._watch_dir(entry)
                child.setText(0, "📁  " + entry.name)
                child.setData(0, _IS_DIR, True)
                child.setForeground(0, QColor("#e7e9ea"))
                try:
                    if any(entry.iterdir()):
                        QTreeWidgetItem(child).setText(0, _PLACEHOLDER)
                except OSError:
                    pass
            else:
                self._watch_file(entry)
                child.setText(0, _file_icon(entry.name) + entry.name)
                child.setForeground(0, QColor("#e7e9ea"))

    def _on_expanded(self, item: QTreeWidgetItem) -> None:
        if item.childCount() != 1 or item.child(0).text(0) != _PLACEHOLDER:
            return
        item.removeChild(item.child(0))
        folder: Path | None = item.data(0, _PATH_ROLE)
        disp: str = item.data(0, _DIR_ROLE) or ""
        if folder:
            self._fill(item, folder, disp)

    def _reset_watcher(self) -> None:
        paths = self._watcher.directories()
        if paths:
            self._watcher.removePaths(paths)
        files = self._watcher.files()
        if files:
            self._watcher.removePaths(files)
        self._pending_refresh.clear()

    def _watch_dir(self, folder: Path) -> None:
        if not folder.is_dir():
            return
        path = str(folder)
        if path not in self._watcher.directories():
            self._watcher.addPath(path)

    def _watch_file(self, file_path: Path) -> None:
        if not file_path.is_file():
            return
        path = str(file_path)
        if path not in self._watcher.files():
            self._watcher.addPath(path)

    def _on_directory_changed(self, path: str) -> None:
        self._pending_refresh.add(path)
        self._refresh_timer.start()

    def _on_tree_file_changed(self, path: str) -> None:
        self._pending_refresh.add(str(Path(path).parent))
        self._pending_file_modified.add(path)
        self._refresh_timer.start()

    def _flush_refreshes(self) -> None:
        for path in self._pending_file_modified:
            self.file_change_event.emit(path, "modified")
        self._pending_file_modified.clear()

        paths = list(self._pending_refresh)
        self._pending_refresh.clear()
        for path in paths:
            changed = Path(path)
            if self._root_parent and changed == self._root_parent:
                self._refresh_root_if_needed()
                continue
            self._refresh_changed_dir(changed)
        self._reposition()

    def _refresh_root_if_needed(self) -> None:
        if not self._root_path:
            return
        exists = self._root_path.is_dir()
        if exists != self._root_exists:
            self._root_exists = exists
            root = self.topLevelItem(0) if self.topLevelItemCount() else None
            if root:
                self._refresh_item(root)

    def _refresh_changed_dir(self, folder: Path) -> None:
        item = self._find_dir_item(folder)
        if item is None:
            if self._root_path and folder == self._root_path:
                root = self.topLevelItem(0) if self.topLevelItemCount() else None
                if root:
                    self._refresh_item(root)
            return
        self._refresh_item(item)

    def _refresh_item(self, item: QTreeWidgetItem) -> None:
        folder: Path | None = item.data(0, _PATH_ROLE)
        disp: str = item.data(0, _DIR_ROLE) or ""
        if folder is None:
            return

        if not folder.is_dir():
            parent = item.parent()
            if parent is not None:
                self._refresh_item(parent)
                return
            self._root_exists = False
            item.takeChildren()
            item.setText(0, "📂  " + folder.name + "  (已删除)")
            item.setForeground(0, QColor("#f4212e"))
            self.folder_changed.emit(disp or str(folder))
            return

        if item.parent() is None:
            self._root_exists = True
        expanded = self._expanded_dir_paths(item)
        was_expanded = item.isExpanded()

        old_paths: set[str] = set()
        for i in range(item.childCount()):
            child = item.child(i)
            if child.text(0) != _PLACEHOLDER:
                p = child.data(0, _PATH_ROLE)
                if p:
                    old_paths.add(str(p))
        was_populated = bool(old_paths)

        item.takeChildren()
        if item.parent() is None:
            item.setText(0, "📂  " + folder.name)
            item.setForeground(0, QColor("#ffffff"))
        self._fill(item, folder, disp)

        if was_populated:
            new_paths: set[str] = set()
            for i in range(item.childCount()):
                child = item.child(i)
                if child.text(0) != _PLACEHOLDER:
                    p = child.data(0, _PATH_ROLE)
                    if p:
                        new_paths.add(str(p))
            for path in new_paths - old_paths:
                self.file_change_event.emit(path, "added")
            for path in old_paths - new_paths:
                self.file_change_event.emit(path, "deleted")

        self._restore_expanded_dirs(item, expanded)
        item.setExpanded(was_expanded or item.parent() is None)
        self._watch_dir(folder)
        self.folder_changed.emit(disp or str(folder))

    def _expanded_dir_paths(self, item: QTreeWidgetItem) -> set[Path]:
        result: set[Path] = set()
        for i in range(item.childCount()):
            child = item.child(i)
            if child.data(0, _IS_DIR) and child.isExpanded():
                path: Path | None = child.data(0, _PATH_ROLE)
                if path is not None:
                    result.add(path)
                result.update(self._expanded_dir_paths(child))
        return result

    def _restore_expanded_dirs(self, item: QTreeWidgetItem, expanded: set[Path]) -> None:
        for i in range(item.childCount()):
            child = item.child(i)
            if not child.data(0, _IS_DIR):
                continue
            path: Path | None = child.data(0, _PATH_ROLE)
            if path not in expanded:
                continue
            if child.childCount() == 1 and child.child(0).text(0) == _PLACEHOLDER:
                child.removeChild(child.child(0))
                disp: str = child.data(0, _DIR_ROLE) or ""
                if path is not None:
                    self._fill(child, path, disp)
            child.setExpanded(True)
            self._restore_expanded_dirs(child, expanded)

    def _find_dir_item(self, folder: Path) -> QTreeWidgetItem | None:
        def walk(item: QTreeWidgetItem) -> QTreeWidgetItem | None:
            item_path: Path | None = item.data(0, _PATH_ROLE)
            if item.data(0, _IS_DIR) and item_path == folder:
                return item
            for i in range(item.childCount()):
                found = walk(item.child(i))
                if found is not None:
                    return found
            return None

        for i in range(self.topLevelItemCount()):
            found = walk(self.topLevelItem(i))
            if found is not None:
                return found
        return None

    def navigate_to_file(self, path: Path) -> None:
        item = self._find_file_item(path)
        if item:
            self.setCurrentItem(item)
            self.scrollToItem(item)

    def _find_file_item(self, path: Path) -> QTreeWidgetItem | None:
        def walk(item: QTreeWidgetItem) -> QTreeWidgetItem | None:
            if not item.data(0, _IS_DIR):
                p: Path | None = item.data(0, _PATH_ROLE)
                if p == path:
                    return item
            else:
                item_path: Path | None = item.data(0, _PATH_ROLE)
                if item_path is not None and item_path == path.parent:
                    if item.childCount() == 1 and item.child(0).text(0) == _PLACEHOLDER:
                        disp: str = item.data(0, _DIR_ROLE) or ""
                        self._fill(item, item_path, disp)
                        item.setExpanded(True)
                    if not item.isExpanded():
                        item.setExpanded(True)
                for i in range(item.childCount()):
                    found = walk(item.child(i))
                    if found is not None:
                        return found
            return None

        for i in range(self.topLevelItemCount()):
            found = walk(self.topLevelItem(i))
            if found is not None:
                return found
        return None


# ── 文件夹标签页 ──────────────────────────────────────────────────────────────

class FolderTabBar(QTabBar):
    scrolled = Signal()

    def wheelEvent(self, event) -> None:
        delta = event.angleDelta().x() or event.angleDelta().y()
        if delta == 0:
            delta = event.pixelDelta().x() or event.pixelDelta().y()
        if delta == 0:
            event.accept()
            return

        steps = max(1, min(8, abs(delta) // 120 if abs(delta) >= 120 else 1))
        for _ in range(steps):
            button = self._scroll_button(forward=delta < 0)
            if button is None or not button.isEnabled():
                break
            button.click()
        QTimer.singleShot(0, self.scrolled.emit)
        event.accept()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        QTimer.singleShot(0, self.scrolled.emit)

    def tabLayoutChange(self) -> None:
        super().tabLayoutChange()
        QTimer.singleShot(0, self.scrolled.emit)

    def _scroll_button(self, forward: bool) -> QToolButton | None:
        buttons = [b for b in self.findChildren(QToolButton) if b.isVisible()]
        if not buttons:
            return None
        buttons.sort(key=lambda b: b.geometry().x())
        return buttons[-1] if forward else buttons[0]

    def tabSizeHint(self, index: int) -> QSize:
        size = super().tabSizeHint(index)
        if self.tabData(index) == _ADD_FOLDER_TAB:
            size.setWidth(60)
        return size

    def minimumSizeHint(self) -> QSize:
        size = super().minimumSizeHint()
        size.setWidth(0)
        return size


class FolderTabsPanel(QWidget):
    file_selected     = Signal(Path)
    path_copied       = Signal(str)
    folder_changed    = Signal(str)
    file_change_event = Signal(str, str)

    def __init__(self) -> None:
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        header = QWidget()
        header.setObjectName("folderTabsHeader")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(0)

        self.tab_bar = FolderTabBar()
        self._tab_bar_style = HiddenTabScrollButtonStyle()
        self.tab_bar.setStyle(self._tab_bar_style)
        self.tab_bar.setMovable(True)
        self.tab_bar.setDocumentMode(True)
        self.tab_bar.setExpanding(False)
        self.tab_bar.setUsesScrollButtons(True)
        self.tab_bar.currentChanged.connect(self._on_current_changed)
        self.tab_bar.tabBarClicked.connect(self._on_tab_clicked)
        self.tab_bar.tabMoved.connect(self._on_tab_moved)
        self.tab_bar.setMinimumWidth(0)
        header_layout.addWidget(self.tab_bar, 1)

        self._tab_scrollbar = QScrollBar(Qt.Orientation.Horizontal)
        self._tab_scrollbar.setObjectName("tabScrollBar")
        self._tab_scrollbar.setSingleStep(30)
        self._tab_scrollbar.setFixedHeight(16)
        self._tab_scrollbar.hide()
        self._tab_scrollbar.valueChanged.connect(self._on_tab_scrollbar_moved)
        self.tab_bar.scrolled.connect(self._update_tab_scrollbar)

        self.stack = QStackedWidget()
        self.stack.setMinimumWidth(0)
        self._tab_widgets: list[FolderTree] = []
        self._last_real_index = -1
        self._add_control_tabs()

        layout.addWidget(header)
        layout.addWidget(self._tab_scrollbar)
        layout.addWidget(self.stack, 1)
        self._last_dir = str(Path.home())

        sc = QShortcut(QKeySequence("Ctrl+W"), self)
        sc.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        sc.activated.connect(self.close_current_tab)

    def close_current_tab(self) -> None:
        idx = self.tab_bar.currentIndex()
        if self._is_add_tab(idx) or idx < 0 or idx >= len(self._tab_widgets):
            return
        self._close(self._tab_widgets[idx])

    def _add_control_tabs(self) -> None:
        idx = self.tab_bar.addTab("+")
        self.tab_bar.setTabData(idx, _ADD_FOLDER_TAB)
        self.tab_bar.setTabToolTip(idx, "添加文件夹 (Ctrl+O)")

    def _remove_control_tabs(self) -> None:
        for idx in range(self.tab_bar.count()):
            if self.tab_bar.tabData(idx) == _ADD_FOLDER_TAB:
                self.tab_bar.removeTab(idx)
                return

    def _is_add_tab(self, idx: int) -> bool:
        return idx >= 0 and self.tab_bar.tabData(idx) == _ADD_FOLDER_TAB

    def _tab_scroll_offset(self) -> int:
        if self.tab_bar.count() == 0:
            return 0
        return max(0, -self.tab_bar.tabRect(0).x())

    def _update_tab_scrollbar(self) -> None:
        total_w = sum(self.tab_bar.tabRect(i).width() for i in range(self.tab_bar.count()))
        visible_w = self.tab_bar.width()
        max_scroll = max(0, total_w - visible_w)

        self._tab_scrollbar.blockSignals(True)
        self._tab_scrollbar.setRange(0, max_scroll)
        self._tab_scrollbar.setPageStep(visible_w)
        self._tab_scrollbar.setValue(self._tab_scroll_offset())
        self._tab_scrollbar.blockSignals(False)
        self._tab_scrollbar.setVisible(max_scroll > 0)

    def _on_tab_scrollbar_moved(self, value: int) -> None:
        for _ in range(100):
            current = self._tab_scroll_offset()
            delta = value - current
            if abs(delta) <= 3:
                break
            forward = delta > 0
            buttons = sorted(
                [b for b in self.tab_bar.findChildren(QToolButton)],
                key=lambda b: b.geometry().x(),
            )
            btn = (buttons[-1] if forward else buttons[0]) if buttons else None
            if btn is None or not btn.isEnabled():
                break
            prev = current
            btn.click()
            if self._tab_scroll_offset() == prev:
                break

    def _on_current_changed(self, idx: int) -> None:
        if self._is_add_tab(idx):
            return
        if 0 <= idx < self.stack.count():
            self._last_real_index = idx
            self.stack.setCurrentIndex(idx)
        QTimer.singleShot(0, self._update_tab_scrollbar)

    def _on_tab_clicked(self, idx: int) -> None:
        if self._is_add_tab(idx):
            opened = self.add_folder()
            if not opened and 0 <= self._last_real_index < len(self._tab_widgets):
                self.tab_bar.setCurrentIndex(self._last_real_index)

    def _on_tab_moved(self, from_idx: int, to_idx: int) -> None:
        QTimer.singleShot(0, self._normalize_tab_order)

    def _normalize_tab_order(self) -> None:
        self._remove_control_tabs()
        self._add_control_tabs()

        ordered: list[FolderTree] = []
        for idx in range(self.tab_bar.count()):
            data = self.tab_bar.tabData(idx)
            if isinstance(data, FolderTree):
                ordered.append(data)

        if ordered != self._tab_widgets:
            current = self.stack.currentWidget()
            self._tab_widgets = ordered
            for widget in ordered:
                self.stack.removeWidget(widget)
            for widget in ordered:
                self.stack.addWidget(widget)
            if current in ordered:
                self.stack.setCurrentWidget(current)
                self._last_real_index = ordered.index(current)

        if 0 <= self._last_real_index < len(self._tab_widgets):
            self.tab_bar.setCurrentIndex(self._last_real_index)

    def open_path(self, path_str: str) -> None:
        p = Path(path_str)
        if p.is_dir():
            self._open(p)

    def open_paths(self) -> list[str]:
        result = []
        for tree in self._tab_widgets:
            if isinstance(tree, FolderTree) and tree.topLevelItemCount() > 0:
                disp: str = tree.topLevelItem(0).data(0, _DIR_ROLE) or ""
                if disp:
                    result.append(disp)
        return result

    def add_folder(self) -> bool:
        folder = QFileDialog.getExistingDirectory(self, "选择文件夹", self._last_dir)
        if not folder:
            return False
        self._last_dir = folder
        self._open(Path(folder))
        return True

    def _open(self, p: Path) -> None:
        display = str(p).replace("\\", "/")
        tree = FolderTree()
        tree.file_selected.connect(self.file_selected)
        tree.path_copied.connect(self.path_copied)
        tree.folder_changed.connect(self.folder_changed)
        tree.file_change_event.connect(self.file_change_event)

        self._remove_control_tabs()
        idx = self.tab_bar.addTab(p.name)
        self.tab_bar.setTabData(idx, tree)
        self._tab_widgets.append(tree)
        self.stack.addWidget(tree)
        self.tab_bar.setTabToolTip(idx, display)
        self._attach_close_btn(idx, tree)
        self._add_control_tabs()
        self.tab_bar.setCurrentIndex(idx)
        tree.load_folder(p, display)

    def _attach_close_btn(self, idx: int, tree: FolderTree) -> None:
        btn = QPushButton("×")
        btn.setObjectName("tabCloseBtn")
        btn.setFlat(True)
        btn.setFixedSize(18, 18)
        btn.setToolTip("关闭")
        btn.clicked.connect(lambda: self._close(tree))
        self.tab_bar.setTabButton(idx, QTabBar.ButtonPosition.RightSide, btn)

    def _close(self, tree: FolderTree) -> None:
        try:
            idx = self._tab_widgets.index(tree)
        except ValueError:
            return
        if idx >= 0:
            self._tab_widgets.pop(idx)
            self.tab_bar.removeTab(idx)
            self.stack.removeWidget(tree)
            tree.deleteLater()
            if self._tab_widgets:
                self._last_real_index = min(idx, len(self._tab_widgets) - 1)
                self.tab_bar.setCurrentIndex(self._last_real_index)
            else:
                self._last_real_index = -1

    def navigate_to_file(self, path: Path) -> None:
        for tree in self._tab_widgets:
            root: Path | None = tree._root_path
            if root is not None:
                try:
                    path.relative_to(root)
                except ValueError:
                    continue
                tree.navigate_to_file(path)
                idx = self._tab_widgets.index(tree)
                if idx != self.tab_bar.currentIndex():
                    self.tab_bar.setCurrentIndex(idx)
                return
