"""主题与样式 — 黑白极简风格，类似 X / Twitter。"""
import sys
import ctypes
from pathlib import Path

from PySide6.QtWidgets import QApplication, QWidget, QProxyStyle, QStyle
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPalette, QIcon


# ── 调色板 ────────────────────────────────────────────────────────────────────
# 灵感来自 X (Twitter) 暗色模式：纯黑底 + 高对比白字 + 极淡边框

BG          = "#000000"   # 主背景
BG_ELEV     = "#16181c"   # 略提升的面板（顶栏、状态栏等）
BG_HOVER    = "#1a1c20"
BG_ACTIVE   = "#1d1f23"
BORDER      = "#2f3336"
BORDER_SOFT = "#202327"
FG          = "#e7e9ea"   # 主文字
FG_DIM      = "#71767b"   # 次要文字
FG_SOFT     = "#536471"
ACCENT      = "#ffffff"   # 高亮（按钮文字 / 选中边）
DANGER      = "#f4212e"
SUCCESS     = "#00ba7c"


def apply_dark_palette(app: QApplication) -> None:
    app.setStyle("Fusion")
    p = QPalette()
    p.setColor(QPalette.ColorRole.Window,          QColor(BG))
    p.setColor(QPalette.ColorRole.WindowText,      QColor(FG))
    p.setColor(QPalette.ColorRole.Base,            QColor(BG))
    p.setColor(QPalette.ColorRole.AlternateBase,   QColor(BG_ELEV))
    p.setColor(QPalette.ColorRole.Text,            QColor(FG))
    p.setColor(QPalette.ColorRole.Button,          QColor(BG_ELEV))
    p.setColor(QPalette.ColorRole.ButtonText,      QColor(FG))
    p.setColor(QPalette.ColorRole.Highlight,       QColor("#ffffff"))
    p.setColor(QPalette.ColorRole.HighlightedText, QColor("#000000"))
    p.setColor(QPalette.ColorRole.Link,            QColor(FG))
    p.setColor(QPalette.ColorRole.Mid,             QColor(BORDER))
    p.setColor(QPalette.ColorRole.Dark,            QColor(BG_ELEV))
    p.setColor(QPalette.ColorRole.Shadow,          QColor("#000000"))
    app.setPalette(p)


# ── 样式表 ────────────────────────────────────────────────────────────────────

STYLESHEET = f"""
QMainWindow, QWidget {{ background: {BG}; color: {FG}; font-family: -apple-system, "Segoe UI", "PingFang SC", "Microsoft YaHei", sans-serif; }}

QSplitter::handle:horizontal {{ background: {BORDER_SOFT}; width: 1px; }}
QSplitter::handle:vertical   {{ background: {BORDER_SOFT}; height: 1px; }}

/* ── 文件夹标签页头部 ── */
#folderTabsHeader {{
    background: {BG};
    border-bottom: 1px solid {BORDER_SOFT};
}}
QTabBar {{ background: {BG}; }}
QTabBar::tab {{
    background: transparent;
    color: {FG_DIM};
    border: none;
    padding: 8px 14px 8px 14px;
    min-width: 60px;
    max-width: 200px;
    margin: 0;
    font-size: 13px;
}}
QTabBar::tab:selected {{
    background: transparent;
    color: {FG};
    border-bottom: 2px solid {FG};
    font-weight: 600;
}}
QTabBar::tab:hover:!selected {{ color: {FG}; background: {BG_HOVER}; }}
QTabBar QToolButton {{
    background: transparent; border: none; padding: 0; margin: 0;
    min-width: 0; max-width: 0; min-height: 0; max-height: 0;
    width: 0; height: 0;
}}
QTabBar QToolButton::left-arrow, QTabBar QToolButton::right-arrow {{
    image: none; width: 0; height: 0;
}}

/* ── 添加按钮 / 通用主按钮 ── */
#addFolderBtn {{
    background: transparent;
    border: 1px solid transparent;
    border-radius: 999px;
    color: {FG_DIM};
    font-size: 18px;
    font-weight: 500;
    padding: 0 12px;
    margin: 4px 6px;
    min-height: 28px;
    min-width: 28px;
}}
#addFolderBtn:hover {{ background: {BG_HOVER}; color: {FG}; }}
#addFolderBtn:pressed {{ background: {BG_ACTIVE}; }}

/* ── 文件夹标签页滚动条 ── */
QScrollBar#tabScrollBar:horizontal {{ background: {BG}; height: 6px; margin: 0; border: none; }}
QScrollBar#tabScrollBar::handle:horizontal {{ background: {BORDER}; border-radius: 3px; min-width: 24px; }}
QScrollBar#tabScrollBar::handle:horizontal:hover {{ background: {FG_SOFT}; }}
QScrollBar#tabScrollBar::add-line, QScrollBar#tabScrollBar::sub-line {{ width: 0; height: 0; }}

#tabCloseBtn {{
    background: transparent;
    border: none;
    color: {FG_DIM};
    font-size: 14px;
    border-radius: 999px;
    min-width: 18px; max-width: 18px;
    min-height: 18px; max-height: 18px;
    padding: 0;
    margin-left: 4px;
    margin-right: 6px;
}}
#tabCloseBtn:hover {{ background: {BORDER}; color: {FG}; }}

/* ── 文件树 ── */
QTreeWidget {{
    background: {BG};
    border: none;
    color: {FG};
    font-family: "JetBrains Mono", "Consolas", monospace;
    font-size: 13px;
    outline: none;
}}
QTreeWidget::item {{ padding: 4px 6px; min-height: 24px; border-radius: 6px; }}
QTreeWidget::item:hover    {{ background: {BG_HOVER}; }}
QTreeWidget::item:selected {{ background: {BG_ACTIVE}; color: {FG}; }}
QTreeWidget::branch {{ background: {BG}; }}

/* ── 树行操作按钮（Copy / Open） ── */
#treeActionBtn {{
    background: transparent;
    border: 1px solid {BORDER};
    border-radius: 999px;
    color: {FG_DIM};
    font-size: 11px;
    padding: 0 10px;
}}
#treeActionBtn:hover {{ background: {FG}; color: #000000; border-color: {FG}; }}

/* ── 预览头 ── */
#previewHeader {{
    background: {BG};
    border-bottom: 1px solid {BORDER_SOFT};
}}

/* ── 浏览器 ── */
#browserToolbar {{
    background: {BG};
    border-bottom: 1px solid {BORDER_SOFT};
}}
#browserNavBtn {{
    background: transparent;
    border: 1px solid {BORDER};
    border-radius: 999px;
    color: {FG};
    font-size: 13px;
    padding: 0 12px;
    min-width: 30px;
}}
#browserNavBtn:hover {{ background: {BG_HOVER}; border-color: {FG_SOFT}; }}
#browserNavBtn:pressed {{ background: {BG_ACTIVE}; }}
#browserNavBtn:disabled {{ color: {BORDER}; background: transparent; border-color: {BORDER_SOFT}; }}
#browserUrlInput {{
    background: {BG_ELEV};
    border: 1px solid {BORDER};
    border-radius: 999px;
    color: {FG};
    font-size: 13px;
    padding: 0 14px;
}}
#browserUrlInput:focus {{ border-color: {FG}; background: {BG}; }}
#browserFallback {{
    background: {BG};
    color: {FG_DIM};
    font-size: 14px;
}}

/* ── 状态栏 ── */
#statusBar {{
    background: {BG};
    border-top: 1px solid {BORDER_SOFT};
    min-height: 30px;
    max-height: 30px;
}}
#statusBarText {{
    color: {FG_DIM};
    font-family: "JetBrains Mono", "Consolas", monospace;
    font-size: 12px;
    padding: 0 4px;
}}

/* ── 搜索栏 ── */
#searchBar {{
    background: {BG_ELEV};
    border: 1px solid {BORDER};
    border-radius: 12px;
}}
#searchInput {{
    background: {BG};
    border: 1px solid {BORDER};
    border-radius: 999px;
    color: {FG};
    font-family: "JetBrains Mono", "Consolas", monospace;
    font-size: 12px;
    padding: 5px 12px;
    min-width: 180px;
}}
#searchInput:focus {{ border-color: {FG}; }}
#searchCount {{
    font-family: "JetBrains Mono", "Consolas", monospace;
    font-size: 11px;
    color: {FG_DIM};
    padding: 0 8px;
    min-width: 40px;
}}
#searchNavBtn, #searchCloseBtn {{
    background: transparent;
    border: none;
    color: {FG_DIM};
    font-size: 14px;
    padding: 2px 4px;
    border-radius: 999px;
}}
#searchNavBtn:hover, #searchCloseBtn:hover {{ background: {BG_HOVER}; color: {FG}; }}

/* ── 纯文本预览回退 ── */
QPlainTextEdit {{
    background: {BG};
    color: {FG};
    border: none;
    font-family: "JetBrains Mono", "Consolas", monospace;
    font-size: 13px;
    padding: 12px;
}}

/* ── 通用滚动条 ── */
QScrollBar:vertical   {{ background: {BG}; width: 8px;  margin: 0; }}
QScrollBar:horizontal {{ background: {BG}; height: 8px; margin: 0; }}
QScrollBar::handle:vertical, QScrollBar::handle:horizontal {{
    background: {BORDER}; border-radius: 4px; min-height: 24px; min-width: 24px;
}}
QScrollBar::handle:vertical:hover, QScrollBar::handle:horizontal:hover {{ background: {FG_SOFT}; }}
QScrollBar::add-line, QScrollBar::sub-line {{ width: 0; height: 0; }}

/* ── 侧边栏 ── */
#sidebarStrip {{
    background: {BG};
    border-right: 1px solid {BORDER_SOFT};
}}
#sidebarBtn {{
    background: transparent;
    border: 1px solid transparent;
    border-radius: 999px;
    color: {FG_DIM};
    font-size: 16px;
    padding: 2px;
}}
#sidebarBtn:hover {{ background: {BG_HOVER}; color: {FG}; }}
#sidebarBtn:checked {{ background: {FG}; color: #000000; border-color: {FG}; }}
#sidebarToggleBtn {{
    background: transparent;
    border: 1px solid transparent;
    border-radius: 999px;
    color: {FG_DIM};
    font-size: 14px;
    padding: 2px;
}}
#sidebarToggleBtn:hover {{ background: {BG_HOVER}; color: {FG}; }}

/* ── 历史面板 ── */
#historyHeader {{
    background: {BG};
    border-bottom: 1px solid {BORDER_SOFT};
    color: {FG};
    font-size: 14px;
    font-weight: 600;
    padding-left: 14px;
}}
QScrollArea#historyScroll {{ border: none; background: transparent; }}
#historyRow {{
    background: {BG};
    border: none;
    border-bottom: 1px solid {BORDER_SOFT};
}}
#historyRow:hover {{ background: {BG_HOVER}; }}
#historyTime {{
    color: {FG_DIM};
    font-size: 11px;
    font-family: "JetBrains Mono", "Consolas", monospace;
}}
#historyName {{
    color: {FG};
    font-size: 12px;
    font-family: "JetBrains Mono", "Consolas", monospace;
}}
#historyEmpty {{
    color: {FG_SOFT};
    font-size: 13px;
    padding: 24px;
}}
"""


# ── 文件图标 ──────────────────────────────────────────────────────────────────

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


def _file_icon(name: str) -> str:
    if name.startswith("."):
        return "⚙  "
    ext = name.rsplit(".", 1)[-1].lower() if "." in name else ""
    return _FILE_ICONS.get(ext, "📄") + "  "


# ── 图标加载 ──────────────────────────────────────────────────────────────────

def _load_icon() -> QIcon:
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).parent))
    if sys.platform == "win32":
        ico = base / "icon.ico"
        if ico.exists():
            return QIcon(str(ico))
    svg = base / "icon.svg"
    return QIcon(str(svg)) if svg.exists() else QIcon()


# ── Windows 深色标题栏 ────────────────────────────────────────────────────────

def _enable_dark_titlebar(hwnd: int) -> None:
    if sys.platform != "win32" or not hwnd:
        return
    dwm = ctypes.windll.dwmapi.DwmSetWindowAttribute
    dwm.argtypes = [ctypes.c_void_p, ctypes.c_uint32, ctypes.c_void_p, ctypes.c_uint32]
    dwm.restype = ctypes.c_long
    dark = ctypes.c_int(1)
    for attr in (20, 19):
        dwm(hwnd, attr, ctypes.byref(dark), ctypes.sizeof(dark))
    # 纯黑标题栏
    caption = ctypes.c_uint32(0x00000000)
    text    = ctypes.c_uint32(0x00EAE9E7)  # FG 反转 BBGGRR
    dwm(hwnd, 35, ctypes.byref(caption), ctypes.sizeof(caption))
    dwm(hwnd, 36, ctypes.byref(text),    ctypes.sizeof(text))


def _apply_dark_titlebar(widget: QWidget) -> None:
    try:
        _enable_dark_titlebar(int(widget.winId()))
    except Exception:
        pass


# ── Tab scroll button hider ──────────────────────────────────────────────────

class HiddenTabScrollButtonStyle(QProxyStyle):
    def pixelMetric(self, metric, option=None, widget=None) -> int:
        if metric in (
            QStyle.PixelMetric.PM_TabBarScrollButtonWidth,
            QStyle.PixelMetric.PM_TabBar_ScrollButtonOverlap,
        ):
            return 0
        return super().pixelMetric(metric, option, widget)
