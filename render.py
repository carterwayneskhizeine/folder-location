"""文件预览的 HTML 渲染（Markdown / 代码高亮 / 图片 / 纯文本）。"""
import re
import html as _html
from pathlib import Path

from PySide6.QtCore import QUrl

from settings_panel import format_copy_path as _format_path

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


_MAX_FILE_BYTES = 2 * 1024 * 1024
_IMG_EXTS = {"png", "jpg", "jpeg", "gif", "webp", "bmp", "ico", "svg"}


# ── HTML 模板 ────────────────────────────────────────────────────────────────

_HTML_TPL = """<!DOCTYPE html>
<html><head><meta charset="utf-8"><meta name="color-scheme" content="dark">
<style>{style}</style></head><body>{body}</body></html>"""

_SCROLLBAR_CSS = """
::-webkit-scrollbar { width: 16px; height: 16px; }
::-webkit-scrollbar-track { background: #16181c; }
::-webkit-scrollbar-track-piece:start { background: #16181c; }
::-webkit-scrollbar-thumb {
    background: #2f3336;
    border: 1px solid #536471;
    border-radius: 0px;
    min-height: 32px;
}
::-webkit-scrollbar-thumb:hover {
    background: #71767b;
    border-color: #e7e9ea;
}
::-webkit-scrollbar-thumb:active {
    background: #e7e9ea;
    border-color: #e7e9ea;
}
::-webkit-scrollbar-corner { background: #16181c; }
"""

_BASE_CSS = (
    "* { box-sizing: border-box; } "
    "html,body { margin:0; padding:0; background:#000000; color:#e7e9ea; }"
    + _SCROLLBAR_CSS
)

_MD_CSS = _BASE_CSS + """
body {
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "PingFang SC", "Microsoft YaHei", Helvetica, Arial, sans-serif;
    font-size: 15px; line-height: 1.7;
    padding: 32px 40px; max-width: 920px;
}
h1,h2,h3,h4,h5,h6 { color:#ffffff; margin: 28px 0 10px; font-weight: 700; }
h1,h2 { border-bottom: 1px solid #2f3336; padding-bottom: 10px; }
a { color: #e7e9ea; text-decoration: underline; text-decoration-color: #71767b; }
a:hover { text-decoration-color: #ffffff; }
p { margin: 0 0 14px; }
code {
    background: #16181c; border: 1px solid #2f3336; border-radius: 6px;
    padding: 2px 6px; font-family: "JetBrains Mono","Consolas","Courier New",monospace;
    font-size: 85%; color: #e7e9ea;
}
pre {
    background: #16181c; border: 1px solid #2f3336; border-radius: 10px;
    padding: 16px; overflow-x: visible; line-height: 1.5; margin: 0 0 14px;
}
pre code { background:none; border:none; padding:0; color:#e7e9ea; font-size:100%; }
.codehilite { background: #16181c !important; border: 1px solid #2f3336; border-radius: 10px; overflow-x: visible; margin: 0; }
.codehilite pre { margin:0; padding:14px 16px; background:transparent; }
.code-wrapper { position: relative; margin-bottom: 14px; }
.code-copy-btn {
    position: absolute; top: 10px; right: 10px;
    background: #000000; border: 1px solid #2f3336;
    color: #e7e9ea; font-size: 11px; padding: 4px 10px;
    border-radius: 999px; cursor: pointer; opacity: 0;
    transition: opacity 0.15s; z-index: 10;
}
.code-copy-btn:hover { background: #ffffff; color: #000000; border-color: #ffffff; }
.code-wrapper:hover .code-copy-btn { opacity: 1; }
blockquote { border-left:3px solid #2f3336; margin:0 0 14px; padding:4px 16px; color:#71767b; }
table { border-collapse:collapse; width:100%; margin-bottom:14px; }
th,td { border:1px solid #2f3336; padding:8px 14px; text-align:left; }
th { background:#16181c; color:#ffffff; font-weight:600; }
tr:nth-child(even) { background:#0a0a0a; }
img { max-width:100%; border-radius:8px; }
hr { border:none; border-top:1px solid #2f3336; margin:24px 0; }
ul,ol { padding-left:24px; margin-bottom:14px; }
li { margin-bottom:4px; }
"""

_CODE_CSS = _BASE_CSS + """
body { padding: 0; font-family: "JetBrains Mono","Consolas","Courier New",monospace; font-size: 13px; }
.code-wrapper { position: relative; margin-bottom: 14px; }
.highlight { background: #000000 !important; margin: 0; overflow-x: visible; }
.highlight pre { margin:0; padding:18px 20px; line-height:1.55; overflow-x:visible; }
table.highlighttable { width:auto; border-collapse:collapse; }
td.linenos {
    background: #0a0a0a; width: 52px; vertical-align:top;
    border-right: 1px solid #2f3336; padding: 0;
}
td.linenos .linenodiv pre {
    background: none; margin:0; padding: 18px 10px 18px 0;
    color: #536471; text-align:right; line-height:1.55;
    font-size:13px; user-select:none;
}
td.code { padding:0; vertical-align:top; }
td.code .highlight pre { padding: 18px 20px; }
.code-copy-btn {
    position: absolute; top: 10px; right: 10px;
    background: #16181c; border: 1px solid #2f3336;
    color: #e7e9ea; font-size: 11px; padding: 4px 10px;
    border-radius: 999px; cursor: pointer; opacity: 0;
    transition: opacity 0.15s; z-index: 10;
}
.code-copy-btn:hover { background: #ffffff; color: #000000; border-color: #ffffff; }
.code-wrapper:hover .code-copy-btn { opacity: 1; }
"""

_PLAIN_CSS = _BASE_CSS + """
pre {
    margin:0; padding:18px 22px;
    font-family:"JetBrains Mono","Consolas","Courier New",monospace; font-size:13px;
    line-height:1.6; white-space:pre-wrap; word-break:break-all; color:#e7e9ea;
}
"""

_IMG_CSS = _BASE_CSS + """
body { display:flex; align-items:center; justify-content:center;
       min-height:100vh; padding:20px; }
img { max-width:100%; max-height:90vh; border-radius:10px;
      box-shadow:0 4px 24px #000000aa; }
"""

_EMPTY_HTML = _HTML_TPL.format(
    style=_BASE_CSS,
    body='<div style="display:flex;align-items:center;justify-content:center;'
         'height:100vh;color:#536471;font-size:14px;font-family:sans-serif;">'
         '点击左侧文件预览内容</div>',
)


def _build(style: str, body: str) -> str:
    return _HTML_TPL.format(style=style, body=body)


def _wrap_code_blocks(html: str, wrap_class: str = "code-wrapper") -> str:
    placeholder_prefix = "__CODE_WRAP_PLACEHOLDER_"
    placeholder_suffix = "__"
    wraps: list[str] = []

    def _store(m):
        wraps.append(f'<div class="{wrap_class}">{m.group(0)}<button class="code-copy-btn">Copy</button></div>')
        return placeholder_prefix + str(len(wraps) - 1) + placeholder_suffix

    html = re.sub(r'<table class="highlighttable">.+?</table>', _store, html, flags=re.DOTALL)
    html = re.sub(r'<div class="codehilite">.+?</div>', _store, html, flags=re.DOTALL)
    html = re.sub(r'<div class="highlight">.+?</div>', _store, html, flags=re.DOTALL)

    for i in range(len(wraps) - 1, -1, -1):
        html = html.replace(placeholder_prefix + str(i) + placeholder_suffix, wraps[i])
    return html


def _pygments_css(cls: str = ".highlight") -> str:
    return _HtmlFmt(style="github-dark").get_style_defs(cls) if HAS_PYGMENTS else ""


# ── 选区辅助 ──────────────────────────────────────────────────────────────────

def _normalize_selected_text(text: str) -> str:
    return text.replace(" ", "\n").replace(" ", "\n")


def _format_copy_path(path: Path, start_line, end_line, text: str) -> str:
    path_text = _format_path(str(path))
    if start_line is not None:
        if end_line is None or end_line == start_line:
            path_text += f":{start_line}"
        else:
            path_text += f":{start_line}-{end_line}"
    return f"{path_text}\n```\n{text}\n```"


def _line_range_for_selection(path: Path, selected_text: str):
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


# ── 渲染入口 ──────────────────────────────────────────────────────────────────

def render_file(path: Path) -> tuple[str, bool]:
    ext = path.suffix.lower().lstrip(".")
    try:
        size = path.stat().st_size
    except OSError as e:
        return _build(_PLAIN_CSS, f"<pre>读取失败：{_html.escape(str(e))}</pre>"), False

    if ext in _IMG_EXTS:
        url = QUrl.fromLocalFile(str(path)).toString()
        img_body = f'<img src="{url}" alt="{_html.escape(path.name)}">'
        return _build(_IMG_CSS, img_body), False

    if size > _MAX_FILE_BYTES:
        return _build(_PLAIN_CSS, "<pre>文件太大，无法预览（超过 2 MB）</pre>"), False

    try:
        text = path.read_text(encoding="utf-8", errors="strict")
    except UnicodeDecodeError:
        return _build(_PLAIN_CSS, "<pre>二进制文件，无法预览</pre>"), False
    except Exception as e:
        return _build(_PLAIN_CSS, f"<pre>读取失败：{_html.escape(str(e))}</pre>"), False

    _FAST_PREVIEW_LIMIT = 200 * 1024
    if size > _FAST_PREVIEW_LIMIT:
        escaped = _html.escape(text)
        if len(text) > 500_000:
            escaped = escaped[:500_000] + "\n\n... (文件过大，已截断显示) ..."
        return _build(_PLAIN_CSS, f"<pre>{escaped}</pre>"), False

    if ext in ("md", "mdx", "markdown") and HAS_MARKDOWN:
        exts = ["tables", "fenced_code", "toc"]
        ext_cfg: dict = {}
        extra_css = ""
        if HAS_PYGMENTS:
            exts.append("codehilite")
            ext_cfg["codehilite"] = {"css_class": "codehilite", "guess_lang": False}
            extra_css = _pygments_css(".codehilite")
        body = _md.markdown(text, extensions=exts, extension_configs=ext_cfg)
        body = _wrap_code_blocks(body, "code-wrapper")
        return _build(_MD_CSS + extra_css, body), False

    if HAS_PYGMENTS:
        try:
            lexer = _lexer_for(path.name)
        except _LexerNotFound:
            lexer = None
        if lexer is not None:
            fmt = _HtmlFmt(style="github-dark", linenos="table", wrapcode=True)
            pyg_css = fmt.get_style_defs(".highlight")
            highlighted = _hl(text, lexer, fmt)
            highlighted = (
                f'<div class="code-wrapper">{highlighted}'
                '<button class="code-copy-btn">Copy</button></div>'
            )
            return _build(_CODE_CSS + pyg_css, highlighted), False

    return _build(_PLAIN_CSS, f"<pre>{_html.escape(text)}</pre>"), False
