"""左侧侧边栏：图标条 + 文件树/历史/设置/git 切换。"""
from pathlib import Path

from PySide6.QtWidgets import QWidget, QHBoxLayout, QVBoxLayout, QStackedWidget, QToolButton
from PySide6.QtCore import Qt, Signal

from tree import FolderTabsPanel
from history import HistoryPanel
from settings_panel import SettingsPanel
from git_panel import GitPanel
from theme import _sidebar_icon


class LeftPanel(QWidget):
    file_selected  = Signal(Path)
    path_copied    = Signal(str)
    folder_changed = Signal(str)
    repo_changed   = Signal(str)   # 当前选中的 repo 路径

    def __init__(self):
        super().__init__()
        outer = QHBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        strip = QWidget()
        strip.setObjectName("sidebarStrip")
        strip.setFixedWidth(40)
        sl = QVBoxLayout(strip)
        sl.setContentsMargins(4, 10, 4, 10)
        sl.setSpacing(6)
        sl.setAlignment(Qt.AlignmentFlag.AlignTop)

        self._tree_icons = _sidebar_icon("FOLDER")
        self._hist_icons = _sidebar_icon("HISTORY")
        self._set_icons = _sidebar_icon("ADJUSTMENTS")
        self._git_icons = _sidebar_icon("GIT_BRANCH")

        self._tree_btn = QToolButton()
        self._tree_btn.setObjectName("sidebarBtn")
        self._tree_btn.setIcon(self._tree_icons[1])  # black icon on white bg
        self._tree_btn.setToolTip("文件树")
        self._tree_btn.setCheckable(True)
        self._tree_btn.setChecked(True)
        self._tree_btn.setFixedSize(32, 32)
        self._tree_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._tree_btn.clicked.connect(self._show_tree)

        self._hist_btn = QToolButton()
        self._hist_btn.setObjectName("sidebarBtn")
        self._hist_btn.setIcon(self._hist_icons[0])  # white icon on dark bg
        self._hist_btn.setToolTip("更改历史")
        self._hist_btn.setCheckable(True)
        self._hist_btn.setFixedSize(32, 32)
        self._hist_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._hist_btn.clicked.connect(self._show_history)

        sl.addWidget(self._tree_btn)
        sl.addWidget(self._hist_btn)

        self._git_btn = QToolButton()
        self._git_btn.setObjectName("sidebarBtn")
        self._git_btn.setIcon(self._git_icons[0])
        self._git_btn.setToolTip("源代码管理 (Git)")
        self._git_btn.setCheckable(True)
        self._git_btn.setFixedSize(32, 32)
        self._git_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._git_btn.clicked.connect(self._show_git)
        sl.addWidget(self._git_btn)

        self._set_btn = QToolButton()
        self._set_btn.setObjectName("sidebarBtn")
        self._set_btn.setIcon(self._set_icons[0])
        self._set_btn.setToolTip("设置")
        self._set_btn.setCheckable(True)
        self._set_btn.setFixedSize(32, 32)
        self._set_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._set_btn.clicked.connect(self._show_settings)
        sl.addWidget(self._set_btn)
        sl.addStretch(1)

        self._stack = QStackedWidget()
        self.folder_panel = FolderTabsPanel()
        self.history_panel = HistoryPanel()
        self.git_panel = GitPanel()
        self.settings_panel = SettingsPanel()
        self._stack.addWidget(self.folder_panel)
        self._stack.addWidget(self.history_panel)
        self._stack.addWidget(self.git_panel)
        self._stack.addWidget(self.settings_panel)

        outer.addWidget(strip)
        outer.addWidget(self._stack, 1)

        self.folder_panel.file_selected.connect(self.file_selected)
        self.folder_panel.path_copied.connect(self.path_copied)
        self.folder_panel.folder_changed.connect(self.folder_changed)
        self.folder_panel.file_change_event.connect(self.history_panel.add_event)

        self.history_panel.file_selected.connect(self.file_selected)
        self.history_panel.path_copied.connect(self.path_copied)

        # git panel: 文件 diff 通过 preview 显示
        self.git_panel.path_copied.connect(self.path_copied)
        self.git_panel.repo_changed.connect(self.repo_changed)

        # 文件夹切换时通知 git 面板（如果它当前是显示的，让它跟新 repo）
        self.folder_panel.folder_changed.connect(self._on_folder_changed_for_git)

    def _on_folder_changed_for_git(self, path: str) -> None:
        """如果用户在文件树面板切换文件夹，且该路径在 git 仓库内，自动同步到 git 面板。"""
        from git_backend import GitBackend
        root = GitBackend.find_repo_root(Path(path))
        if root:
            self.git_panel.set_repo(root)

    def _show_tree(self) -> None:
        self._stack.setCurrentIndex(0)
        self._tree_btn.setChecked(True)
        self._tree_btn.setIcon(self._tree_icons[1])   # black on white
        self._hist_btn.setChecked(False)
        self._hist_btn.setIcon(self._hist_icons[0])    # white on dark
        self._git_btn.setChecked(False)
        self._git_btn.setIcon(self._git_icons[0])
        self._set_btn.setChecked(False)
        self._set_btn.setIcon(self._set_icons[0])

    def _show_history(self) -> None:
        self._stack.setCurrentIndex(1)
        self._tree_btn.setChecked(False)
        self._tree_btn.setIcon(self._tree_icons[0])    # white on dark
        self._hist_btn.setChecked(True)
        self._hist_btn.setIcon(self._hist_icons[1])    # black on white
        self._git_btn.setChecked(False)
        self._git_btn.setIcon(self._git_icons[0])
        self._set_btn.setChecked(False)
        self._set_btn.setIcon(self._set_icons[0])

    def _show_git(self) -> None:
        self._stack.setCurrentIndex(2)
        self._tree_btn.setChecked(False)
        self._tree_btn.setIcon(self._tree_icons[0])
        self._hist_btn.setChecked(False)
        self._hist_btn.setIcon(self._hist_icons[0])
        self._git_btn.setChecked(True)
        self._git_btn.setIcon(self._git_icons[1])    # black on white
        self._set_btn.setChecked(False)
        self._set_btn.setIcon(self._set_icons[0])
        # 切到 git 面板时，如果还没有 repo，尝试用当前打开的文件夹
        self.git_panel.auto_pick_repo(self.folder_panel.open_paths())

    def _show_settings(self) -> None:
        self._stack.setCurrentIndex(3)
        self._tree_btn.setChecked(False)
        self._tree_btn.setIcon(self._tree_icons[0])
        self._hist_btn.setChecked(False)
        self._hist_btn.setIcon(self._hist_icons[0])
        self._git_btn.setChecked(False)
        self._git_btn.setIcon(self._git_icons[0])
        self._set_btn.setChecked(True)
        self._set_btn.setIcon(self._set_icons[1])

    @property
    def _last_dir(self) -> str:
        return self.folder_panel._last_dir

    @_last_dir.setter
    def _last_dir(self, val: str) -> None:
        self.folder_panel._last_dir = val

    def open_paths(self) -> list[str]:
        return self.folder_panel.open_paths()

    def open_path(self, path_str: str) -> None:
        self.folder_panel.open_path(path_str)

    def add_folder(self) -> bool:
        return self.folder_panel.add_folder()

    def navigate_to_file(self, path: Path) -> None:
        self.folder_panel.navigate_to_file(path)
