"""Git Commit 历史列表组件。

布局：
  ┌────────────────────────────────────────┐
  │ ⏱ 8ee7eff  Fix bug                     │  ← 每行 commit
  │        by KK · 2 hours ago             │
  │ ⏱ 5d3a9c2  Add feature                 │
  │        by KK · 3 hours ago             │
  │ ⏱ 9a01f3e  Initial commit              │
  │        by Tester · yesterday           │
  └────────────────────────────────────────┘

点击 commit → 选中的 commit 替换右侧 diff 视图
"""
from __future__ import annotations

from datetime import datetime

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QScrollArea,
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPainter, QColor, QFontMetrics, QMouseEvent

from git_backend import Commit
from theme import BG, BG_ELEV, BG_HOVER, BORDER, BORDER_SOFT, FG, FG_DIM


# ── 单条 commit 行 ────────────────────────────────────────────────────────


class CommitRow(QWidget):
    """单条 commit。"""
    commit_clicked = Signal(str)  # sha

    def __init__(self, commit: Commit, parent=None):
        super().__init__(parent)
        self._commit = commit
        self._selected = False
        self._hover = False
        self.setFixedHeight(56)
        self.setMouseTracking(True)
        self.setObjectName("commitRow")

    def commit(self) -> Commit:
        return self._commit

    def set_selected(self, selected: bool) -> None:
        if self._selected != selected:
            self._selected = selected
            self.update()

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.commit_clicked.emit(self._commit.sha)
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
        if self._selected:
            p.fillRect(rect, QColor(BG_ACTIVE))
        elif self._hover:
            p.fillRect(rect, QColor(BG_HOVER))

        # 左边 4px 选中条
        if self._selected:
            p.fillRect(0, 0, 3, rect.height(), QColor(FG))

        # 短 SHA
        p.setPen(QColor(FG_DIM))
        p.setFont(self.font())
        fm = QFontMetrics(p.font())
        sha_text = self._commit.short_sha
        p.drawText(14, fm.ascent() + 12, sha_text)

        # 短 SHA 后的 summary（如果长就截断）
        p.setPen(QColor(FG))
        summary = self._commit.summary
        max_w = rect.width() - 14 - fm.horizontalAdvance(sha_text) - 12
        elided = fm.elidedText(summary, Qt.TextElideMode.ElideRight, max_w)
        p.drawText(14 + fm.horizontalAdvance(sha_text) + 8, fm.ascent() + 12, elided)

        # 第二行：author + date
        date_str = self._format_date(self._commit.date)
        subtitle = f"{self._commit.author} · {date_str}"
        p.setPen(QColor(FG_DIM))
        subtitle_elided = fm.elidedText(subtitle, Qt.TextElideMode.ElideRight, rect.width() - 28)
        p.drawText(14, fm.ascent() + 12 + fm.height() + 2, subtitle_elided)

    @staticmethod
    def _format_date(iso: str) -> str:
        """ISO 日期 → 相对时间（"2 hours ago" / "yesterday" / "2026-06-25"）。"""
        try:
            dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
        except (ValueError, TypeError):
            return iso
        now = datetime.now(dt.tzinfo)
        delta = now - dt
        secs = int(delta.total_seconds())
        if secs < 60:
            return "just now"
        if secs < 3600:
            return f"{secs // 60} minutes ago"
        if secs < 86400:
            return f"{secs // 3600} hours ago"
        if secs < 7 * 86400:
            return f"{secs // 86400} days ago"
        return dt.strftime("%Y-%m-%d")


# ── 主列表 ────────────────────────────────────────────────────────────────


class CommitList(QWidget):
    """commit 历史滚动列表。

    信号：
      commit_selected(str sha)  — 用户点击了某条 commit
    """
    commit_selected = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._rows: list[CommitRow] = []
        self._selected_sha: str | None = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # 滚动容器
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._scroll.setStyleSheet(f"""
            QScrollArea {{ background: {BG}; border: none; }}
            QScrollBar:vertical {{
                background: {BG}; width: 8px; margin: 0;
            }}
            QScrollBar::handle:vertical {{
                background: {BORDER}; border-radius: 4px; min-height: 20px;
            }}
            QScrollBar::handle:vertical:hover {{ background: {FG_DIM}; }}
        """)

        self._container = QWidget()
        self._cl = QVBoxLayout(self._container)
        self._cl.setContentsMargins(0, 0, 0, 0)
        self._cl.setSpacing(0)
        self._cl.setAlignment(Qt.AlignmentFlag.AlignTop)
        self._scroll.setWidget(self._container)

        self._empty_lbl = QLabel("(无 commit 历史)")
        self._empty_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._empty_lbl.setStyleSheet(f"color: {FG_DIM}; padding: 20px; font-size: 12px;")
        self._cl.addWidget(self._empty_lbl)

        layout.addWidget(self._scroll)
        self.setStyleSheet(f"background: {BG};")

    def populate(self, commits: list[Commit]) -> None:
        """清空旧行，加载新 commits。"""
        for r in self._rows:
            self._cl.removeWidget(r)
            r.deleteLater()
        self._rows.clear()
        self._selected_sha = None

        if not commits:
            self._empty_lbl.show()
            return
        self._empty_lbl.hide()

        for c in commits:
            row = CommitRow(c)
            row.commit_clicked.connect(self._on_row_clicked)
            self._rows.append(row)
            self._cl.addWidget(row)

    def selected_sha(self) -> str | None:
        return self._selected_sha

    def _on_row_clicked(self, sha: str) -> None:
        # 取消旧选中
        if self._selected_sha is not None:
            for r in self._rows:
                if r.commit().sha == self._selected_sha:
                    r.set_selected(False)
                    break
        # 设新选中
        self._selected_sha = sha
        for r in self._rows:
            if r.commit().sha == sha:
                r.set_selected(True)
                break
        self.commit_selected.emit(sha)
