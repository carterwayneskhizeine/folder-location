"""最近文件更改历史面板。"""
import subprocess
from pathlib import Path
from datetime import datetime, timedelta

from PySide6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QScrollArea,
)
from PySide6.QtCore import Qt, QTimer, Signal

from theme import _file_icon, _sidebar_icon


class HistoryRowWidget(QWidget):
    copy_clicked = Signal(str)
    item_clicked = Signal(Path)

    _BTN_H = 22
    _EVENT_COLORS = {"added": "#00ba7c", "deleted": "#f4212e", "modified": "#ffffff"}
    _EVENT_LABELS = {"added": "+", "deleted": "−", "modified": "~"}

    def __init__(self, path: str, event_type: str, ts: datetime, parent=None):
        super().__init__(parent)
        self._path = path
        self._ts = ts
        self._event_type = event_type
        self.setFixedHeight(30)
        self.setMouseTracking(True)
        self.setObjectName("historyRow")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 0, 6, 0)
        layout.setSpacing(6)

        color = self._EVENT_COLORS.get(event_type, "#71767b")
        dot = QLabel(self._EVENT_LABELS.get(event_type, "·"))
        dot.setFixedWidth(12)
        dot.setStyleSheet(f"color: {color}; font-size: 12px; font-weight: bold;")
        layout.addWidget(dot)

        self._time_lbl = QLabel(self._fmt_time())
        self._time_lbl.setFixedWidth(58)
        self._time_lbl.setObjectName("historyTime")
        layout.addWidget(self._time_lbl)

        p = Path(path)
        if p.suffix == "" and p.is_dir():
            name_icon = _sidebar_icon("FOLDER", 16)[0]
        else:
            name_icon = _file_icon(p.name)
        icon_lbl = QLabel()
        icon_lbl.setPixmap(name_icon.pixmap(16, 16))
        icon_lbl.setFixedSize(16, 16)
        layout.addWidget(icon_lbl)

        name_lbl = QLabel(p.name)
        name_lbl.setObjectName("historyName")
        name_lbl.setToolTip(path)
        if event_type == "deleted":
            name_lbl.setStyleSheet("color: #536471;")
        layout.addWidget(name_lbl, 1)

        self._copy_btn = QPushButton("Copy")
        self._copy_btn.setObjectName("treeActionBtn")
        self._copy_btn.setFixedHeight(self._BTN_H)
        self._copy_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._copy_btn.hide()
        self._copy_btn.clicked.connect(self._do_copy)
        layout.addWidget(self._copy_btn)

        self._open_btn = QPushButton("Open")
        self._open_btn.setObjectName("treeActionBtn")
        self._open_btn.setFixedHeight(self._BTN_H)
        self._open_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._open_btn.hide()
        self._open_btn.clicked.connect(self._do_open)
        layout.addWidget(self._open_btn)

        self._hide_timer = QTimer(self)
        self._hide_timer.setSingleShot(True)
        self._hide_timer.setInterval(90)
        self._hide_timer.timeout.connect(self._hide_btns)

    def _fmt_time(self) -> str:
        secs = int((datetime.now() - self._ts).total_seconds())
        if secs < 60:
            return "刚刚"
        if secs < 3600:
            return f"{secs // 60}分钟前"
        return f"{secs // 3600}小时前"

    def update_time(self) -> None:
        self._time_lbl.setText(self._fmt_time())

    def enterEvent(self, event) -> None:
        self._hide_timer.stop()
        self._copy_btn.show()
        self._open_btn.show()

    def leaveEvent(self, event) -> None:
        self._hide_timer.start()

    def _hide_btns(self) -> None:
        self._copy_btn.hide()
        self._open_btn.hide()

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            p = Path(self._path)
            if p.is_file():
                self.item_clicked.emit(p)
        super().mousePressEvent(event)

    def _do_copy(self) -> None:
        text = "@" + self._path.replace("\\", "/")
        QApplication.clipboard().setText(text)
        self.copy_clicked.emit(text)
        self._copy_btn.setText("OK")
        QTimer.singleShot(900, lambda: self._copy_btn.setText("Copy"))

    def _do_open(self) -> None:
        p = Path(self._path)
        target = p if p.exists() else (p.parent if p.parent.exists() else None)
        if target:
            subprocess.Popen(f'explorer /select,"{target}"')


class HistoryPanel(QWidget):
    file_selected = Signal(Path)
    path_copied   = Signal(str)

    _MAX_AGE     = 86400
    _MAX_ENTRIES = 300

    def __init__(self):
        super().__init__()
        vl = QVBoxLayout(self)
        vl.setContentsMargins(0, 0, 0, 0)
        vl.setSpacing(0)

        header = QLabel("更改历史")
        header.setObjectName("historyHeader")
        header.setFixedHeight(40)
        vl.addWidget(header)

        self._scroll = QScrollArea()
        self._scroll.setObjectName("historyScroll")
        self._scroll.setWidgetResizable(True)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        self._container = QWidget()
        self._cl = QVBoxLayout(self._container)
        self._cl.setContentsMargins(0, 0, 0, 0)
        self._cl.setSpacing(0)
        self._cl.setAlignment(Qt.AlignmentFlag.AlignTop)
        self._scroll.setWidget(self._container)
        vl.addWidget(self._scroll, 1)

        self._entries: list[tuple[datetime, str, str]] = []
        self._rows: list[HistoryRowWidget] = []

        self._empty_lbl = QLabel("暂无更改记录")
        self._empty_lbl.setObjectName("historyEmpty")
        self._empty_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._cl.addWidget(self._empty_lbl)

        self._dirty = False
        self._rebuild_timer = QTimer(self)
        self._rebuild_timer.setSingleShot(True)
        self._rebuild_timer.setInterval(250)
        self._rebuild_timer.timeout.connect(self._do_rebuild)

        self._tick = QTimer(self)
        self._tick.setInterval(60_000)
        self._tick.timeout.connect(self._tick_times)
        self._tick.start()

    def add_event(self, path: str, event_type: str) -> None:
        now = datetime.now()
        cutoff = now - timedelta(seconds=self._MAX_AGE)
        self._entries = [(ts, p, et) for ts, p, et in self._entries if ts > cutoff]

        if self._entries:
            last_ts, last_p, last_et = self._entries[0]
            if last_p == path and last_et == event_type:
                if (now - last_ts).total_seconds() < 2:
                    return

        self._entries.insert(0, (now, path, event_type))
        if len(self._entries) > self._MAX_ENTRIES:
            self._entries = self._entries[:self._MAX_ENTRIES]

        self._dirty = True
        self._rebuild_timer.start()

    def _do_rebuild(self) -> None:
        self._dirty = False
        for row in self._rows:
            self._cl.removeWidget(row)
            row.deleteLater()
        self._rows.clear()

        if not self._entries:
            self._empty_lbl.show()
            return

        self._empty_lbl.hide()
        for ts, path, event_type in self._entries:
            row = HistoryRowWidget(path, event_type, ts)
            row.copy_clicked.connect(self.path_copied)
            row.item_clicked.connect(self.file_selected)
            self._rows.append(row)
            self._cl.addWidget(row)

    def _tick_times(self) -> None:
        now = datetime.now()
        cutoff = now - timedelta(seconds=self._MAX_AGE)
        old_count = len(self._entries)
        self._entries = [(ts, p, et) for ts, p, et in self._entries if ts > cutoff]
        if len(self._entries) != old_count:
            self._do_rebuild()
        else:
            for row in self._rows:
                row.update_time()
