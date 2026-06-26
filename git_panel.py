"""Git 面板：源代码管理侧边栏（VS Code 风格）。

布局：
  ┌────────────────────────────────────┐
  │ Repo: [▼ /path/to/repo  ⏎ ] [⟳]   │  ← repo 选择器 + 刷新
  │ Branch: main · ±3 staged           │  ← 状态头
  ├────────────────────────────────────┤
  │ ▼ STAGED CHANGES (3)               │  ← 可折叠分组
  │   ☑ M  src/foo.py                  │
  │   ☑ A  README.md                   │
  │ ▼ CHANGES (2)                      │
  │   ☐ M  src/bar.py                  │
  │   ☐ ?  new_file.py                 │
  ├────────────────────────────────────┤
  │ Message: ┌────────────────────┐ ⏎  │  ← 多行 commit 消息
  │          │                    │    │
  │          │                    │    │
  │          └────────────────────┘    │
  │ [Commit] [Discard] [Amend]         │
  └────────────────────────────────────┘

实现说明
--------
- 阶段 3 只搭骨架：占位 widget + repo 切换 + 基本布局
- 阶段 4 填文件状态列表（最复杂）
- 阶段 5 加 diff 视图（在右侧 PreviewPane 显示）
- 阶段 6 接 commit 流程
"""
from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QComboBox,
    QPlainTextEdit, QFrame, QToolButton, QFileDialog, QMessageBox,
    QSizePolicy, QSpacerItem, QSplitter, QButtonGroup,
)
from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtGui import QFont, QShortcut, QKeySequence

from git_backend import GitBackend, FileStatus, FileDiff
from git_file_list import FileList, GroupHeader
from git_log_list import CommitList
from diff_view import DiffView
from theme import BG, BG_ELEV, BG_HOVER, BORDER, BORDER_SOFT, FG, FG_DIM, _sidebar_icon


class RepoBar(QWidget):
    """顶部：repo 选择器 + 刷新按钮。"""
    repo_changed = Signal(Path)
    refresh_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 4)
        layout.setSpacing(6)

        self._combo = QComboBox()
        self._combo.setEditable(True)  # 允许直接输入路径
        self._combo.lineEdit().setPlaceholderText("选择 git 仓库…")
        self._combo.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self._combo.currentTextChanged.connect(self._on_text_changed)

        self._browse_btn = QToolButton()
        self._browse_btn.setText("📂")
        self._browse_btn.setToolTip("浏览文件夹…")
        self._browse_btn.setFixedSize(28, 28)
        self._browse_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._browse_btn.clicked.connect(self._browse)

        self._refresh_btn = QToolButton()
        self._refresh_btn.setText("⟳")
        self._refresh_btn.setToolTip("刷新 (F5)")
        self._refresh_btn.setFixedSize(28, 28)
        self._refresh_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._refresh_btn.clicked.connect(self.refresh_requested.emit)

        layout.addWidget(self._combo, 1)
        layout.addWidget(self._browse_btn)
        layout.addWidget(self._refresh_btn)

    def add_repo(self, path: Path) -> None:
        p = str(Path(path).resolve())
        if self._combo.findText(p) < 0:
            self._combo.addItem(p)
        self._combo.setCurrentText(p)

    def current_repo(self) -> Path | None:
        text = self._combo.currentText().strip()
        if not text:
            return None
        p = Path(text)
        return p if p.exists() else None

    def _on_text_changed(self, text: str) -> None:
        p = Path(text) if text else None
        if p and p.exists() and (p / ".git").exists():
            self.repo_changed.emit(p)

    def _browse(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "选择 Git 仓库")
        if path:
            self.add_repo(Path(path))
            self.repo_changed.emit(Path(path))


class BranchLabel(QWidget):
    """分支名 + staged count + 改动数 状态行。"""
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setSpacing(8)

        self._branch_lbl = QLabel("(未选择仓库)")
        self._branch_lbl.setStyleSheet(f"color: {FG}; font-weight: bold; font-size: 13px;")

        self._counts_lbl = QLabel("")
        self._counts_lbl.setStyleSheet(f"color: {FG_DIM}; font-size: 12px;")

        layout.addWidget(self._branch_lbl)
        layout.addWidget(self._counts_lbl, 1)

    def update_info(self, branch: str | None, staged: int, unstaged: int, untracked: int) -> None:
        if branch is None:
            self._branch_lbl.setText("(未选择仓库)")
            self._counts_lbl.setText("")
        else:
            self._branch_lbl.setText(f"⎇ {branch}")
            parts = []
            if staged:
                parts.append(f"+{staged} staged")
            if unstaged:
                parts.append(f"±{unstaged} changes")
            if untracked:
                parts.append(f"?{untracked} untracked")
            self._counts_lbl.setText(" · ".join(parts) if parts else "clean working tree")


class ViewTabBar(QWidget):
    """git panel 顶部的视图切换条：Changes / History。

    类似 VS Code 侧边栏顶部的下拉/标签切换。
    """
    tab_changed = Signal(str)  # "changes" | "history"

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("gitViewTabBar")
        self.setFixedHeight(30)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 0, 8, 0)
        layout.setSpacing(0)

        self._btns: dict[str, QPushButton] = {}
        self._group = QButtonGroup(self)
        self._group.setExclusive(True)

        for key, label in [("changes", "Changes"), ("history", "History")]:
            btn = QPushButton(label)
            btn.setCheckable(True)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setObjectName("gitViewTabBtn")
            btn.setStyleSheet(f"""
                QPushButton {{
                    background: transparent; color: {FG_DIM};
                    border: none; border-bottom: 2px solid transparent;
                    padding: 4px 14px; font-size: 12px;
                }}
                QPushButton:checked {{
                    color: {FG}; border-bottom: 2px solid {FG};
                }}
                QPushButton:hover:!checked {{ color: {FG}; }}
            """)
            btn.clicked.connect(lambda _checked=False, k=key: self.tab_changed.emit(k))
            self._btns[key] = btn
            self._group.addButton(btn)
            layout.addWidget(btn)

        layout.addStretch(1)

        # 默认 Changes
        self._btns["changes"].setChecked(True)

    def set_active(self, key: str) -> None:
        if key in self._btns:
            self._btns[key].setChecked(True)


class FileListPlaceholder(QWidget):
    """保留旧占位 API，但实际指向新 FileList。

    阶段 4 用真列表替换。"""
    file_selected = Signal(str, bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        self._placeholder = QLabel("(无文件改动)")
        self._placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._placeholder.setStyleSheet(f"color: {FG_DIM}; font-size: 12px; padding: 20px;")
        layout.addWidget(self._placeholder, 1)
        self.setStyleSheet(f"background: {BG};")


class CommitBox(QWidget):
    """底部 commit 消息 + 按钮。"""
    commit_requested = Signal(str)
    discard_requested = Signal()
    message_changed = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        self._msg = QPlainTextEdit()
        self._msg.setPlaceholderText("Message (Ctrl+Enter to commit)")
        self._msg.setMaximumHeight(80)
        self._msg.setStyleSheet(f"""
            QPlainTextEdit {{
                background: {BG_ELEV}; color: {FG}; border: 1px solid {BORDER_SOFT};
                border-radius: 3px; padding: 6px;
                font-family: 'Cascadia Code', 'Consolas', 'Courier New', monospace;
                font-size: 12px;
            }}
            QPlainTextEdit:focus {{ border-color: {FG}; }}
        """)
        self._msg.textChanged.connect(
            lambda: (
                self.message_changed.emit(self.message()),
                self._refresh_buttons(),
            )
        )
        # Ctrl+Enter → commit
        sc = QShortcut(QKeySequence("Ctrl+Return"), self._msg)
        sc.setContext(Qt.ShortcutContext.WidgetShortcut)
        sc.activated.connect(self._emit_commit)
        sc2 = QShortcut(QKeySequence("Ctrl+Enter"), self._msg)
        sc2.setContext(Qt.ShortcutContext.WidgetShortcut)
        sc2.activated.connect(self._emit_commit)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(6)

        self._commit_btn = QPushButton("Commit")
        self._commit_btn.setEnabled(False)
        self._commit_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._commit_btn.setStyleSheet(f"""
            QPushButton {{
                background: {FG}; color: {BG}; border: none; border-radius: 3px;
                padding: 6px 16px; font-weight: bold; font-size: 12px;
            }}
            QPushButton:disabled {{ background: {BG_ELEV}; color: {FG_DIM}; }}
            QPushButton:hover:!disabled {{ background: {FG_DIM}; color: {BG}; }}
        """)
        self._commit_btn.clicked.connect(self._emit_commit)

        self._discard_btn = QPushButton("Discard")
        self._discard_btn.setEnabled(False)
        self._discard_btn.setToolTip("放弃工作区文件改动（危险，需二次确认）")
        self._discard_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._discard_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent; color: {FG_DIM}; border: 1px solid {BORDER_SOFT};
                border-radius: 3px; padding: 6px 12px; font-size: 12px;
            }}
            QPushButton:disabled {{ color: {BG_HOVER}; border-color: {BG_HOVER}; }}
            QPushButton:hover:!disabled {{ color: #f4212e; border-color: #f4212e; }}
        """)
        self._discard_btn.clicked.connect(self.discard_requested.emit)

        btn_row.addWidget(self._commit_btn)
        btn_row.addWidget(self._discard_btn)
        btn_row.addStretch(1)

        layout.addWidget(self._msg)
        layout.addLayout(btn_row)

    def set_message(self, text: str) -> None:
        self._msg.setPlainText(text)

    def message(self) -> str:
        return self._msg.toPlainText().strip()

    def clear_message(self) -> None:
        self._msg.clear()

    def set_can_commit(self, enabled: bool) -> None:
        """切换 commit 按钮可用性（同时刷新 commit/draft 按钮）。"""
        self._can_commit_external = enabled
        self._refresh_buttons()

    def set_can_discard(self, enabled: bool) -> None:
        """切换 Discard 按钮可用性（仅当工作区有改动时）。"""
        self._can_discard_external = enabled
        self._refresh_buttons()

    def _refresh_buttons(self) -> None:
        has_msg = bool(self.message())
        can_commit = getattr(self, "_can_commit_external", False) and has_msg
        self._commit_btn.setEnabled(can_commit)
        self._discard_btn.setEnabled(getattr(self, "_can_discard_external", False))

    def _emit_commit(self) -> None:
        text = self.message()
        if text:
            self.commit_requested.emit(text)


# ── 主面板 ────────────────────────────────────────────────────────────────


class GitPanel(QWidget):
    """git 源代码管理侧边栏。

    信号：
      path_copied(str)  — 复制 commit hash / 路径
      repo_changed(str)  — 当前 repo 路径变了
    """
    path_copied = Signal(str)
    repo_changed = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._backend: GitBackend | None = None
        self._build_ui()
        self._wire()

    # ── 布局 ──

    def _build_ui(self) -> None:
        # 顶部 repo + 状态（全宽）
        top = QWidget()
        tl = QVBoxLayout(top)
        tl.setContentsMargins(0, 0, 0, 0)
        tl.setSpacing(0)
        self.repo_bar = RepoBar()
        self.branch_label = BranchLabel()
        sep1 = QFrame()
        sep1.setFrameShape(QFrame.Shape.HLine)
        sep1.setStyleSheet(f"background: {BORDER_SOFT}; max-height: 1px;")
        tl.addWidget(self.repo_bar)
        tl.addWidget(self.branch_label)
        tl.addWidget(sep1)

        # 视图切换条 (Changes / History)
        self.view_tabs = ViewTabBar()

        # ── Changes 视图：file list + commit box ──
        self.file_list = FileList()
        sep2 = QFrame()
        sep2.setFrameShape(QFrame.Shape.HLine)
        sep2.setStyleSheet(f"background: {BORDER_SOFT}; max-height: 1px;")
        self.commit_box = CommitBox()

        changes_page = QWidget()
        cpl = QVBoxLayout(changes_page)
        cpl.setContentsMargins(0, 0, 0, 0)
        cpl.setSpacing(0)
        cpl.addWidget(self.file_list, 1)
        cpl.addWidget(sep2)
        cpl.addWidget(self.commit_box)

        # ── History 视图：commit list ──
        self.commit_list = CommitList()

        history_page = QWidget()
        hpl = QVBoxLayout(history_page)
        hpl.setContentsMargins(0, 0, 0, 0)
        hpl.setSpacing(0)
        hpl.addWidget(self.commit_list, 1)

        # left 容器：tab 条 + stack
        from PySide6.QtWidgets import QStackedWidget
        self._left_stack = QStackedWidget()
        self._left_stack.addWidget(changes_page)   # 0
        self._left_stack.addWidget(history_page)   # 1

        left = QWidget()
        ll = QVBoxLayout(left)
        ll.setContentsMargins(0, 0, 0, 0)
        ll.setSpacing(0)
        ll.addWidget(self.view_tabs)
        ll.addWidget(self._left_stack, 1)

        # 右：diff 视图
        self.diff_view = DiffView()

        # 横向 splitter
        self._splitter = QSplitter(Qt.Orientation.Horizontal)
        self._splitter.setHandleWidth(1)
        self._splitter.setChildrenCollapsible(False)
        self._splitter.addWidget(left)
        self._splitter.addWidget(self.diff_view)
        self._splitter.setSizes([420, 480])

        # 总布局
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        root.addWidget(top)
        root.addWidget(self._splitter, 1)

        self.setStyleSheet(f"background: {BG};")

    def _wire(self) -> None:
        self.repo_bar.repo_changed.connect(self._on_repo_changed)
        self.repo_bar.refresh_requested.connect(self.refresh)
        self.commit_box.commit_requested.connect(self._on_commit)
        self.commit_box.discard_requested.connect(self._on_discard)
        self.commit_box.message_changed.connect(self._on_message_changed)
        # file list: 行点击 → 内部 show_diff；checkbox 变 → 暂存/取消
        self.file_list.file_selected.connect(self._on_file_clicked)
        self.file_list.selection_changed.connect(self._on_selection_changed)
        # tab 切换
        self.view_tabs.tab_changed.connect(self._on_tab_changed)
        # commit 历史 → 显示该 commit 的 diff
        self.commit_list.commit_selected.connect(self._on_commit_history_clicked)

    # ── 公共 API ──

    def set_repo(self, path: Path) -> None:
        """切换到指定 repo（从外部调用，例如文件树切换）。"""
        p = Path(path).resolve()
        self.repo_bar.add_repo(p)
        self._set_backend(p)

    def auto_pick_repo(self, candidates: list[str]) -> None:
        """从候选文件夹中找第一个包含 .git 的，作为初始 repo。"""
        if self._backend is not None:
            return  # 已选过就不动
        for s in candidates:
            root = GitBackend.find_repo_root(Path(s))
            if root:
                self.set_repo(root)
                return
        # 没找到 .git，至少显示当前文件夹
        if candidates:
            self.repo_bar.add_repo(Path(candidates[0]))

    def refresh(self) -> None:
        """刷新当前 repo 状态（status + 分支 + commit 按钮可用性 + history）。"""
        if self._backend is None:
            return
        statuses = self._backend.status()
        self.file_list.set_repo(self._backend.repo)
        self.file_list.populate(statuses)
        self._update_branch_label(statuses)
        self._update_commit_button()
        # 顺手刷新历史（轻量）
        try:
            commits = self._backend.log(20)
            self.commit_list.populate(commits)
        except Exception:
            self.commit_list.populate([])
        self.repo_changed.emit(str(self._backend.repo))

    # ── 内部 ──

    def _on_repo_changed(self, path: Path) -> None:
        self._set_backend(path)

    def _on_selection_changed(self, _selected: set[str]) -> None:
        """用户改了 checkbox 勾选 → 同步到 git（add / reset）。"""
        if self._backend is None:
            return
        checked = self.file_list.selected_paths()
        already_staged = self.file_list.staged_paths()
        to_add = checked - already_staged
        to_reset = already_staged - checked
        if to_add:
            self._backend.add(sorted(to_add))
        if to_reset:
            self._backend.reset(sorted(to_reset))
        if to_add or to_reset:
            # 刷新让 status 跟上（重新算 staged 状态）
            self.refresh()

    def _set_backend(self, path: Path) -> None:
        if not (path / ".git").exists():
            self.branch_label.update_info(None, 0, 0, 0)
            self.file_list.clear()
            self._backend = None
            self.commit_box.set_can_commit(False)
            self.repo_changed.emit(str(path))
            return
        self._backend = GitBackend(path)
        self.refresh()

    def _update_branch_label(self, statuses: list[FileStatus] | None = None) -> None:
        if self._backend is None or not self._backend.is_valid_repo():
            self.branch_label.update_info(None, 0, 0, 0)
            return
        branch = self._backend.current_branch()
        if statuses is None:
            statuses = self._backend.status()
        staged = sum(1 for s in statuses if s.is_staged)
        unstaged = sum(1 for s in statuses if s.is_dirty and not s.is_staged)
        untracked = sum(1 for s in statuses if s.is_untracked)
        self.branch_label.update_info(branch, staged, unstaged, untracked)

    def _update_commit_button(self) -> None:
        """根据 staged 文件数 + 消息是否为空，更新 commit 按钮。"""
        can_commit = bool(self.file_list.staged_paths())
        # Discard 只在有工作区改动时启用（changes + untracked）
        has_workdir_changes = bool(self.file_list._changes_rows or self.file_list._untracked_rows)
        self.commit_box.set_can_commit(can_commit)
        self.commit_box.set_can_discard(has_workdir_changes)

    def _on_message_changed(self, _msg: str) -> None:
        """消息变化时刷新按钮可用性（消息非空 AND staged 才可 commit）。"""
        # 重新调用 _update_commit_button 让消息参与判断
        self._update_commit_button()

    def _on_commit(self, message: str) -> None:
        """执行 git commit。"""
        if self._backend is None:
            self._show_error("未选择仓库")
            return
        if not message.strip():
            self._show_error("Commit message 为空")
            return
        staged = self.file_list.staged_paths()
        if not staged:
            self._show_error("没有 staged 文件，无法 commit")
            return
        ok, sha, err = self._backend.commit(message)
        if ok:
            short_sha = sha[:7] if sha else ""
            self.commit_box.clear_message()
            self.path_copied.emit(f"✓ 提交成功 {short_sha}\n{message.splitlines()[0]}")
            self.refresh()
        else:
            self._show_error(f"Commit 失败：{err or '未知错误'}")

    def _on_discard(self) -> None:
        """放弃工作区所有改动（changes + untracked），需二次确认。"""
        if self._backend is None:
            return
        paths = [r.status().path for r in self.file_list._changes_rows + self.file_list._untracked_rows]
        if not paths:
            return
        preview = "\n".join(f"  • {p}" for p in paths[:8])
        if len(paths) > 8:
            preview += f"\n  …以及 {len(paths) - 8} 个文件"
        reply = QMessageBox.warning(
            self,
            "放弃改动？",
            f"以下文件的本地改动将被永久丢弃（无法恢复）：\n\n{preview}\n\n确定继续？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        ok, err = self._backend.discard(paths)
        if ok:
            self.path_copied.emit(f"✓ 已放弃 {len(paths)} 个文件的改动")
            self.refresh()
        else:
            self._show_error(f"放弃失败：{err or '未知错误'}")

    def _show_error(self, msg: str) -> None:
        QMessageBox.warning(self, "Git 错误", msg)

    def _on_file_clicked(self, path: str, staged: bool) -> None:
        """用户在文件列表点了一行 → 显示 diff。"""
        self._show_diff_for(path, staged)

    def _show_diff_for(self, path: str, staged: bool) -> None:
        if self._backend is None:
            self.diff_view.show_message("(未选择仓库)")
            return
        try:
            diff = self._backend.diff(path, staged=staged)
        except Exception as e:
            self.diff_view.show_message(f"diff 失败: {e}")
            return
        if diff.is_binary:
            self.diff_view.show_binary(self._backend.repo, diff)
        elif not diff.hunks:
            self.diff_view.show_message("(无 diff — 文件未改动)")
        else:
            self.diff_view.show_diff(self._backend.repo, diff)

    def _on_tab_changed(self, key: str) -> None:
        """Changes / History 切换。"""
        if key == "changes":
            self._left_stack.setCurrentIndex(0)
        elif key == "history":
            self._left_stack.setCurrentIndex(1)
            # 切到 history 时确保最新
            if self._backend is not None:
                try:
                    self.commit_list.populate(self._backend.log(20))
                except Exception:
                    self.commit_list.populate([])

    def _on_commit_history_clicked(self, sha: str) -> None:
        """用户点了一条 commit → 显示该 commit 改动的总览 diff。

        VS Code 在 Sources Control 里点 commit 会显示该 commit 的所有文件。
        我们用 ``git show --stat`` 风格，diff header 显示列表，diff body 显示完整 diff。
        """
        if self._backend is None:
            return
        # 显示 commit 元信息 + stat
        commits = self._backend.log(50)
        meta = next((c for c in commits if c.sha == sha), None)
        if meta is None:
            self.diff_view.show_message(f"(找不到 commit {sha[:7]})")
            return
        # 用 --stat 拿改动的文件列表
        try:
            stat = self._backend._run("show", "--stat", "--format=", sha, "--")
        except Exception:
            self.diff_view.show_message("(读取 commit 失败)")
            return
        stat_text = stat.stdout.strip()
        # 用 diff_range(commit^, commit, each_file) 拿完整 diff
        # 简单做法：先取该 commit 改动的文件列表，挨个 diff 然后拼起来
        files_changed = []
        for line in stat_text.splitlines():
            # 形如 " foo.py | 5 +++--"
            m = line.strip().split(" | ")
            if len(m) == 2 and m[0]:
                files_changed.append(m[0])

        # 构造合成 diff
        from git_backend import FileDiff, Hunk
        agg = FileDiff(path=meta.summary)
        agg.hunks.append(Hunk(
            old_start=0, old_count=0, new_start=0, new_count=0,
            lines=[(" ", f"Commit:  {meta.short_sha} — {meta.summary}"),
                   (" ", f"Author:  {meta.author}"),
                   (" ", f"Date:    {meta.date}"),
                   (" ", ""),
                   (" ", "Files changed:")],
        ))
        for fc in files_changed:
            agg.hunks.append(Hunk(
                old_start=0, old_count=0, new_start=0, new_count=0,
                lines=[(" ", f"  • {fc}")],
            ))
        agg.hunks.append(Hunk(
            old_start=0, old_count=0, new_start=0, new_count=0,
            lines=[(" ", ""), (" ", "(单文件 diff 请到 Changes 视图选择对应文件查看)")],
        ))
        # 把 stat 解析塞到 header
        # 复用 show_diff 但用占位
        self.diff_view._header.setText(f" {meta.short_sha}  {meta.summary}    {meta.author}")
        # 直接 populate 静态展示
        text_lines = [
            f" {meta.short_sha}  {meta.summary}",
            f" Author: {meta.author}",
            f" Date:   {meta.date}",
            "",
            f" Files changed ({len(files_changed)}):",
        ] + [f"   • {f}" for f in files_changed] + [
            "",
            " (提示：选择文件后到 Changes 视图查看单文件 diff)",
        ]
        for side in (self.diff_view._left, self.diff_view._right):
            side.clear()
            cur = side.textCursor()
            cur.beginEditBlock()
            for line in text_lines:
                cur.insertText(line + "\n")
            cur.endEditBlock()
