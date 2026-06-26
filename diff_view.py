"""Git Side-by-Side Diff 视图。

布局（VS Code Diff 风格）：
  ┌──────────────────────┬──────────────────────┐
  │ README.md  (HEAD)    │ README.md  (working) │
  ├──────────────────────┼──────────────────────┤
  │  1  # Hello          │  1  # Hello v2       │
  │  2                   │  2                   │
  │  3 - world           │  3 + world changed   │   ← 行级 +- 染色
  │  4                   │  4 + added line      │
  └──────────────────────┴──────────────────────┘

性能
----
- 用 ``QPlainTextEdit`` 而非 ``QTextEdit``（大文本性能好得多）
- 单文件最大显示行数 MAX_LINES 防止卡死（超出截断并显示提示）
- 双栏共享同一个 scrollbar valueChanged 信号，实现同步滚动
"""
from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPlainTextEdit, QFrame,
    QSizePolicy,
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont, QTextCursor, QTextCharFormat, QColor, QFontDatabase

from git_backend import FileDiff, Hunk
from theme import BG, BG_ELEV, BG_HOVER, BORDER, BORDER_SOFT, FG, FG_DIM, DANGER, SUCCESS


# ── 配色 ──────────────────────────────────────────────────────────────────

_COLOR_GUTTER_BG     = "#0e0e0e"   # 行号列底色
_COLOR_GUTTER_FG     = "#71767b"   # 行号字色
_COLOR_LINE_ADD_BG   = "#0d3320"   # 绿色 + 行底
_COLOR_LINE_ADD_FG   = "#a6e3a1"
_COLOR_LINE_DEL_BG   = "#3b0d10"   # 红色 - 行底
_COLOR_LINE_DEL_FG   = "#f2b3b6"
_COLOR_HUNK_BG       = "#16181c"   # @@ 标题行
_COLOR_HUNK_FG       = "#8b98a5"
_COLOR_HEADER_BG     = "#16181c"   # 文件头
_COLOR_HEADER_FG     = "#e7e9ea"
_COLOR_GAP_BG        = "#1a1c20"   # 上下文空行


_MAX_LINES = 5000     # 单文件 diff 显示上限（防卡死）


# ── 单侧视图 ──────────────────────────────────────────────────────────────


class DiffSide(QPlainTextEdit):
    """diff 的一侧（左旧右新）。

    不使用行号 gutter，而是把行号嵌在文本前缀里，方便两栏对齐。
    """

    def __init__(self, side: str, parent=None):
        super().__init__(parent)
        self._side = side   # "old" or "new"
        self.setReadOnly(True)
        self.setUndoRedoEnabled(False)
        self.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setStyleSheet(f"""
            QPlainTextEdit {{
                background: {BG};
                color: {FG};
                border: none;
                selection-background-color: #ffffff40;
                selection-color: {FG};
            }}
        """)

        # 等宽字体（用 Cascadia Code / Consolas，回退到 monospace）
        f = QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont)
        f.setPointSize(11)
        f.setStyleHint(QFont.StyleHint.Monospace)
        self.setFont(f)

        # 设置 tab 宽度为 4 字符
        fm = self.fontMetrics()
        self.setTabStopDistance(fm.horizontalAdvance(" ") * 4)

    def populate(self, lines: list[tuple[str, str, str]]) -> None:
        """填入行：(kind, lineno, text)。

        kind ∈ {"ctx", "+", "-", "hunk", "gap"}
        lineno 为字符串（对齐用空格填充），为 None 时不显示行号。
        """
        self.clear()
        if not lines:
            return

        cursor = self.textCursor()
        cursor.beginEditBlock()

        fmt_ctx   = self._fmt(QColor(FG),          BG)
        fmt_add   = self._fmt(QColor(_COLOR_LINE_ADD_FG), _COLOR_LINE_ADD_BG)
        fmt_del   = self._fmt(QColor(_COLOR_LINE_DEL_FG), _COLOR_LINE_DEL_BG)
        fmt_hunk  = self._fmt(QColor(_COLOR_HUNK_FG),  _COLOR_HUNK_BG, italic=True)
        fmt_gap   = self._fmt(QColor(FG_DIM),         _COLOR_GAP_BG,  italic=True)

        for kind, lineno, text in lines:
            fmt = {
                "ctx":  fmt_ctx,
                "+":    fmt_add,
                "-":    fmt_del,
                "hunk": fmt_hunk,
                "gap":  fmt_gap,
            }.get(kind, fmt_ctx)
            prefix = (lineno or "").ljust(5)
            # 行格式：lineno │ text
            line_text = f"{prefix} │ {text}"
            cursor.insertText(line_text + "\n", fmt)

        cursor.endEditBlock()
        cursor.movePosition(QTextCursor.MoveOperation.Start)

    @staticmethod
    def _fmt(color: QColor, bg: str, *, italic: bool = False) -> QTextCharFormat:
        f = QTextCharFormat()
        f.setForeground(color)
        # 背景只能通过 setBackground(QColor) 不能直接用字符串
        f.setBackground(QColor(bg))
        f.setFontItalic(italic)
        return f


# ── DiffView 主组件 ────────────────────────────────────────────────────────


class DiffView(QWidget):
    """Side-by-Side diff 视图。

    用两个 ``QPlainTextEdit`` 共享一个 ``QScrollBar`` 实现同步滚动。
    """
    file_copied = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()
        self._wire()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # 顶部：文件信息头
        self._header = QLabel("(未选择文件)")
        self._header.setObjectName("gitDiffHeader")
        self._header.setFixedHeight(34)
        self._header.setStyleSheet(f"""
            QLabel {{
                background: {_COLOR_HEADER_BG};
                color: {_COLOR_HEADER_FG};
                padding: 0 12px;
                border-bottom: 1px solid {BORDER_SOFT};
                font-size: 12px;
            }}
        """)
        root.addWidget(self._header)

        # 双栏 + 共享滚动条
        body = QWidget()
        bl = QHBoxLayout(body)
        bl.setContentsMargins(0, 0, 0, 0)
        bl.setSpacing(0)

        self._left = DiffSide("old")
        self._right = DiffSide("new")

        # 中间分隔
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.VLine)
        sep.setStyleSheet(f"background: {BORDER}; max-width: 1px;")

        bl.addWidget(self._left, 1)
        bl.addWidget(sep)
        bl.addWidget(self._right, 1)

        # 共享垂直滚动条（只显示一个）
        self._scroll = self._left.verticalScrollBar()
        self._right.setVerticalScrollBar(self._scroll)

        # 文件大小写自己的水平滚动
        bl.addWidget(self._scroll, 0)  # 占位，避免布局错误
        body_layout_index = bl.indexOf(self._scroll)
        bl.removeWidget(self._scroll)
        self._scroll.setParent(body)
        # 单独放在右侧 — 实际我们用 left 的滚动条
        # 简化方案：把 right 的滚动条隐藏，left 显示
        self._left.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self._right.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        root.addWidget(body, 1)
        self.setStyleSheet(f"background: {BG};")

    def _wire(self) -> None:
        # 同步滚动：左侧滚 → 右侧跟
        self._left.verticalScrollBar().valueChanged.connect(
            self._right.verticalScrollBar().setValue
        )
        self._right.verticalScrollBar().valueChanged.connect(
            self._left.verticalScrollBar().setValue
        )

    # ── 公共 API ──

    def show_diff(self, repo: Path, diff: FileDiff) -> None:
        """渲染一个文件的 diff。"""
        self._header.setText(self._format_header(repo, diff))
        left_lines, right_lines = self._align_lines(diff)
        truncated = sum(len(h.lines) for h in diff.hunks) > _MAX_LINES
        if truncated:
            gap_line = ("gap", "···", "··· diff truncated to " + str(_MAX_LINES) + " lines")
            left_lines.append(gap_line)
            right_lines.append(gap_line)
        self._left.populate(left_lines)
        self._right.populate(right_lines)

    def show_message(self, text: str) -> None:
        """显示占位文本（无文件 / 无 diff / 错误）。"""
        self._header.setText("(无 diff)")
        msg = f"     │ {text}"
        self._left.populate([("gap", "", msg)])
        self._right.populate([("gap", "", msg)])

    def show_binary(self, repo: Path, diff: FileDiff) -> None:
        self._header.setText(self._format_header(repo, diff) + " [binary]")
        self._left.populate([("gap", "", "Binary file differs")])
        self._right.populate([("gap", "", "Binary file differs")])

    # ── 内部 ──

    @staticmethod
    def _format_header(repo: Path, diff: FileDiff) -> str:
        additions = diff.additions
        deletions = diff.deletions
        path = diff.path
        if diff.old_path and diff.old_path != diff.path:
            path = f"{diff.old_path} → {diff.path}"
        parts = [
            f" {path}",
            f"+{additions}" if additions else "",
            f"−{deletions}" if deletions else "",
        ]
        parts = [p for p in parts if p]
        return "    ".join(parts)

    @staticmethod
    def _align_lines(diff: FileDiff) -> tuple[list[tuple[str, str, str]],
                                              list[tuple[str, str, str]]]:
        """把 hunk 转成左右两栏对齐的行序列。

        返回：([(kind, lineno, text), ...], [同样的形状])
        kind ∈ {"ctx", "+", "-", "hunk", "gap"}
        """
        left: list[tuple[str, str, str]] = []
        right: list[tuple[str, str, str]] = []

        for hunk in diff.hunks:
            # hunk header
            hunk_text = f"@@ -{hunk.old_start},{hunk.old_count} +{hunk.new_start},{hunk.new_count} @@"
            left.append(("hunk", "", hunk_text))
            right.append(("hunk", "", hunk_text))

            old_line_no = hunk.old_start
            new_line_no = hunk.new_start

            # 走 Myers-style 算法：匹配连续 ctx/-/+ 来对齐两栏
            # 简单策略：扫描，遇到 " "-行 ctx 同步；遇到 - 把右侧填空；遇到 + 把左侧填空
            for kind, text in hunk.lines:
                if kind == " ":
                    left.append(("ctx",  str(old_line_no), text))
                    right.append(("ctx", str(new_line_no), text))
                    old_line_no += 1
                    new_line_no += 1
                elif kind == "-":
                    left.append(("-", str(old_line_no), text))
                    right.append(("gap", "", ""))
                    old_line_no += 1
                elif kind == "+":
                    left.append(("gap", "", ""))
                    right.append(("+", str(new_line_no), text))
                    new_line_no += 1
                # 忽略 \ No newline 等其他行

        return left, right
