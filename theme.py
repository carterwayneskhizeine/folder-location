"""主题与样式 — 黑白极简风格，类似 X / Twitter。"""
import sys
import ctypes
from pathlib import Path

from PySide6.QtWidgets import QApplication, QWidget, QProxyStyle, QStyle
from PySide6.QtCore import Qt, QByteArray
from PySide6.QtGui import QColor, QPalette, QIcon, QPixmap, QImage

try:
    from pytablericons import TablerIcons, OutlineIcon
    HAS_TABLER = True
except ImportError:
    HAS_TABLER = False


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
    min-height: 36px;
    max-height: 36px;
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
    padding: 0 10px;
    margin: 0 4px;
    max-height: 28px;
    min-width: 28px;
}}
#addFolderBtn:hover {{ background: {BG_HOVER}; color: {FG}; }}
#addFolderBtn:pressed {{ background: {BG_ACTIVE}; }}

/* ── 标签页横向滚动条（复古 Windows 长方形风格） ── */
QScrollBar#tabScrollBar:horizontal {{
    background: {BG_ELEV};
    height: 16px;
    margin: 0;
    border-top: 1px solid {BORDER};
}}
QScrollBar#tabScrollBar::handle:horizontal {{
    background: {BORDER};
    border: 1px solid {FG_SOFT};
    border-radius: 0px;
    min-width: 32px;
}}
QScrollBar#tabScrollBar::handle:horizontal:hover {{
    background: {FG_DIM};
    border-color: {FG};
}}
QScrollBar#tabScrollBar::handle:horizontal:pressed {{
    background: {FG};
    border-color: {FG};
}}
QScrollBar#tabScrollBar::add-line:horizontal, QScrollBar#tabScrollBar::sub-line:horizontal {{
    width: 0; height: 0;
}}
QScrollBar#tabScrollBar::add-page:horizontal, QScrollBar#tabScrollBar::sub-page:horizontal {{
    background: {BG_ELEV};
}}

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
    min-height: 36px;
    max-height: 36px;
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

/* ── 通用滚动条（复古 Windows 长方形风格） ── */
QScrollBar:vertical {{
    background: {BG_ELEV};
    width: 16px;
    margin: 0;
    border-left: 1px solid {BORDER};
}}
QScrollBar::handle:vertical {{
    background: {BORDER};
    border: 1px solid {FG_SOFT};
    border-radius: 0px;
    min-height: 32px;
}}
QScrollBar::handle:vertical:hover {{
    background: {FG_DIM};
    border-color: {FG};
}}
QScrollBar::handle:vertical:pressed {{
    background: {FG};
    border-color: {FG};
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    width: 0; height: 0;
}}
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
    background: {BG_ELEV};
}}
QScrollBar:horizontal {{
    background: {BG_ELEV};
    height: 16px;
    margin: 0;
    border-top: 1px solid {BORDER};
}}
QScrollBar::handle:horizontal {{
    background: {BORDER};
    border: 1px solid {FG_SOFT};
    border-radius: 0px;
    min-width: 32px;
}}
QScrollBar::handle:horizontal:hover {{
    background: {FG_DIM};
    border-color: {FG};
}}
QScrollBar::handle:horizontal:pressed {{
    background: {FG};
    border-color: {FG};
}}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
    width: 0; height: 0;
}}
QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {{
    background: {BG_ELEV};
}}

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
    "js": "FILE_TYPE_JS", "ts": "FILE_TYPE_TS", "jsx": "FILE_TYPE_JSX", "tsx": "FILE_TYPE_TSX",
    "py": "FILE_CODE_2", "rb": "FILE_CODE_2", "go": "FILE_CODE_2", "rs": "FILE_CODE_2",
    "java": "FILE_CODE_2", "c": "FILE_CODE_2", "cpp": "FILE_CODE_2", "h": "FILE_CODE_2", "cs": "FILE_CODE_2",
    "php": "FILE_CODE_2", "swift": "FILE_CODE_2", "kt": "FILE_CODE_2",
    "html": "FILE_TYPE_HTML", "htm": "FILE_TYPE_HTML", "css": "FILE_TYPE_CSS", "scss": "FILE_TYPE_CSS", "less": "FILE_TYPE_CSS",
    "json": "FILE_CODE_2", "jsonc": "FILE_CODE_2", "yaml": "FILE_CODE_2", "yml": "FILE_CODE_2",
    "toml": "FILE_CODE_2", "xml": "FILE_CODE_2", "csv": "FILE_TYPE_CSV", "sql": "DATABASE",
    "md": "FILE_TEXT", "mdx": "FILE_TEXT", "txt": "FILE_TYPE_TXT", "rst": "FILE_TEXT", "pdf": "FILE_TYPE_PDF",
    "png": "FILE_TYPE_PNG", "jpg": "FILE_TYPE_JPG", "jpeg": "FILE_TYPE_JPG", "gif": "FILE_TYPE_JPG",
    "svg": "FILE_TYPE_SVG", "ico": "FILE", "webp": "FILE_TYPE_PNG",
    "zip": "FILE_TYPE_ZIP", "tar": "FILE_TYPE_ZIP", "gz": "FILE_TYPE_ZIP", "rar": "FILE_TYPE_ZIP", "7z": "FILE_TYPE_ZIP",
    "sh": "FILE_CODE_2", "ps1": "FILE_CODE_2", "bat": "FILE_CODE_2", "cmd": "FILE_CODE_2",
    "env": "LOCK", "lock": "LOCK", "db": "DATABASE", "sqlite": "DATABASE",
    "mp4": "FILE_MUSIC", "mp3": "FILE_MUSIC", "wav": "FILE_MUSIC",
    "dockerfile": "BRAND_DOCKER",
}

_ICON_CACHE: dict[str, QIcon] = {}


def _tabler_to_qicon(icon_name: str, size: int = 16) -> QIcon:
    key = f"{icon_name}_{size}"
    if key in _ICON_CACHE:
        return _ICON_CACHE[key]
    if not HAS_TABLER:
        _ICON_CACHE[key] = QIcon()
        return QIcon()
    member = getattr(OutlineIcon, icon_name, None)
    if member is None:
        _ICON_CACHE[key] = QIcon()
        return QIcon()
    try:
        # White version (normal / unchecked)
        pil_w = TablerIcons.load(member, size=size, color="#e7e9ea")
        rgba_w = pil_w.convert("RGBA").tobytes()
        qimg_w = QImage(rgba_w, size, size, size * 4, QImage.Format.Format_RGBA8888).copy()
        pm_w = QPixmap.fromImage(qimg_w)

        # Black version (checked — white background needs dark icon)
        pil_b = TablerIcons.load(member, size=size, color="#000000")
        rgba_b = pil_b.convert("RGBA").tobytes()
        qimg_b = QImage(rgba_b, size, size, size * 4, QImage.Format.Format_RGBA8888).copy()
        pm_b = QPixmap.fromImage(qimg_b)

        icon = QIcon()
        icon.addPixmap(pm_w, QIcon.Mode.Normal, QIcon.State.Off)
        icon.addPixmap(pm_w, QIcon.Mode.Normal, QIcon.State.On)   # fallback
        icon.addPixmap(pm_b, QIcon.Mode.Selected, QIcon.State.On)
        icon.addPixmap(pm_b, QIcon.Mode.Active, QIcon.State.On)
        _ICON_CACHE[key] = icon
        return icon
    except Exception:
        _ICON_CACHE[key] = QIcon()
        return QIcon()


def _file_icon(name: str) -> QIcon:
    if name.startswith("."):
        return _tabler_to_qicon("SETTINGS", 16)
    ext = name.rsplit(".", 1)[-1].lower() if "." in name else ""
    icon_name = _FILE_ICONS.get(ext, "FILE")
    return _tabler_to_qicon(icon_name, 16)


def _sidebar_icon(icon_name: str, size: int = 20) -> tuple[QIcon, QIcon]:
    """Return (icon_white, icon_black) for unchecked / checked states."""
    if not HAS_TABLER:
        return QIcon(), QIcon()
    member = getattr(OutlineIcon, icon_name, None)
    if member is None:
        return QIcon(), QIcon()

    def _make(color: str) -> QIcon:
        pil = TablerIcons.load(member, size=size, color=color)
        rgba = pil.convert("RGBA").tobytes()
        qimg = QImage(rgba, size, size, size * 4, QImage.Format.Format_RGBA8888).copy()
        return QIcon(QPixmap.fromImage(qimg))

    try:
        return _make("#e7e9ea"), _make("#000000")
    except Exception:
        return QIcon(), QIcon()


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
