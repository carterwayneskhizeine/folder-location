"""文件内容预览面板，多标签 + 内嵌浏览器 + Ctrl+F 搜索高亮。"""
import json
from pathlib import Path

from PySide6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QLineEdit, QTabBar,
    QPlainTextEdit, QMenu, QStackedWidget, QToolButton, QScrollBar,
)
from PySide6.QtCore import (
    Qt, QTimer, QEvent, Signal, QUrl, QSize, QFileSystemWatcher,
    QObject, Slot,
)
from PySide6.QtGui import QColor, QShortcut, QKeySequence

from browser_panel import BrowserPanel
from theme import HiddenTabScrollButtonStyle
from render import render_file, _EMPTY_HTML, _normalize_selected_text, _format_copy_path, _line_range_for_selection

try:
    from PySide6.QtWebEngineWidgets import QWebEngineView
    HAS_WEBENGINE = True
except ImportError:
    HAS_WEBENGINE = False

try:
    from PySide6.QtWebChannel import QWebChannel
    HAS_WEBCHANNEL = True
except ImportError:
    HAS_WEBCHANNEL = False


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
    this.marks.forEach(m => { m.style.cssText = 'background:#ffffff40;color:inherit;border-radius:2px;padding:0 1px;'; });
    this.idx = i;
    const m = this.marks[i];
    m.style.cssText = 'background:#ffffff;color:#000000;border-radius:2px;padding:0 1px;outline:2px solid #ffffff;';
    m.scrollIntoView({ behavior: 'smooth', block: 'center' });
    return this._result(this.idx, this.marks.length);
  },
  next() { return this.marks.length ? this._goto((this.idx + 1) % this.marks.length) : this._result(-1, 0); },
  prev() { return this.marks.length ? this._goto((this.idx - 1 + this.marks.length) % this.marks.length) : this._result(-1, 0); },
};
(function() {
  function getCodeText(wrapper) {
    const table = wrapper.querySelector('table.highlighttable');
    if (table) {
      const codeCell = table.querySelector('td.code .highlight pre, td.code pre');
      if (codeCell) return codeCell.textContent;
    }
    const highlight = wrapper.querySelector('.highlight pre, .highlight');
    if (highlight) return highlight.textContent;
    const codehilite = wrapper.querySelector('.codehilite pre, .codehilite');
    if (codehilite) return codehilite.textContent;
    const pre = wrapper.querySelector('pre');
    return pre ? pre.textContent : '';
  }
  function copyText(text) {
    function fallbackCopy() {
      if (navigator.clipboard && window.isSecureContext) {
        return navigator.clipboard.writeText(text);
      }
      return legacyCopy(text);
    }
    return getClipboardBridge().then(bridge => {
      if (!bridge || !bridge.copyText) return fallbackCopy();
      return new Promise((resolve, reject) => {
        bridge.copyText(text, ok => ok ? resolve() : fallbackCopy().then(resolve, reject));
      });
    });
  }
  function getClipboardBridge() {
    if (window._qtClipboardBridge) return Promise.resolve(window._qtClipboardBridge);
    if (!window.qt || !qt.webChannelTransport) return Promise.resolve(null);
    if (window._qtClipboardBridgePromise) return window._qtClipboardBridgePromise;
    window._qtClipboardBridgePromise = new Promise(resolve => {
      const init = () => {
        new QWebChannel(qt.webChannelTransport, channel => {
          window._qtClipboardBridge = channel.objects.clipboardBridge || null;
          resolve(window._qtClipboardBridge);
        });
      };
      if (window.QWebChannel) {
        init();
        return;
      }
      const script = document.createElement('script');
      script.src = 'qrc:///qtwebchannel/qwebchannel.js';
      script.onload = init;
      script.onerror = () => resolve(null);
      document.head.appendChild(script);
    });
    return window._qtClipboardBridgePromise;
  }
  function legacyCopy(text) {
    const ta = document.createElement('textarea');
    ta.value = text;
    ta.style.cssText = 'position:fixed;left:-9999px;top:-9999px;opacity:0;';
    document.body.appendChild(ta);
    ta.select();
    const ok = document.execCommand('copy');
    document.body.removeChild(ta);
    return ok ? Promise.resolve() : Promise.reject(new Error('copy failed'));
  }
  function setupCopyButtons() {
    document.querySelectorAll('.code-copy-btn').forEach(btn => {
      if (btn.dataset.setup) return;
      btn.dataset.setup = '1';
      btn.addEventListener('click', function(e) {
        e.preventDefault();
        e.stopPropagation();
        const wrapper = this.parentElement;
        const text = getCodeText(wrapper);
        if (text) {
          const origText = this.textContent;
          copyText(text).then(() => {
            this.textContent = 'OK';
            setTimeout(() => { this.textContent = origText; }, 900);
          }).catch(() => {});
        }
      });
    });
  }
  setupCopyButtons();
  const observer = new MutationObserver(() => setupCopyButtons());
  observer.observe(document.body, { childList: true, subtree: true });
})();
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

  return { text, startLine, endLine: startLine + selectedLines - 1 };
})()
"""


class ClipboardBridge(QObject):
    path_copied = Signal(str)

    @Slot(str, result=bool)
    def copyText(self, text: str) -> bool:
        if not text:
            return False
        QApplication.clipboard().setText(text)
        self.path_copied.emit(text)
        return True


class PreviewWebView(QWebEngineView if HAS_WEBENGINE else QWidget):
    path_copied = Signal(str)

    def __init__(self) -> None:
        super().__init__()
        self.current_path: Path | None = None
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._show_context_menu)

        if HAS_WEBENGINE:
            self.page().setBackgroundColor(QColor("#000000"))
            if HAS_WEBCHANNEL:
                self._clipboard_bridge = ClipboardBridge(self)
                self._clipboard_bridge.path_copied.connect(self.path_copied)
                self._web_channel = QWebChannel(self)
                self._web_channel.registerObject("clipboardBridge", self._clipboard_bridge)
                self.page().setWebChannel(self._web_channel)
            self.setHtml(_EMPTY_HTML)

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


class PreviewTabBar(QTabBar):
    scrolled = Signal()

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
        QTimer.singleShot(0, self.scrolled.emit)
        event.accept()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        QTimer.singleShot(0, self.scrolled.emit)

    def tabLayoutChange(self) -> None:
        super().tabLayoutChange()
        QTimer.singleShot(0, self.scrolled.emit)

    def _scroll_button(self, forward: bool) -> QToolButton | None:
        buttons = [b for b in self.findChildren(QToolButton) if b.isVisible()]
        if not buttons:
            return None
        buttons.sort(key=lambda b: b.geometry().x())
        return buttons[-1] if forward else buttons[0]

    def tabSizeHint(self, index: int) -> QSize:
        return super().tabSizeHint(index)

    def minimumSizeHint(self) -> QSize:
        size = super().minimumSizeHint()
        size.setWidth(0)
        return size


class PreviewPane(QWidget):
    path_copied = Signal(str)
    file_tab_switched = Signal(Path)

    def __init__(self) -> None:
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._tab_bar = PreviewTabBar()
        self._tab_bar_style = HiddenTabScrollButtonStyle()
        self._tab_bar.setStyle(self._tab_bar_style)
        self._tab_bar.setMovable(True)
        self._tab_bar.setDocumentMode(True)
        self._tab_bar.setExpanding(False)
        self._tab_bar.setUsesScrollButtons(True)
        self._tab_bar.setElideMode(Qt.TextElideMode.ElideNone)
        self._tab_bar.setMinimumWidth(0)
        self._tab_bar.currentChanged.connect(self._on_tab_changed)
        self._tab_bar.tabMoved.connect(self._on_tab_moved)

        tab_header = QWidget()
        tab_header.setObjectName("previewHeader")
        thl = QHBoxLayout(tab_header)
        thl.setContentsMargins(0, 0, 0, 0)
        thl.setSpacing(0)
        thl.addWidget(self._tab_bar, 1)

        self._add_browser_btn = QPushButton("+")
        self._add_browser_btn.setObjectName("addFolderBtn")
        self._add_browser_btn.setFlat(True)
        self._add_browser_btn.setToolTip("打开浏览器")
        self._add_browser_btn.clicked.connect(self.open_browser)
        thl.addWidget(self._add_browser_btn)
        layout.addWidget(tab_header)

        self._tab_scrollbar = QScrollBar(Qt.Orientation.Horizontal)
        self._tab_scrollbar.setObjectName("tabScrollBar")
        self._tab_scrollbar.setSingleStep(30)
        self._tab_scrollbar.setFixedHeight(16)
        self._tab_scrollbar.hide()
        self._tab_scrollbar.valueChanged.connect(self._on_tab_scrollbar_moved)
        self._tab_bar.scrolled.connect(self._update_tab_scrollbar)
        layout.addWidget(self._tab_scrollbar)

        self._stack = QStackedWidget()
        layout.addWidget(self._stack, 1)

        self._tabs: dict[Path, dict] = {}
        self._ordered_paths: list[Path] = []
        self._browser_tabs: list[BrowserPanel] = []
        self._current_path: Path | None = None
        self._js_ready = False
        self._block_tab_signal = False
        self._pending_preview_refresh: set[Path] = set()

        self._watcher = QFileSystemWatcher(self)
        self._watcher.fileChanged.connect(self._on_preview_file_changed)
        self._watcher.directoryChanged.connect(self._on_preview_dir_changed)

        self._refresh_timer = QTimer(self)
        self._refresh_timer.setSingleShot(True)
        self._refresh_timer.setInterval(120)
        self._refresh_timer.timeout.connect(self._flush_preview_refreshes)

        sc = QShortcut(QKeySequence("Ctrl+W"), self)
        sc.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        sc.activated.connect(self.close_current_tab)

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

    def _tab_scroll_offset(self) -> int:
        if self._tab_bar.count() == 0:
            return 0
        return max(0, -self._tab_bar.tabRect(0).x())

    def _update_tab_scrollbar(self) -> None:
        total_w = sum(self._tab_bar.tabRect(i).width() for i in range(self._tab_bar.count()))
        visible_w = self._tab_bar.width()
        max_scroll = max(0, total_w - visible_w)

        self._tab_scrollbar.blockSignals(True)
        self._tab_scrollbar.setRange(0, max_scroll)
        self._tab_scrollbar.setPageStep(visible_w)
        self._tab_scrollbar.setValue(self._tab_scroll_offset())
        self._tab_scrollbar.blockSignals(False)
        self._tab_scrollbar.setVisible(max_scroll > 0)

    def _on_tab_scrollbar_moved(self, value: int) -> None:
        for _ in range(100):
            current = self._tab_scroll_offset()
            delta = value - current
            if abs(delta) <= 3:
                break
            forward = delta > 0
            buttons = sorted(
                [b for b in self._tab_bar.findChildren(QToolButton)],
                key=lambda b: b.geometry().x(),
            )
            btn = (buttons[-1] if forward else buttons[0]) if buttons else None
            if btn is None or not btn.isEnabled():
                break
            prev = current
            btn.click()
            if self._tab_scroll_offset() == prev:
                break

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

    def open_browser(self, url: str | None = None) -> BrowserPanel:
        browser = BrowserPanel(url)
        self._add_browser_tab(browser, url or "浏览器", focus_address=True)
        return browser

    def _add_browser_tab(self, browser: BrowserPanel, tooltip: str = "浏览器",
                         *, focus_address: bool = False) -> None:
        if browser in self._browser_tabs:
            return
        self._browser_tabs.append(browser)
        idx = self._tab_bar.addTab("浏览器")
        self._tab_bar.setTabData(idx, browser)
        self._tab_bar.setTabToolTip(idx, tooltip)
        self._attach_browser_close_btn(idx, browser)
        self._stack.addWidget(browser)
        self._tab_bar.setCurrentIndex(idx)

        browser.title_changed.connect(lambda title, b=browser: self._update_browser_tab_title(b, title))
        browser.url_changed.connect(lambda current_url, b=browser: self._update_browser_tab_url(b, current_url))
        browser.popup_created.connect(self._on_browser_popup_created)
        if focus_address:
            browser.focus_address_bar()

    def _on_browser_popup_created(self, browser: BrowserPanel) -> None:
        self._add_browser_tab(browser, "浏览器弹窗")

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
            self._sync_preview_watches()
        finally:
            self._block_tab_signal = False

    def _tab_index_for(self, path: Path) -> int | None:
        for i in range(self._tab_bar.count()):
            if self._tab_bar.tabData(i) == path:
                return i
        return None

    def _tab_index_for_browser(self, browser: BrowserPanel) -> int | None:
        for i in range(self._tab_bar.count()):
            if self._tab_bar.tabData(i) is browser:
                return i
        return None

    def _attach_close_btn(self, idx: int, path: Path) -> None:
        btn = QPushButton("×")
        btn.setObjectName("tabCloseBtn")
        btn.setFlat(True)
        btn.setFixedSize(18, 18)
        btn.setToolTip("关闭")
        btn.clicked.connect(lambda: self._close_tab(path))
        self._tab_bar.setTabButton(idx, QTabBar.ButtonPosition.RightSide, btn)

    def _attach_browser_close_btn(self, idx: int, browser: BrowserPanel) -> None:
        btn = QPushButton("×")
        btn.setObjectName("tabCloseBtn")
        btn.setFlat(True)
        btn.setFixedSize(18, 18)
        btn.setToolTip("关闭")
        btn.clicked.connect(lambda: self._close_browser_tab(browser))
        self._tab_bar.setTabButton(idx, QTabBar.ButtonPosition.RightSide, btn)

    def close_current_tab(self) -> None:
        idx = self._tab_bar.currentIndex()
        if idx < 0:
            return
        data = self._tab_bar.tabData(idx)
        if isinstance(data, Path):
            self._close_tab(data)
        elif isinstance(data, BrowserPanel):
            self._close_browser_tab(data)

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
        self._sync_preview_watches()

        if self._current_path == path:
            self._current_path = None
            if self._ordered_paths:
                new_path = self._ordered_paths[-1]
                new_idx = self._tab_index_for(new_path)
                if new_idx is not None:
                    self._tab_bar.setCurrentIndex(new_idx)
            else:
                self._js_ready = False

    def _close_browser_tab(self, browser: BrowserPanel) -> None:
        if browser not in self._browser_tabs:
            return
        was_current = self._current_view() is browser
        self._browser_tabs.remove(browser)

        idx = self._tab_index_for_browser(browser)
        if idx is not None:
            self._tab_bar.removeTab(idx)
        self._stack.removeWidget(browser)
        browser.deleteLater()

        if was_current and self._tab_bar.currentIndex() < 0:
            self._current_path = None
            self._js_ready = False

    def _update_browser_tab_title(self, browser: BrowserPanel, title: str) -> None:
        idx = self._tab_index_for_browser(browser)
        if idx is None:
            return
        clean = (title or "浏览器").strip() or "浏览器"
        if len(clean) > 24:
            clean = clean[:21] + "..."
        self._tab_bar.setTabText(idx, clean)

    def _update_browser_tab_url(self, browser: BrowserPanel, url: str) -> None:
        idx = self._tab_index_for_browser(browser)
        if idx is None:
            return
        self._tab_bar.setTabToolTip(idx, url or "浏览器")

    def _on_tab_changed(self, idx: int) -> None:
        if idx < 0:
            return
        data = self._tab_bar.tabData(idx)
        if isinstance(data, BrowserPanel):
            self._current_path = None
            self._js_ready = False
            self._stack.setCurrentWidget(data)
            if self._search_bar.isVisible():
                self.close_search()
            return

        path: Path | None = data
        if path is None or path not in self._tabs:
            return
        self._current_path = path
        self._js_ready = False
        info = self._tabs[path]
        self._stack.setCurrentWidget(info["view"])

        if HAS_WEBENGINE and isinstance(info["view"], PreviewWebView):
            if not info["view"].current_path:
                info["view"].setHtml(_EMPTY_HTML)
            else:
                info["view"].page().runJavaScript(_SEARCH_JS)
                self._js_ready = True

        if not getattr(self, "_block_tab_signal", False):
            self.file_tab_switched.emit(path)
        QTimer.singleShot(0, self._update_tab_scrollbar)

    def _on_tab_moved(self, from_idx: int, to_idx: int) -> None:
        QTimer.singleShot(0, self._update_tab_scrollbar)

    def _render_in_view(self, view, path: Path, *, activate: bool = True) -> None:
        if activate:
            self._current_path = path
            self._js_ready = False
        if HAS_WEBENGINE and isinstance(view, PreviewWebView):
            view.current_path = path
            view.page().setBackgroundColor(QColor("#000000"))
        elif isinstance(view, PreviewPlainTextEdit):
            view.current_path = path

        if activate and self._search_bar.isVisible():
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

        def on_loaded(ok):
            if ok:
                view.page().runJavaScript("window.scrollTo(0,0);")
                if activate:
                    QTimer.singleShot(100, self._inject_search_js)
                else:
                    QTimer.singleShot(100, lambda: view.page().runJavaScript(_SEARCH_JS))

        view.loadFinished.connect(on_loaded, Qt.ConnectionType.SingleShotConnection)

    def _sync_preview_watches(self) -> None:
        files = self._watcher.files()
        dirs = self._watcher.directories()
        if files:
            self._watcher.removePaths(files)
        if dirs:
            self._watcher.removePaths(dirs)

        file_paths: list[str] = []
        dir_paths: list[str] = []
        for path in self._ordered_paths:
            parent = path.parent
            if parent.is_dir():
                dir_paths.append(str(parent))
            if path.is_file():
                file_paths.append(str(path))

        if dir_paths:
            self._watcher.addPaths(sorted(set(dir_paths)))
        if file_paths:
            self._watcher.addPaths(sorted(set(file_paths)))

    def _queue_preview_refresh(self, path: Path) -> None:
        if path in self._tabs:
            self._pending_preview_refresh.add(path)
            self._refresh_timer.start()

    def _on_preview_file_changed(self, path: str) -> None:
        self._queue_preview_refresh(Path(path))

    def _on_preview_dir_changed(self, path: str) -> None:
        changed_dir = Path(path)
        for opened in self._ordered_paths:
            if opened.parent == changed_dir:
                self._queue_preview_refresh(opened)

    def _flush_preview_refreshes(self) -> None:
        paths = list(self._pending_preview_refresh)
        self._pending_preview_refresh.clear()

        current = self._current_path
        for path in paths:
            info = self._tabs.get(path)
            if not info:
                continue
            is_current = path == current
            self._render_in_view(info["view"], path, activate=is_current)
            idx = self._tab_index_for(path)
            if idx is not None:
                self._tab_bar.setTabText(idx, path.name)
                self._tab_bar.setTabToolTip(idx, str(path).replace("\\", "/"))

        self._sync_preview_watches()

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

    def _as_non_bool_int(self, value):
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

    def open_paths(self) -> list[str]:
        return [str(p) for p in self._ordered_paths]

    def browser_urls(self) -> list[str]:
        return [browser.current_url() for browser in self._browser_tabs if browser.current_url()]

    def restore_tabs(self, paths: list[str]) -> None:
        self._block_tab_signal = True
        try:
            for p in paths:
                path = Path(p)
                if path.is_file():
                    view = self._create_view()
                    self._tabs[path] = {"view": view}
                    self._ordered_paths.append(path)
                    idx = self._tab_bar.addTab(path.name)
                    self._tab_bar.setTabData(idx, path)
                    self._tab_bar.setTabToolTip(idx, str(path).replace("\\", "/"))
                    self._attach_close_btn(idx, path)
                    self._stack.addWidget(view)
                    self._render_in_view(view, path)
            self._sync_preview_watches()
            if self._ordered_paths:
                self._tab_bar.setCurrentIndex(0)
        finally:
            self._block_tab_signal = False

    def restore_browser_tabs(self, urls: list[str]) -> None:
        for url in urls or []:
            if isinstance(url, str) and url.strip():
                self.open_browser(url)
