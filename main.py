#!/usr/bin/env python3
"""Folder Location + 文件预览 — 多标签页"""
import sys
import json
import ctypes
import subprocess
import html as _html
from pathlib import Path

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QLineEdit, QTreeWidget, QTreeWidgetItem,
    QTabBar, QSplitter, QFileDialog, QPlainTextEdit,
    QSystemTrayIcon, QMenu, QStackedWidget, QToolButton,
    QProxyStyle, QStyle,
)
from PySide6.QtCore import Qt, QTimer, QEvent, Signal, QUrl, QSettings, QSize, QFileSystemWatcher
from PySide6.QtGui import QColor, QPalette, QIcon, QAction

try:
    from PySide6.QtWebEngineWidgets import QWebEngineView
    HAS_WEBENGINE = True
except ImportError:
    HAS_WEBENGINE = False

try:
    import markdown as _md
    HAS_MARKDOWN = True
except ImportError:
    HAS_MARKDOWN = False

try:
    from pygments import highlight as _hl
    from pygments.lexers import get_lexer_for_filename as _lexer_for
    from pygments.formatters import HtmlFormatter as _HtmlFmt
    from pygments.util import ClassNotFound as _LexerNotFound
    HAS_PYGMENTS = True
except ImportError:
    HAS_PYGMENTS = False


# ── Dark palette ──────────────────────────────────────────────────────────────

def apply_dark_palette(app: QApplication) -> None:
    app.setStyle("Fusion")
    p = QPalette()
    p.setColor(QPalette.ColorRole.Window,          QColor("#0d1117"))
    p.setColor(QPalette.ColorRole.WindowText,      QColor("#c9d1d9"))
    p.setColor(QPalette.ColorRole.Base,            QColor("#0d1117"))
    p.setColor(QPalette.ColorRole.AlternateBase,   QColor("#161b22"))
    p.setColor(QPalette.ColorRole.Text,            QColor("#c9d1d9"))
    p.setColor(QPalette.ColorRole.Button,          QColor("#21262d"))
    p.setColor(QPalette.ColorRole.ButtonText,      QColor("#c9d1d9"))
    p.setColor(QPalette.ColorRole.Highlight,       QColor("#1f6feb"))
    p.setColor(QPalette.ColorRole.HighlightedText, QColor("#ffffff"))
    p.setColor(QPalette.ColorRole.Link,            QColor("#58a6ff"))
    p.setColor(QPalette.ColorRole.Mid,             QColor("#30363d"))
    p.setColor(QPalette.ColorRole.Dark,            QColor("#21262d"))
    p.setColor(QPalette.ColorRole.Shadow,          QColor("#010409"))
    app.setPalette(p)


# ── Stylesheet ────────────────────────────────────────────────────────────────

STYLESHEET = """
QMainWindow, QWidget { background: #0d1117; color: #c9d1d9; }

QSplitter::handle:horizontal { background: #30363d; width: 1px; }
QSplitter::handle:vertical   { background: #30363d; height: 1px; }

/* ── Tab widget ── */
#folderTabsHeader {
    background: #0d1117;
    border-bottom: 1px solid #30363d;
}
QTabBar { background: #0d1117; }
QTabBar::tab {
    background: #161b22;
    color: #8b949e;
    border: 1px solid #30363d;
    border-bottom: none;
    padding: 5px 6px 5px 12px;
    min-width: 60px;
    max-width: 180px;
    border-top-left-radius: 6px;
    border-top-right-radius: 6px;
    margin-right: 2px;
}
QTabBar::tab:selected {
    background: #0d1117;
    color: #e6edf3;
    border-color: #30363d;
    border-bottom-color: #0d1117;
}
QTabBar::tab:!selected { margin-top: 2px; }
QTabBar::tab:hover:!selected { background: #21262d; color: #c9d1d9; }
QTabBar QToolButton {
    background: transparent;
    border: none;
    padding: 0;
    margin: 0;
    min-width: 0;
    max-width: 0;
    min-height: 0;
    max-height: 0;
    width: 0;
    height: 0;
}
QTabBar QToolButton::left-arrow,
QTabBar QToolButton::right-arrow {
    image: none;
    width: 0;
    height: 0;
}

/* ── Buttons ── */
#addFolderBtn {
    background: transparent;
    border: 1px solid transparent;
    border-radius: 5px;
    color: #8b949e;
    font-size: 18px;
    font-weight: bold;
    padding: 0 8px;
    margin: 3px 4px;
    min-height: 24px;
}
#addFolderBtn:hover { background: #30363d; color: #c9d1d9; border-color: #30363d; }
#addFolderBtn:pressed { background: #21262d; }

#tabCloseBtn {
    background: transparent;
    border: none;
    color: #6e7681;
    font-size: 12px;
    border-radius: 3px;
    min-width: 15px; max-width: 15px;
    min-height: 15px; max-height: 15px;
    padding: 0;
    margin-left: 2px;
}
#tabCloseBtn:hover { background: #484f58; color: #e6edf3; }

/* ── Tree ── */
QTreeWidget {
    background: #0d1117;
    border: none;
    color: #c9d1d9;
    font-family: "Consolas", monospace;
    font-size: 13px;
    outline: none;
}
QTreeWidget::item { padding: 2px 4px; min-height: 22px; }
QTreeWidget::item:hover    { background: #161b22; }
QTreeWidget::item:selected { background: #1f3a5f; color: #c9d1d9; }
QTreeWidget::branch { background: #0d1117; }

/* ── Tree action buttons (copy / explorer) ── */
#treeActionBtn {
    background: #21262d;
    border: 1px solid #30363d;
    border-radius: 4px;
    color: #8b949e;
    font-size: 11px;
    padding: 0 6px;
}
#treeActionBtn:hover { background: #0d2340; border-color: #58a6ff; color: #58a6ff; }

/* ── Preview ── */
#previewHeader {
    background: #161b22;
    border-bottom: 1px solid #30363d;
}

/* ── Status ── */
#statusBar {
    background: #161b22;
    border-top: 1px solid #30363d;
    color: #3fb950;
    font-family: "Consolas", monospace;
    font-size: 12px;
    padding: 4px 12px;
    min-height: 26px;
    max-height: 26px;
}

/* ── Search bar ── */
#searchBar {
    background: #161b22;
    border: 1px solid #30363d;
    border-radius: 4px;
}
#searchInput {
    background: #0d1117;
    border: 1px solid #30363d;
    border-radius: 4px;
    color: #c9d1d9;
    font-family: "Consolas", monospace;
    font-size: 12px;
    padding: 3px 6px;
    min-width: 180px;
}
#searchInput:focus { border-color: #58a6ff; }
#searchCount {
    font-family: "Consolas", monospace;
    font-size: 11px;
    color: #8b949e;
    padding: 0 6px;
    min-width: 40px;
}
#searchNavBtn, #searchCloseBtn {
    background: transparent;
    border: none;
    color: #8b949e;
    font-size: 14px;
    padding: 2px 4px;
    border-radius: 3px;
}
#searchNavBtn:hover, #searchCloseBtn:hover { background: #30363d; color: #c9d1d9; }

/* ── Fallback plain text ── */
QPlainTextEdit {
    background: #0d1117;
    color: #c9d1d9;
    border: none;
    font-family: "Consolas", monospace;
    font-size: 13px;
}

/* ── Scrollbars ── */
QScrollBar:vertical   { background: #0d1117; width: 8px;  margin: 0; }
QScrollBar:horizontal { background: #0d1117; height: 8px; margin: 0; }
QScrollBar::handle:vertical, QScrollBar::handle:horizontal {
    background: #30363d; border-radius: 4px; min-height: 24px; min-width: 24px;
}
QScrollBar::handle:vertical:hover, QScrollBar::handle:horizontal:hover { background: #484f58; }
QScrollBar::add-line, QScrollBar::sub-line { width: 0; height: 0; }
"""


# ── File icons / tree roles ───────────────────────────────────────────────────

_FILE_ICONS: dict[str, str] = {
    "js": "📜", "ts": "📘", "jsx": "⚛", "tsx": "⚛",
    "py": "🐍", "rb": "💎", "go": "🔵", "rs": "🦀",
    "java": "☕", "c": "⚙", "cpp": "⚙", "h": "⚙", "cs": "⚙",
    "php": "🐘", "swift": "🍎", "kt": "🟣",
    "html": "🌐", "htm": "🌐", "css": "🎨", "scss": "🎨", "less": "🎨",
    "json": "📋", "jsonc": "📋", "yaml": "📋", "yml": "📋",
    "toml": "📋", "xml": "📋", "csv": "📊", "sql": "🗄",
    "md": "📝", "mdx": "📝", "txt": "📄", "rst": "📄", "pdf": "📕",
    "png": "🖼", "jpg": "🖼", "jpeg": "🖼", "gif": "🖼",
    "svg": "🖼", "ico": "🖼", "webp": "🖼",
    "zip": "📦", "tar": "📦", "gz": "📦", "rar": "📦", "7z": "📦",
    "sh": "⚙", "ps1": "⚙", "bat": "⚙", "cmd": "⚙",
    "env": "🔑", "lock": "🔒", "db": "🗄", "sqlite": "🗄",
    "mp4": "🎬", "mp3": "🎵", "wav": "🎵",
    "dockerfile": "🐳",
}

_DIR_ROLE   = Qt.ItemDataRole.UserRole       # display path (str)
_IS_DIR     = Qt.ItemDataRole.UserRole + 1  # bool
_PATH_ROLE  = Qt.ItemDataRole.UserRole + 2  # Path object

_PLACEHOLDER    = "__pending__"
_MAX_FILE_BYTES = 2 * 1024 * 1024  # 2 MB
_IMG_EXTS = {"png", "jpg", "jpeg", "gif", "webp", "bmp", "ico", "svg"}


def _load_icon() -> QIcon:
    """加载 icon.svg，兼容开发目录和 PyInstaller 打包后的路径。"""
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).parent))
    svg = base / "icon.svg"
    return QIcon(str(svg)) if svg.exists() else QIcon()


def _enable_dark_titlebar(hwnd: int) -> None:
    """Windows 10/11 深色标题栏，激活时也保持灰色。"""
    dwm = ctypes.windll.dwmapi.DwmSetWindowAttribute
    dwm.argtypes = [
        ctypes.c_void_p,   # HWND
        ctypes.c_uint32,   # DWORD dwAttribute
        ctypes.c_void_p,   # LPCVOID pvAttribute
        ctypes.c_uint32,   # DWORD cbAttribute
    ]
    dwm.restype = ctypes.c_long

    # DWMWA_USE_IMMERSIVE_DARK_MODE — 让系统知道这是深色窗口
    dark = ctypes.c_int(1)
    for attr in (20, 19):
        dwm(hwnd, attr, ctypes.byref(dark), ctypes.sizeof(dark))

    # DWMWA_CAPTION_COLOR (35) — 直接指定标题栏背景色 (Win11 22000+)
    # DWMWA_TEXT_COLOR   (36) — 直接指定标题栏文字色
    # COLORREF 格式: 0x00BBGGRR
    caption = ctypes.c_uint32(0x00221B16)  # #161b22
    text    = ctypes.c_uint32(0x00D9D1C9)  # #c9d1d9
    dwm(hwnd, 35, ctypes.byref(caption), ctypes.sizeof(caption))
    dwm(hwnd, 36, ctypes.byref(text),    ctypes.sizeof(text))


def _file_icon(name: str) -> str:
    if name.startswith("."):
        return "⚙  "
    ext = name.rsplit(".", 1)[-1].lower() if "." in name else ""
    return _FILE_ICONS.get(ext, "📄") + "  "


# ── HTML rendering ────────────────────────────────────────────────────────────

_HTML_TPL = """<!DOCTYPE html>
<html><head><meta charset="utf-8"><meta name="color-scheme" content="dark">
<style>{style}</style></head><body>{body}</body></html>"""

_SCROLLBAR_CSS = """
::-webkit-scrollbar { width: 8px; height: 8px; }
::-webkit-scrollbar-track { background: #0d1117; }
::-webkit-scrollbar-thumb { background: #30363d; border-radius: 4px; }
::-webkit-scrollbar-thumb:hover { background: #484f58; }
"""

_BASE_CSS = "* { box-sizing: border-box; } html,body { margin:0; padding:0; background:#0d1117; color:#c9d1d9; }" + _SCROLLBAR_CSS

_MD_CSS = _BASE_CSS + """
body {
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif;
    font-size: 14px; line-height: 1.6;
    padding: 28px 36px; max-width: 900px;
}
h1,h2,h3,h4,h5,h6 { color:#e6edf3; margin: 24px 0 8px; }
h1,h2 { border-bottom: 1px solid #21262d; padding-bottom: 8px; }
a { color: #58a6ff; text-decoration: none; }
a:hover { text-decoration: underline; }
p { margin: 0 0 14px; }
code {
    background: #161b22; border: 1px solid #30363d; border-radius: 4px;
    padding: 1px 6px; font-family: "Consolas","Courier New",monospace;
    font-size: 85%; color: #ff7b72;
}
pre {
    background: #161b22; border: 1px solid #30363d; border-radius: 6px;
    padding: 16px; overflow-x: auto; line-height: 1.45; margin: 0 0 14px;
}
pre code { background:none; border:none; padding:0; color:#c9d1d9; font-size:100%; }
.codehilite { background: #161b22 !important; border: 1px solid #30363d; border-radius: 6px; overflow-x: auto; margin: 0 0 14px; }
.codehilite pre { margin:0; padding:14px 16px; background:transparent; }
blockquote { border-left:4px solid #30363d; margin:0 0 14px; padding:0 16px; color:#8b949e; }
table { border-collapse:collapse; width:100%; margin-bottom:14px; }
th,td { border:1px solid #30363d; padding:6px 12px; text-align:left; }
th { background:#161b22; color:#e6edf3; }
tr:nth-child(even) { background:#161b22; }
img { max-width:100%; border-radius:4px; }
hr { border:none; border-top:1px solid #30363d; margin:24px 0; }
ul,ol { padding-left:24px; margin-bottom:14px; }
li { margin-bottom:4px; }
"""

_CODE_CSS = _BASE_CSS + """
body { padding: 0; font-family: "Consolas","Courier New",monospace; font-size: 13px; }
.highlight { background: #0d1117 !important; margin: 0; }
.highlight pre { margin:0; padding:18px 20px; line-height:1.5; overflow-x:auto; }
table.highlighttable { width:100%; border-collapse:collapse; table-layout:fixed; }
td.linenos {
    background: #161b22; width: 52px; vertical-align:top;
    border-right: 1px solid #30363d; padding: 0;
}
td.linenos .linenodiv pre {
    background: none; margin:0; padding: 18px 10px 18px 0;
    color: #6e7681; text-align:right; line-height:1.5;
    font-size:13px; user-select:none;
}
td.code { padding:0; vertical-align:top; }
td.code .highlight pre { padding: 18px 20px; }
"""

_PLAIN_CSS = _BASE_CSS + """
pre {
    margin:0; padding:18px 20px;
    font-family:"Consolas","Courier New",monospace; font-size:13px;
    line-height:1.5; white-space:pre-wrap; word-break:break-all; color:#c9d1d9;
}
"""

_IMG_CSS = _BASE_CSS + """
body { display:flex; align-items:center; justify-content:center;
       min-height:100vh; padding:20px; }
img { max-width:100%; max-height:90vh; border-radius:4px;
      box-shadow:0 4px 24px #00000088; }
"""

_EMPTY_HTML = _HTML_TPL.format(
    style=_BASE_CSS,
    body='<div style="display:flex;align-items:center;justify-content:center;'
         'height:100vh;color:#484f58;font-size:14px;font-family:sans-serif;">'
         '点击左侧文件预览内容</div>',
)


def _build(style: str, body: str) -> str:
    return _HTML_TPL.format(style=style, body=body)


def _normalize_selected_text(text: str) -> str:
    return text.replace("\u2029", "\n").replace("\u2028", "\n")


def _format_copy_path(path: Path, start_line: int | None, end_line: int | None, text: str) -> str:
    path_text = path.as_posix()
    if start_line is not None:
        if end_line is None or end_line == start_line:
            path_text += f":{start_line}"
        else:
            path_text += f":{start_line}-{end_line}"
    return f"{path_text}\n```\n{text}\n```"


def _line_range_for_selection(path: Path, selected_text: str) -> tuple[int | None, int | None]:
    try:
        source = path.read_text(encoding="utf-8", errors="strict")
    except Exception:
        return None, None

    source = source.replace("\r\n", "\n").replace("\r", "\n")
    needle = _normalize_selected_text(selected_text).replace("\r\n", "\n").replace("\r", "\n")
    if not needle:
        return None, None

    idx = source.find(needle)
    if idx < 0 and needle.endswith("\n"):
        needle = needle.rstrip("\n")
        idx = source.find(needle)
    if idx < 0:
        return None, None

    start_line = source.count("\n", 0, idx) + 1
    selected_for_count = needle[:-1] if needle.endswith("\n") else needle
    end_line = start_line + selected_for_count.count("\n")
    return start_line, end_line


def _pygments_css(cls: str = ".highlight") -> str:
    return _HtmlFmt(style="monokai").get_style_defs(cls) if HAS_PYGMENTS else ""


def render_file(path: Path) -> tuple[str, bool]:
    """Return (html_string, is_url).
    is_url=True means html_string is a file:// URL for direct loading (images).
    """
    ext = path.suffix.lower().lstrip(".")

    # ── Images ────────────────────────────────────────────────────────────────
    if ext in _IMG_EXTS:
        url = QUrl.fromLocalFile(str(path)).toString()
        img_body = f'<img src="{url}" alt="{_html.escape(path.name)}">'
        return _build(_IMG_CSS, img_body), False

    # ── Read text ─────────────────────────────────────────────────────────────
    try:
        size = path.stat().st_size
    except OSError as e:
        return _build(_PLAIN_CSS, f"<pre>读取失败：{_html.escape(str(e))}</pre>"), False

    if size > _MAX_FILE_BYTES:
        return _build(_PLAIN_CSS, "<pre>文件太大，无法预览（超过 2 MB）</pre>"), False

    try:
        text = path.read_text(encoding="utf-8", errors="strict")
    except UnicodeDecodeError:
        return _build(_PLAIN_CSS, "<pre>二进制文件，无法预览</pre>"), False
    except Exception as e:
        return _build(_PLAIN_CSS, f"<pre>读取失败：{_html.escape(str(e))}</pre>"), False

    # ── Markdown ──────────────────────────────────────────────────────────────
    if ext in ("md", "mdx", "markdown") and HAS_MARKDOWN:
        exts = ["tables", "fenced_code", "toc"]
        ext_cfg: dict = {}
        extra_css = ""
        if HAS_PYGMENTS:
            exts.append("codehilite")
            ext_cfg["codehilite"] = {"css_class": "codehilite", "guess_lang": False}
            extra_css = _pygments_css(".codehilite")
        body = _md.markdown(text, extensions=exts, extension_configs=ext_cfg)
        return _build(_MD_CSS + extra_css, body), False

    # ── Code with Pygments ────────────────────────────────────────────────────
    if HAS_PYGMENTS:
        try:
            lexer = _lexer_for(path.name)
        except _LexerNotFound:
            lexer = None
        if lexer is not None:
            fmt = _HtmlFmt(style="monokai", linenos="table", wrapcode=True)
            pyg_css = fmt.get_style_defs(".highlight")
            highlighted = _hl(text, lexer, fmt)
            return _build(_CODE_CSS + pyg_css, highlighted), False

    # ── Plain text ────────────────────────────────────────────────────────────
    return _build(_PLAIN_CSS, f"<pre>{_html.escape(text)}</pre>"), False


# ── FolderTree ────────────────────────────────────────────────────────────────

class FolderTree(QTreeWidget):
    path_copied   = Signal(str)
    file_selected = Signal(Path)
    folder_changed = Signal(str)

    _BTN_H = 20
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

        self._watcher = QFileSystemWatcher(self)
        self._watcher.directoryChanged.connect(self._on_directory_changed)

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

    # ── hover / copy button ───────────────────────────────────────────────────

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
        # explorer button on the right, copy button to its left
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

    # ── lazy tree ─────────────────────────────────────────────────────────────

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
        root.setForeground(0, QColor("#79c0ff"))
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
                child.setForeground(0, QColor("#79c0ff"))
                try:
                    if any(entry.iterdir()):
                        QTreeWidgetItem(child).setText(0, _PLACEHOLDER)
                except OSError:
                    pass
            else:
                child.setText(0, _file_icon(entry.name) + entry.name)
                child.setForeground(0, QColor("#c9d1d9"))

    def _on_expanded(self, item: QTreeWidgetItem) -> None:
        if item.childCount() != 1 or item.child(0).text(0) != _PLACEHOLDER:
            return
        item.removeChild(item.child(0))
        folder: Path | None = item.data(0, _PATH_ROLE)
        disp: str = item.data(0, _DIR_ROLE) or ""
        if folder:
            self._fill(item, folder, disp)

    # ── file system updates ──────────────────────────────────────────────────

    def _reset_watcher(self) -> None:
        paths = self._watcher.directories()
        if paths:
            self._watcher.removePaths(paths)
        self._pending_refresh.clear()

    def _watch_dir(self, folder: Path) -> None:
        if not folder.is_dir():
            return
        path = str(folder)
        if path not in self._watcher.directories():
            self._watcher.addPath(path)

    def _on_directory_changed(self, path: str) -> None:
        self._pending_refresh.add(path)
        self._refresh_timer.start()

    def _flush_refreshes(self) -> None:
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
            item.setForeground(0, QColor("#f85149"))
            self.folder_changed.emit(disp or str(folder))
            return

        if item.parent() is None:
            self._root_exists = True
        expanded = self._expanded_dir_paths(item)
        was_expanded = item.isExpanded()
        item.takeChildren()
        if item.parent() is None:
            item.setText(0, "📂  " + folder.name)
            item.setForeground(0, QColor("#79c0ff"))
        self._fill(item, folder, disp)
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
        """展开路径并选中对应文件项。"""
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


# ── FolderTabsPanel ───────────────────────────────────────────────────────────

_ADD_FOLDER_TAB = "__add_folder_tab__"


class FolderTabBar(QTabBar):
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
        event.accept()

    def _scroll_button(self, forward: bool) -> QToolButton | None:
        buttons = [b for b in self.findChildren(QToolButton) if b.isVisible()]
        if not buttons:
            return None
        buttons.sort(key=lambda b: b.geometry().x())
        return buttons[-1] if forward else buttons[0]

    def tabSizeHint(self, index: int) -> QSize:
        size = super().tabSizeHint(index)
        if self.tabData(index) == _ADD_FOLDER_TAB:
            size.setWidth(42)
        return size

    def minimumSizeHint(self) -> QSize:
        size = super().minimumSizeHint()
        size.setWidth(0)
        return size


class HiddenTabScrollButtonStyle(QProxyStyle):
    def pixelMetric(self, metric, option=None, widget=None) -> int:
        if metric in (
            QStyle.PixelMetric.PM_TabBarScrollButtonWidth,
            QStyle.PixelMetric.PM_TabBar_ScrollButtonOverlap,
        ):
            return 0
        return super().pixelMetric(metric, option, widget)


class FolderTabsPanel(QWidget):
    """左侧多文件夹标签页面板。"""

    file_selected = Signal(Path)
    path_copied   = Signal(str)
    folder_changed = Signal(str)

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

        self.stack = QStackedWidget()
        self.stack.setMinimumWidth(0)
        self._tab_widgets: list[FolderTree] = []
        self._last_real_index = -1
        self._add_control_tabs()

        layout.addWidget(header)
        layout.addWidget(self.stack, 1)
        self._last_dir = str(Path.home())

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

    def _on_current_changed(self, idx: int) -> None:
        if self._is_add_tab(idx):
            return
        if 0 <= idx < self.stack.count():
            self._last_real_index = idx
            self.stack.setCurrentIndex(idx)

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

    # ── Public session helpers ────────────────────────────────────────────────

    def open_path(self, path_str: str) -> None:
        """直接用路径字符串打开文件夹（供会话恢复调用）。"""
        p = Path(path_str)
        if p.is_dir():
            self._open(p)

    def open_paths(self) -> list[str]:
        """返回当前所有标签页的文件夹路径。"""
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
        btn.setFixedSize(15, 15)
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
        """在对应的文件夹标签树中定位并选中文件。"""
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


# ── Search highlight JS (injected into WebEngine pages) ───────────────────────

_SEARCH_JS = r"""
window._searchHL = {
  marks: [], idx: -1,
  _result(idx, total) { return { idx, total }; },
  clear() {
    this.marks.forEach(m => { const p = m.parentNode; p.replaceChild(document.createTextNode(m.textContent), m); p.normalize(); });
    this.marks = []; this.idx = -1;
  },
  find(q) {
    this.clear();
    if (!q) return this._result(-1, 0);
    const qL = q.toLowerCase();
    const w = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
    const nodes = [];
    while (w.nextNode()) {
      const n = w.currentNode, tag = n.parentElement?.tagName;
      if (tag === 'SCRIPT' || tag === 'STYLE' || tag === 'MARK') continue;
      if (n.textContent.toLowerCase().includes(qL)) nodes.push(n);
    }
    for (let i = nodes.length - 1; i >= 0; i--) {
      const node = nodes[i], text = node.textContent;
      const frag = document.createDocumentFragment();
      let last = 0; const lo = text.toLowerCase(); let pos;
      while ((pos = lo.indexOf(qL, last)) !== -1) {
        if (pos > last) frag.appendChild(document.createTextNode(text.slice(last, pos)));
        const mark = document.createElement('mark');
        mark.setAttribute('data-shl', '');
        mark.textContent = text.slice(pos, pos + q.length);
        frag.appendChild(mark);
        last = pos + q.length;
      }
      if (last < text.length) frag.appendChild(document.createTextNode(text.slice(last)));
      node.parentNode.replaceChild(frag, node);
    }
    this.marks = Array.from(document.querySelectorAll('mark[data-shl]'));
    return this.marks.length ? this._goto(0) : this._result(-1, 0);
  },
  _goto(i) {
    this.marks.forEach(m => { m.style.cssText = 'background:#ff954f80;color:inherit;border-radius:2px;padding:0 1px;'; });
    this.idx = i;
    const m = this.marks[i];
    m.style.cssText = 'background:#f0883e;color:#0d1117;border-radius:2px;padding:0 1px;outline:2px solid #f0883e;';
    m.scrollIntoView({ behavior: 'smooth', block: 'center' });
    return this._result(this.idx, this.marks.length);
  },
  next() { return this.marks.length ? this._goto((this.idx + 1) % this.marks.length) : this._result(-1, 0); },
  prev() { return this.marks.length ? this._goto((this.idx - 1 + this.marks.length) % this.marks.length) : this._result(-1, 0); },
};
"""


_SELECTION_INFO_JS = r"""
(function () {
  const sel = window.getSelection();
  if (!sel || sel.rangeCount === 0 || sel.isCollapsed) return null;
  const text = sel.toString();
  const range = sel.getRangeAt(0);

  function closestPre(node) {
    const el = node.nodeType === Node.ELEMENT_NODE ? node : node.parentElement;
    return el ? el.closest("pre") : null;
  }

  const root = closestPre(range.startContainer);
  if (!root || root !== closestPre(range.endContainer)) {
    return { text, startLine: null, endLine: null };
  }

  const beforeRange = document.createRange();
  beforeRange.selectNodeContents(root);
  beforeRange.setEnd(range.startContainer, range.startOffset);

  const beforeText = beforeRange.toString();
  const startLine = beforeText.split("\n").length;
  const selectedForCount = text.endsWith("\n") ? text.slice(0, -1) : text;
  const selectedLines = selectedForCount ? selectedForCount.split("\n").length : 1;

  return {
    text,
    startLine,
    endLine: startLine + selectedLines - 1
  };
})()
"""


class PreviewWebView(QWebEngineView if HAS_WEBENGINE else QWidget):
    path_copied = Signal(str)

    def __init__(self) -> None:
        super().__init__()
        self.current_path: Path | None = None
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._show_context_menu)

    def _show_context_menu(self, pos) -> None:
        if not self.current_path:
            return

        global_pos = self.mapToGlobal(pos)

        def show_menu(info) -> None:
            selected = self.page().selectedText()
            if isinstance(info, dict):
                text = _normalize_selected_text(str(info.get("text") or selected))
                start_line = info.get("startLine")
                end_line = info.get("endLine")
            else:
                text = _normalize_selected_text(selected)
                start_line = None
                end_line = None
            if not text:
                return
            if not isinstance(start_line, int):
                start_line = None
            if not isinstance(end_line, int):
                end_line = None
            if start_line is None:
                start_line, end_line = _line_range_for_selection(self.current_path, text)

            menu = QMenu(self)
            copy_path = menu.addAction("Copy Path")
            copy_text = menu.addAction("Copy")
            action = menu.exec(global_pos)
            if action is copy_path:
                clip = _format_copy_path(self.current_path, start_line, end_line, text)
                QApplication.clipboard().setText(clip)
                self.path_copied.emit(clip)
            elif action is copy_text:
                QApplication.clipboard().setText(text)

        self.page().runJavaScript(_SELECTION_INFO_JS, show_menu)


class PreviewPlainTextEdit(QPlainTextEdit):
    path_copied = Signal(str)

    def __init__(self) -> None:
        super().__init__()
        self.current_path: Path | None = None
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._show_context_menu)

    def _show_context_menu(self, pos) -> None:
        cursor = self.textCursor()
        text = _normalize_selected_text(cursor.selectedText())
        if not self.current_path or not text:
            return

        start = cursor.selectionStart()
        end = cursor.selectionEnd()
        doc = self.document()
        start_line = doc.findBlock(start).blockNumber() + 1
        end_pos = max(start, end - 1)
        end_line = doc.findBlock(end_pos).blockNumber() + 1

        menu = QMenu(self)
        copy_path = menu.addAction("Copy Path")
        copy_text = menu.addAction("Copy")
        action = menu.exec(self.mapToGlobal(pos))
        if action is copy_path:
            clip = _format_copy_path(self.current_path, start_line, end_line, text)
            QApplication.clipboard().setText(clip)
            self.path_copied.emit(clip)
        elif action is copy_text:
            QApplication.clipboard().setText(text)


# ── PreviewPane ───────────────────────────────────────────────────────────────

class PreviewTabBar(QTabBar):
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
        event.accept()

    def _scroll_button(self, forward: bool) -> QToolButton | None:
        buttons = [b for b in self.findChildren(QToolButton) if b.isVisible()]
        if not buttons:
            return None
        buttons.sort(key=lambda b: b.geometry().x())
        return buttons[-1] if forward else buttons[0]

    def tabSizeHint(self, index: int) -> QSize:
        size = super().tabSizeHint(index)
        size.setWidth(max(size.width(), 100))
        return size

    def minimumSizeHint(self) -> QSize:
        size = super().minimumSizeHint()
        size.setWidth(0)
        return size


class PreviewPane(QWidget):
    """右侧文件内容预览面板，多标签页 + Ctrl+F 搜索高亮。"""
    path_copied = Signal(str)
    file_tab_switched = Signal(Path)

    def __init__(self) -> None:
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # ── 标签栏 ──────────────────────────────────────────────────────────
        self._tab_bar = PreviewTabBar()
        self._tab_bar_style = HiddenTabScrollButtonStyle()
        self._tab_bar.setStyle(self._tab_bar_style)
        self._tab_bar.setMovable(True)
        self._tab_bar.setDocumentMode(True)
        self._tab_bar.setExpanding(False)
        self._tab_bar.setUsesScrollButtons(True)
        self._tab_bar.setElideMode(Qt.TextElideMode.ElideMiddle)
        self._tab_bar.currentChanged.connect(self._on_tab_changed)
        self._tab_bar.tabMoved.connect(self._on_tab_moved)

        tab_header = QWidget()
        tab_header.setObjectName("previewHeader")
        thl = QHBoxLayout(tab_header)
        thl.setContentsMargins(0, 0, 0, 0)
        thl.setSpacing(0)
        thl.addWidget(self._tab_bar, 1)
        layout.addWidget(tab_header)

        # ── 内容区 ──────────────────────────────────────────────────────────
        self._stack = QStackedWidget()
        layout.addWidget(self._stack, 1)

        # path → { "tab_idx": int, "view": PreviewWebView|PreviewPlainTextEdit }
        self._tabs: dict[Path, dict] = {}
        self._ordered_paths: list[Path] = []
        self._current_path: Path | None = None
        self._js_ready = False
        self._block_tab_signal = False

        # ── 搜索栏（默认隐藏）──────────────────────────────────────────────
        self._search_bar = QWidget(self)
        self._search_bar.setObjectName("searchBar")
        self._search_bar.setFixedSize(420, 36)
        self._search_bar.hide()
        sl = QHBoxLayout(self._search_bar)
        sl.setContentsMargins(8, 4, 8, 4)
        sl.setSpacing(4)

        self._search_input = QLineEdit()
        self._search_input.setObjectName("searchInput")
        self._search_input.setPlaceholderText("搜索…")
        self._search_input.setClearButtonEnabled(True)
        sl.addWidget(self._search_input, 1)

        self._search_count = QLabel("")
        self._search_count.setObjectName("searchCount")
        sl.addWidget(self._search_count)

        prev_btn = QPushButton("▲")
        prev_btn.setObjectName("searchNavBtn")
        prev_btn.setFixedSize(24, 24)
        prev_btn.setToolTip("上一个 (Shift+Enter)")
        prev_btn.clicked.connect(lambda: self._search_nav(True))
        sl.addWidget(prev_btn)

        next_btn = QPushButton("▼")
        next_btn.setObjectName("searchNavBtn")
        next_btn.setFixedSize(24, 24)
        next_btn.setToolTip("下一个 (Enter)")
        next_btn.clicked.connect(lambda: self._search_nav(False))
        sl.addWidget(next_btn)

        close_btn = QPushButton("×")
        close_btn.setObjectName("searchCloseBtn")
        close_btn.setFixedSize(24, 24)
        close_btn.setToolTip("关闭 (Escape)")
        close_btn.clicked.connect(self.close_search)
        sl.addWidget(close_btn)

        self._search_input.textChanged.connect(self._search_fresh)
        self._search_input.installEventFilter(self)

    # ── Tab management ───────────────────────────────────────────────────────

    def _create_view(self):
        if HAS_WEBENGINE:
            view = PreviewWebView()
            view.path_copied.connect(self.path_copied)
            view.setHtml(_EMPTY_HTML)
        else:
            view = PreviewPlainTextEdit()
            view.path_copied.connect(self.path_copied)
            view.setReadOnly(True)
            view.setPlaceholderText(
                "提示：安装 PySide6[WebEngine] 可获得 Markdown/代码高亮预览"
            )
        return view

    def _current_view(self):
        return self._stack.currentWidget()

    def show_file(self, path: Path) -> None:
        self._block_tab_signal = True
        try:
            if path in self._tabs:
                idx = self._tab_index_for(path)
                if idx is not None:
                    self._tab_bar.setCurrentIndex(idx)
                return

            view = self._create_view()
            self._tabs[path] = {"view": view}
            self._ordered_paths.append(path)

            idx = self._tab_bar.addTab(path.name)
            self._tab_bar.setTabData(idx, path)
            self._tab_bar.setTabToolTip(idx, str(path).replace("\\", "/"))
            self._attach_close_btn(idx, path)
            self._stack.addWidget(view)
            self._tab_bar.setCurrentIndex(idx)

            self._render_in_view(view, path)
        finally:
            self._block_tab_signal = False

    def _tab_index_for(self, path: Path) -> int | None:
        for i in range(self._tab_bar.count()):
            if self._tab_bar.tabData(i) is path:
                return i
        return None

    def _attach_close_btn(self, idx: int, path: Path) -> None:
        btn = QPushButton("×")
        btn.setObjectName("tabCloseBtn")
        btn.setFlat(True)
        btn.setFixedSize(15, 15)
        btn.setToolTip("关闭")
        btn.clicked.connect(lambda: self._close_tab(path))
        self._tab_bar.setTabButton(idx, QTabBar.ButtonPosition.RightSide, btn)

    def _close_tab(self, path: Path) -> None:
        if path not in self._tabs:
            return
        info = self._tabs.pop(path)
        view = info["view"]
        self._ordered_paths.remove(path)

        idx = self._tab_index_for(path)
        if idx is not None:
            self._tab_bar.removeTab(idx)
        self._stack.removeWidget(view)
        view.deleteLater()

        if self._current_path == path:
            self._current_path = None
            if self._ordered_paths:
                new_path = self._ordered_paths[-1]
                new_idx = self._tab_index_for(new_path)
                if new_idx is not None:
                    self._tab_bar.setCurrentIndex(new_idx)
            else:
                self._js_ready = False

    def _on_tab_changed(self, idx: int) -> None:
        if idx < 0:
            return
        path: Path | None = self._tab_bar.tabData(idx)
        if path is None or path not in self._tabs:
            return
        self._current_path = path
        self._js_ready = False
        info = self._tabs[path]
        self._stack.setCurrentWidget(info["view"])

        if HAS_WEBENGINE and isinstance(info["view"], PreviewWebView):
            info["view"].page().runJavaScript(_SEARCH_JS)
            self._js_ready = True

        if not getattr(self, "_block_tab_signal", False):
            self.file_tab_switched.emit(path)

    def _on_tab_moved(self, from_idx: int, to_idx: int) -> None:
        pass  # tabData stays attached, no reordering of _ordered_paths needed

    # ── File rendering ───────────────────────────────────────────────────────

    def _render_in_view(self, view, path: Path) -> None:
        self._current_path = path
        self._js_ready = False
        if HAS_WEBENGINE and isinstance(view, PreviewWebView):
            view.current_path = path
        elif isinstance(view, PreviewPlainTextEdit):
            view.current_path = path

        if self._search_bar.isVisible():
            self.close_search()

        if not HAS_WEBENGINE:
            try:
                text = path.read_text(encoding="utf-8", errors="replace")[:200_000]
            except Exception as e:
                text = str(e)
            view.setPlainText(text)
            return

        html_str, _ = render_file(path)
        base_url = QUrl.fromLocalFile(str(path.parent) + "/")
        view.setHtml(html_str, base_url)
        view.loadFinished.connect(
            lambda ok: (view.page().runJavaScript("window.scrollTo(0,0);"),
                        self._inject_search_js()) if ok else None,
            Qt.ConnectionType.SingleShotConnection,
        )

    # ── Search ───────────────────────────────────────────────────────────────

    def eventFilter(self, obj, event) -> bool:
        if obj is self._search_input:
            if event.type() == QEvent.Type.KeyPress:
                key = event.key()
                if key == Qt.Key.Key_Escape:
                    self.close_search()
                    return True
                if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                    backward = bool(event.modifiers() & Qt.KeyboardModifier.ShiftModifier)
                    self._search_nav(backward)
                    return True
        return super().eventFilter(obj, event)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._position_search_bar()

    def _position_search_bar(self) -> None:
        margin = 10
        available = max(160, self.width() - margin * 2)
        width = min(420, available)
        height = 36
        x = max(margin, self.width() - width - margin)
        y = self._tab_bar.parentWidget().height() + margin
        self._search_bar.setFixedSize(width, height)
        self._search_bar.move(x, y)
        self._search_bar.raise_()

    def open_search(self) -> None:
        self._position_search_bar()
        self._search_bar.show()
        self._search_bar.raise_()
        self._search_input.setFocus()
        self._search_input.selectAll()

    def close_search(self) -> None:
        self._search_bar.hide()
        self._js_eval("window._searchHL && window._searchHL.clear()")
        self._search_count.setText("")

    def _js_eval(self, expr: str, callback=None) -> None:
        view = self._current_view()
        if not (HAS_WEBENGINE and isinstance(view, PreviewWebView) and self._js_ready):
            return
        if callback:
            view.page().runJavaScript(expr, callback)
        else:
            view.page().runJavaScript(expr)

    def _search_fresh(self) -> None:
        query = self._search_input.text()
        if not query:
            self._js_eval("window._searchHL && window._searchHL.clear()")
            self._search_count.setText("")
            return
        js_q = json.dumps(query)
        self._js_eval(
            f"JSON.stringify(window._searchHL ? window._searchHL.find({js_q}) : {{idx:-1,total:0}})",
            self._on_nav_result,
        )

    def _search_nav(self, backward: bool) -> None:
        method = "prev" if backward else "next"
        self._js_eval(
            f"JSON.stringify(window._searchHL ? window._searchHL.{method}() : {{idx:-1,total:0}})",
            self._on_nav_result,
        )

    def _as_non_bool_int(self, value) -> int | None:
        if isinstance(value, bool):
            return None
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    def _on_nav_result(self, result) -> None:
        if isinstance(result, str):
            try:
                result = json.loads(result)
            except json.JSONDecodeError:
                result = None

        if isinstance(result, dict):
            idx = result.get("idx")
            total = result.get("total")
            idx_i = self._as_non_bool_int(idx)
            total_i = self._as_non_bool_int(total)
            if total_i is not None and total_i > 0 and idx_i is not None and idx_i >= 0:
                self._search_count.setText(f"{idx_i + 1}/{total_i}")
            else:
                self._search_count.setText("无结果")
        elif isinstance(result, (list, tuple)) and len(result) == 2:
            idx, total = result
            idx_i = self._as_non_bool_int(idx)
            total_i = self._as_non_bool_int(total)
            if total_i is not None and total_i > 0 and idx_i is not None and idx_i >= 0:
                self._search_count.setText(f"{idx_i + 1}/{total_i}")
            else:
                self._search_count.setText("无结果")
        else:
            self._search_count.setText("无结果")

    def _inject_search_js(self) -> None:
        view = self._current_view()
        if HAS_WEBENGINE and isinstance(view, PreviewWebView):
            view.page().runJavaScript(_SEARCH_JS)
            self._js_ready = True


# ── MainWindow ────────────────────────────────────────────────────────────────

class MainWindow(QMainWindow):
    def __init__(self, icon: QIcon) -> None:
        super().__init__()
        self.setWindowTitle("Folder Location")
        self.setWindowIcon(icon)
        self.resize(1440, 840)
        self.setMinimumSize(900, 500)

        central = QWidget()
        self.setCentralWidget(central)
        vl = QVBoxLayout(central)
        vl.setContentsMargins(0, 0, 0, 0)
        vl.setSpacing(0)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setHandleWidth(1)
        splitter.setChildrenCollapsible(False)

        self.folder_panel = FolderTabsPanel()
        self.preview = PreviewPane()

        splitter.addWidget(self.folder_panel)
        splitter.addWidget(self.preview)
        splitter.setSizes([400, 1040])
        vl.addWidget(splitter, 1)

        # 状态栏
        self._status = QLabel()
        self._status.setObjectName("statusBar")
        self._fade = QTimer(self)
        self._fade.setSingleShot(True)
        self._fade.setInterval(3000)
        self._fade.timeout.connect(lambda: self._status.setText(""))
        vl.addWidget(self._status)

        self.folder_panel.file_selected.connect(self.preview.show_file)
        self.folder_panel.path_copied.connect(self._on_copied)
        self.folder_panel.folder_changed.connect(self._on_folder_changed)
        self.preview.path_copied.connect(self._on_copied)
        self.preview.file_tab_switched.connect(self._on_preview_tab_switched)

        # 快捷键
        from PySide6.QtGui import QShortcut, QKeySequence
        QShortcut(QKeySequence("Ctrl+O"), self).activated.connect(
            self.folder_panel.add_folder
        )
        QShortcut(QKeySequence("Ctrl+F"), self).activated.connect(
            self.preview.open_search
        )

        self._quitting = False
        self._setup_tray(icon)

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
        if visible:
            self._show_act.setText("隐藏窗口")
        else:
            self._show_act.setText("显示窗口")

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
        self._update_tray_menu()

    def showEvent(self, event) -> None:
        super().showEvent(event)
        if not getattr(self, '_titlebar_fixed', False):
            self._titlebar_fixed = True
            _enable_dark_titlebar(int(self.winId()))

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

    # ── Session persistence ───────────────────────────────────────────────────

    _SETTINGS_ORG = "FolderTree"
    _SETTINGS_APP = "FolderTree"

    def save_session(self) -> None:
        s = QSettings(self._SETTINGS_ORG, self._SETTINGS_APP)
        s.setValue("session/folders",  self.folder_panel.open_paths())
        s.setValue("session/last_dir", self.folder_panel._last_dir)

    def restore_session(self) -> None:
        s = QSettings(self._SETTINGS_ORG, self._SETTINGS_APP)
        last_dir = s.value("session/last_dir", "")
        if last_dir:
            self.folder_panel._last_dir = last_dir

        paths = s.value("session/folders", [])
        if isinstance(paths, str):          # QSettings 单值时返回裸字符串
            paths = [paths] if paths else []
        for p in paths or []:
            self.folder_panel.open_path(str(p))

    # ── Status bar ────────────────────────────────────────────────────────────

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
        self.folder_panel.navigate_to_file(path)


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)   # 关闭窗口不退出，托盘仍在运行
    apply_dark_palette(app)
    app.setStyleSheet(STYLESHEET)

    icon = _load_icon()
    app.setWindowIcon(icon)

    win = MainWindow(icon)
    win.show()
    win.restore_session()                    # 恢复上次打开的文件夹
    app.aboutToQuit.connect(win.save_session)  # 退出前保存
    sys.exit(app.exec())
