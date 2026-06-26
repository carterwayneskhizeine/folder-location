"""Git 文件状态列表组件。

布局（VS Code Source Control 风格）：
  ▼ STAGED CHANGES (3)             ← 可点击折叠标题
    ☑ M  src/foo.py              +12 −4
    ☑ A  README.md               +15
    ☑ D  old.txt                 −20
  ▼ CHANGES (2)                     ← 工作区未暂存
    ☐ M  src/bar.py              +3 −1
    ☐ ?  new_file.py             (untracked)
  ▼ UNTRACKED FILES (1)
    ☐ ?  scratch.py              +add

设计要点
--------
- 用 ``QWidget`` + 自定义 paintEvent 而非 ``QListWidget``（需要三态 checkbox）
- checkbox 状态独立于文件状态（用户可手动选择要暂存哪些）
- 折叠/展开状态保存在实例属性，会话恢复时一起恢复
- 异步刷新：在后台线程跑 ``backend.status()``，完成后切回主线程更新
"""
from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QCheckBox, QPushButton,
    QSizePolicy, QApplication,
)
from PySide6.QtCore import Qt, Signal, QPropertyAnimation, QEasingCurve
from PySide6.QtGui import QPainter, QColor, QFontMetrics, QMouseEvent

from git_backend import FileStatus
from theme import BG, BG_ELEV, BG_HOVER, BORDER, BORDER_SOFT, FG, FG_DIM, _file_icon, _sidebar_icon


# ── 颜色常量（按状态） ─────────────────────────────────────────────────────

_STATUS_COLOR: dict[str, str] = {
    "A":  "#00ba7c",   # green
    "M":  "#e7e9ea",   # white-ish (worktree changes)
    "D":  "#f4212e",   # red
    "?":  "#1d9bf0",   # blue (untracked)
    "R":  "#e7e9ea",
    "U":  "#ffd400",   # conflict
}

_STATUS_ICON: dict[str, str] = {
    "A":  "A",
    "M":  "M",
    "D":  "D",
    "?":  "?",
    "R":  "R",
    "U":  "!",
}


# ── 分组标题行（可折叠） ───────────────────────────────────────────────────


class GroupHeader(QWidget):
    """可点击折叠/展开的分组标题。

    子组件：
      ▶/▼    GROUP NAME        (12)     +34 −5
    """
    toggled = Signal(bool)  # True = expanded

    def __init__(self, title: str, count: int = 0, parent=None):
        super().__init__(parent)
        self._title = title
        self._count = count
        self._expanded = True
        self._hover = False
        self.setFixedHeight(26)
        self.setMouseTracking(True)
        self.setObjectName("gitGroupHeader")
        self._update_tooltip()

    def set_count(self, n: int) -> None:
        self._count = n
        self._update_tooltip()
        self.update()

    def is_expanded(self) -> bool:
        return self._expanded

    def set_expanded(self, expanded: bool) -> None:
        if self._expanded != expanded:
            self._expanded = expanded
            self.toggled.emit(expanded)
            self.update()

    def _update_tooltip(self) -> None:
        self.setToolTip(f"{self._title} ({self._count}) — 点击折叠/展开")

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.set_expanded(not self._expanded)
            event.accept()
            return
        super().mousePressEvent(event)

    def enterEvent(self, event) -> None:
        self._hover = True
        self.update()

    def leaveEvent(self, event) -> None:
        self._hover = False
        self.update()

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = self.rect()

        # 背景
        if self._hover:
            p.fillRect(rect, QColor(BG_HOVER))

        # 三角箭头
        arrow = "▼" if self._expanded else "▶"
        p.setPen(QColor(FG_DIM))
        p.setFont(self.font())
        fm = QFontMetrics(p.font())
        p.drawText(10, fm.ascent() + 5, arrow)

        # 标题
        p.setPen(QColor(FG))
        bold = p.font()
        bold.setBold(True)
        bold.setPointSize(10)
        p.setFont(bold)
        p.drawText(22, fm.ascent() + 5, self._title)

        # 计数
        p.setFont(self.font())
        p.setPen(QColor(FG_DIM))
        p.drawText(22 + fm.horizontalAdvance(self._title) + 6, fm.ascent() + 5,
                   f"({self._count})")


# ── 单文件行 ──────────────────────────────────────────────────────────────


class FileRowWidget(QWidget):
    """git 状态列表中的一行文件。

    信号：
      checkbox_changed(str path, bool checked)
      clicked(str path, bool staged)
    """
    checkbox_changed = Signal(str, bool)
    clicked = Signal(str, bool)

    _H = 26

    def __init__(self, status: FileStatus, *, repo: Path,
                 initially_checked: bool = False, parent=None):
        super().__init__(parent)
        self._status = status
        self._repo = repo
        self._path = status.path
        self._staged = bool(status.is_staged)
        self._hover = False
        self.setFixedHeight(self._H)
        self.setMouseTracking(True)
        self.setObjectName("gitFileRow")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(22, 0, 8, 0)
        layout.setSpacing(6)

        # ── checkbox ──
        self._cb = QCheckBox()
        self._cb.setFixedSize(16, 16)
        self._cb.setChecked(initially_checked)
        self._cb.setCursor(Qt.CursorShape.PointingHandCursor)
        self._cb.stateChanged.connect(self._on_cb_changed)
        layout.addWidget(self._cb)

        # ── 状态码徽章 ──
        # 用 staged 状态对应的字母；staged 用 X，工作区用 y
        letter = status.x.strip() if status.is_staged else (
            "?" if status.is_untracked else status.y.strip() or status.x.strip()
        )
        badge_color = _STATUS_COLOR.get(letter, "#71767b")
        badge_lbl = QLabel(_STATUS_ICON.get(letter, "·"))
        badge_lbl.setFixedSize(14, 14)
        badge_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        badge_lbl.setStyleSheet(
            f"color: {badge_color}; font-weight: bold; font-size: 11px; "
            f"font-family: 'Cascadia Code', 'Consolas', monospace;"
        )
        layout.addWidget(badge_lbl)

        # ── 文件名 ──
        display = self._display_name()
        name_lbl = QLabel(display)
        name_lbl.setObjectName("gitFileName")
        name_lbl.setToolTip(str(repo / status.path))
        layout.addWidget(name_lbl, 1)

        # ── 增减统计（M / A 才有意义）──
        stats_lbl = self._make_stats_label()
        if stats_lbl:
            layout.addWidget(stats_lbl)

        self.setStyleSheet(f"""
            QCheckBox {{
                background: transparent;
            }}
            QCheckBox::indicator {{
                width: 13px; height: 13px;
                border: 1px solid {BORDER};
                border-radius: 2px; background: {BG_ELEV};
            }}
            QCheckBox::indicator:hover {{ border-color: {FG}; }}
            QCheckBox::indicator:checked {{
                background: {FG}; border-color: {FG};
                image: url();  /* 不显示对勾，简单用白底 */
            }}
        """)

    def _display_name(self) -> str:
        p = self._status.path
        # 太长路径截断中间，显示文件名 + 父目录
        if len(p) > 50:
            parts = p.replace("\\", "/").split("/")
            if len(parts) > 2:
                return f"{parts[0]}/…/{parts[-1]}"
        return p.replace("\\", "/")

    def _make_stats_label(self) -> QLabel | None:
        """返回显示 +X −Y 的标签；纯新增/删除/未跟踪时不显示。"""
        if self._status.is_untracked:
            return None
        # 不实际 diff 算行数（开销大）；用 status 颜色暗示
        x = self._status.x.strip()
        y = self._status.y.strip()
        if x and not y:  # 纯 staged（已 add，未改动）
            if x == "A":
                lbl = QLabel("(added)")
                lbl.setStyleSheet(f"color: #00ba7c; font-size: 11px;")
                return lbl
            if x == "D":
                lbl = QLabel("(deleted)")
                lbl.setStyleSheet(f"color: #f4212e; font-size: 11px;")
                return lbl
            return None  # 纯 staged M：先不展开
        # 工作区有改动 —— 留到阶段 5 diff 视图显示
        return None

    def status(self) -> FileStatus:
        return self._status

    def is_checked(self) -> bool:
        return self._cb.isChecked()

    def set_checked(self, checked: bool) -> None:
        if self._cb.isChecked() != checked:
            self._cb.setChecked(checked)

    def _on_cb_changed(self, state: int) -> None:
        self.checkbox_changed.emit(self._path, bool(state))

    def mousePressEvent(self, event: QMouseEvent) -> None:
        # 点击非 checkbox 区域 → 触发 clicked
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self._path, self._staged)
            event.accept()
            return
        super().mousePressEvent(event)

    def enterEvent(self, event) -> None:
        self._hover = True
        self.setStyleSheet(self.styleSheet() + f"#gitFileRow {{ background: {BG_HOVER}; }}")

    def leaveEvent(self, event) -> None:
        self._hover = False
        self.setStyleSheet(self.styleSheet().replace(f"background: {BG_HOVER};", ""))


# ── 主列表 ────────────────────────────────────────────────────────────────


class FileList(QWidget):
    """git 文件状态列表。

    三组：STAGED / CHANGES / UNTRACKED。
    信号：
      file_selected(str path, bool staged)  — 点击行
      selection_changed(str set[path])      — checkbox 变化
    """
    file_selected = Signal(str, bool)
    selection_changed = Signal(set)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._repo: Path | None = None
        self._staged_rows: list[FileRowWidget] = []
        self._changes_rows: list[FileRowWidget] = []
        self._untracked_rows: list[FileRowWidget] = []
        self._staged_header: GroupHeader | None = None
        self._changes_header: GroupHeader | None = None
        self._untracked_header: GroupHeader | None = None

        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(0)
        self._layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        self._empty_lbl = QLabel("(无文件改动)")
        self._empty_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._empty_lbl.setStyleSheet(f"color: {FG_DIM}; padding: 20px; font-size: 12px;")
        self._empty_lbl.hide()
        self._layout.addWidget(self._empty_lbl)

        self.setStyleSheet(f"background: {BG};")

    def set_repo(self, repo: Path) -> None:
        self._repo = repo
        self.clear()

    def clear(self) -> None:
        """清空所有行。"""
        for row in self._staged_rows + self._changes_rows + self._untracked_rows:
            self._layout.removeWidget(row)
            row.deleteLater()
        self._staged_rows.clear()
        self._changes_rows.clear()
        self._untracked_rows.clear()

        for hdr in (self._staged_header, self._changes_header, self._untracked_header):
            if hdr is not None:
                self._layout.removeWidget(hdr)
                hdr.deleteLater()
        self._staged_header = None
        self._changes_header = None
        self._untracked_header = None
        self._empty_lbl.hide()

    def populate(self, statuses: list[FileStatus]) -> None:
        """用 backend.status() 结果填列表。"""
        self.clear()
        if not statuses:
            self._empty_lbl.show()
            return

        # 分组
        staged = [s for s in statuses if s.is_staged]
        changes = [s for s in statuses if s.is_dirty and not s.is_staged]
        untracked = [s for s in statuses if s.is_untracked]

        if staged:
            self._staged_header = GroupHeader("STAGED CHANGES", len(staged))
            self._staged_header.toggled.connect(self._toggle_staged_visibility)
            self._layout.addWidget(self._staged_header)
            for s in staged:
                row = self._make_row(s)
                self._staged_rows.append(row)
                self._layout.addWidget(row)

        if changes:
            self._changes_header = GroupHeader("CHANGES", len(changes))
            self._changes_header.toggled.connect(self._toggle_changes_visibility)
            self._layout.addWidget(self._changes_header)
            for s in changes:
                row = self._make_row(s)
                self._changes_rows.append(row)
                self._layout.addWidget(row)

        if untracked:
            self._untracked_header = GroupHeader("UNTRACKED FILES", len(untracked))
            self._untracked_header.toggled.connect(self._toggle_untracked_visibility)
            self._layout.addWidget(self._untracked_header)
            for s in untracked:
                row = self._make_row(s)
                self._untracked_rows.append(row)
                self._layout.addWidget(row)

        # 全空（status 没结果但列表非空也不显示 empty）
        self._empty_lbl.setVisible(not (staged or changes or untracked))
        if self._empty_lbl.isVisible():
            self._empty_lbl.setText("(无文件改动)")

    def selected_paths(self) -> set[str]:
        """所有被勾选的路径。"""
        result: set[str] = set()
        for row in self._staged_rows + self._changes_rows + self._untracked_rows:
            if row.is_checked():
                result.add(row.status().path)
        return result

    def staged_paths(self) -> set[str]:
        """当前已 staged 的文件路径（用于 commit 前判断）。"""
        return {r.status().path for r in self._staged_rows}

    def _make_row(self, status: FileStatus) -> FileRowWidget:
        # 初始勾选：已 staged 的默认勾选；其他不勾
        row = FileRowWidget(
            status,
            repo=self._repo or Path("."),
            initially_checked=status.is_staged,
        )
        row.checkbox_changed.connect(self._on_checkbox_changed)
        row.clicked.connect(self.file_selected.emit)
        return row

    def _on_checkbox_changed(self, path: str, checked: bool) -> None:
        self.selection_changed.emit(self.selected_paths())

    def _toggle_staged_visibility(self, expanded: bool) -> None:
        for r in self._staged_rows:
            r.setVisible(expanded)

    def _toggle_changes_visibility(self, expanded: bool) -> None:
        for r in self._changes_rows:
            r.setVisible(expanded)

    def _toggle_untracked_visibility(self, expanded: bool) -> None:
        for r in self._untracked_rows:
            r.setVisible(expanded)
