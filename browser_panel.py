"""Embedded browser panel used by the right-side preview tabs."""

from __future__ import annotations

import json
import os
from pathlib import Path
from urllib.parse import quote_plus

from PySide6.QtCore import QSettings, QStandardPaths, Qt, QUrl, Signal
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMenu,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

try:
    from PySide6.QtWebEngineCore import (
        QWebEnginePage,
        QWebEngineProfile,
        QWebEngineSettings,
    )
    from PySide6.QtWebEngineWidgets import QWebEngineView
    HAS_BROWSER_WEBENGINE = True
except ImportError:
    QWebEnginePage = None
    QWebEngineProfile = None
    QWebEngineSettings = None
    QWebEngineView = None
    HAS_BROWSER_WEBENGINE = False


_HOME_URL = "https://www.google.com"
_SETTINGS_ORG = "FolderTree"
_SETTINGS_APP = "FolderTree"
_FAVORITES_KEY = "browser/favorites"
_BROWSER_PROFILE: QWebEngineProfile | None = None


def _normalize_url(text: str) -> QUrl:
    value = text.strip()
    if not value:
        return QUrl(_HOME_URL)

    if "://" not in value:
        if " " in value or "." not in value:
            return QUrl(f"https://www.google.com/search?q={quote_plus(value)}")
        value = "https://" + value

    return QUrl.fromUserInput(value)


def _browser_data_dir() -> Path:
    local_app_data = os.environ.get("LOCALAPPDATA")
    if local_app_data:
        return Path(local_app_data) / "Folder Location" / "Browser"

    base = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppLocalDataLocation)
    if base:
        return Path(base) / "browser"

    return Path.home() / ".folder-location" / "browser"


def _persistent_browser_profile() -> QWebEngineProfile:
    global _BROWSER_PROFILE
    if _BROWSER_PROFILE is not None:
        return _BROWSER_PROFILE

    profile_root = _browser_data_dir()
    storage_path = profile_root / "storage"
    cache_path = profile_root / "cache"
    storage_path.mkdir(parents=True, exist_ok=True)
    cache_path.mkdir(parents=True, exist_ok=True)

    profile = QWebEngineProfile("FolderLocationBrowser")
    profile.setPersistentStoragePath(str(storage_path))
    profile.setCachePath(str(cache_path))
    profile.setPersistentCookiesPolicy(
        QWebEngineProfile.PersistentCookiesPolicy.ForcePersistentCookies
    )
    profile.setHttpCacheType(QWebEngineProfile.HttpCacheType.DiskHttpCache)
    profile.setHttpCacheMaximumSize(256 * 1024 * 1024)

    _BROWSER_PROFILE = profile
    return profile


if HAS_BROWSER_WEBENGINE:
    class BrowserWebView(QWebEngineView):
        def __init__(self, browser_panel: "BrowserPanel") -> None:
            super().__init__()
            self._browser_panel = browser_panel

        def createWindow(self, window_type):
            popup = self._browser_panel.create_popup_browser()
            if popup._view is not None:
                return popup._view
            return super().createWindow(window_type)
else:
    BrowserWebView = None


class BrowserPanel(QWidget):
    """Small Chrome-like browser: navigation, address bar, refresh, favorites."""

    title_changed = Signal(str)
    url_changed = Signal(str)
    popup_created = Signal(object)

    def __init__(self, initial_url: str | None = None, *, autoload: bool = True) -> None:
        super().__init__()
        self._favorites: list[dict[str, str]] = self._load_favorites()
        self._loading = False
        self._last_url = ""

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        toolbar = QWidget()
        toolbar.setObjectName("browserToolbar")
        toolbar_layout = QHBoxLayout(toolbar)
        toolbar_layout.setContentsMargins(8, 6, 8, 6)
        toolbar_layout.setSpacing(6)
        layout.addWidget(toolbar)

        self._back_btn = self._tool_button("‹", "返回")
        self._forward_btn = self._tool_button("›", "前进")
        self._reload_btn = self._tool_button("⟳", "刷新")
        self._home_btn = self._tool_button("⌂", "主页")

        toolbar_layout.addWidget(self._back_btn)
        toolbar_layout.addWidget(self._forward_btn)
        toolbar_layout.addWidget(self._reload_btn)
        toolbar_layout.addWidget(self._home_btn)

        self._url_input = QLineEdit()
        self._url_input.setObjectName("browserUrlInput")
        self._url_input.setClearButtonEnabled(True)
        self._url_input.setPlaceholderText("输入网址或搜索内容")
        self._url_input.returnPressed.connect(self._load_from_input)
        toolbar_layout.addWidget(self._url_input, 1)
        QShortcut(QKeySequence("Ctrl+L"), self).activated.connect(self.focus_address_bar)

        self._favorite_btn = self._tool_button("☆", "收藏当前网页")
        self._favorites_btn = self._tool_button("收藏夹", "打开收藏夹")
        self._favorites_btn.setMinimumWidth(64)
        toolbar_layout.addWidget(self._favorite_btn)
        toolbar_layout.addWidget(self._favorites_btn)

        if not HAS_BROWSER_WEBENGINE:
            fallback = QLabel("当前环境缺少 Qt WebEngine，无法打开内置浏览器。")
            fallback.setObjectName("browserFallback")
            fallback.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(fallback, 1)
            self._view = None
            self._last_url = initial_url or _HOME_URL
            self._url_input.setText(self._last_url)
            self._set_nav_enabled(False)
            return

        self._view = BrowserWebView(self)
        self._view.setObjectName("browserView")
        self._view.setPage(QWebEnginePage(_persistent_browser_profile(), self._view))
        self._view.settings().setAttribute(
            QWebEngineSettings.WebAttribute.JavascriptCanOpenWindows,
            True,
        )
        layout.addWidget(self._view, 1)

        self._back_btn.clicked.connect(self._view.back)
        self._forward_btn.clicked.connect(self._view.forward)
        self._reload_btn.clicked.connect(self._reload_or_stop)
        self._home_btn.clicked.connect(lambda: self.load_url(_HOME_URL))
        self._favorite_btn.clicked.connect(self._toggle_favorite)
        self._favorites_btn.clicked.connect(self._show_favorites_menu)

        self._view.urlChanged.connect(self._on_url_changed)
        self._view.titleChanged.connect(self._on_title_changed)
        self._view.loadStarted.connect(self._on_load_started)
        self._view.loadFinished.connect(self._on_load_finished)
        self._view.loadProgress.connect(self._on_load_progress)

        if autoload:
            self.load_url(initial_url or _HOME_URL)

    def current_url(self) -> str:
        if self._view is None:
            return self._last_url
        return self._view.url().toString() or self._last_url

    def load_url(self, text: str) -> None:
        url = _normalize_url(text)
        self._last_url = url.toString()
        self._url_input.setText(self._last_url)
        if self._view is None:
            return
        self._view.load(url)

    def focus_address_bar(self) -> None:
        self._url_input.setFocus()
        self._url_input.selectAll()

    def create_popup_browser(self) -> "BrowserPanel":
        popup = BrowserPanel(autoload=False)
        self.popup_created.emit(popup)
        return popup

    def _tool_button(self, text: str, tooltip: str) -> QPushButton:
        button = QPushButton(text)
        button.setObjectName("browserNavBtn")
        button.setToolTip(tooltip)
        button.setFixedHeight(28)
        return button

    def _load_from_input(self) -> None:
        self.load_url(self._url_input.text())

    def _reload_or_stop(self) -> None:
        if self._view is None:
            return
        if self._loading:
            self._view.stop()
        else:
            self._view.reload()

    def _on_load_started(self) -> None:
        self._loading = True
        self._reload_btn.setText("×")
        self._reload_btn.setToolTip("停止加载")

    def _on_load_progress(self, progress: int) -> None:
        if 0 <= progress < 100:
            self._reload_btn.setToolTip(f"正在加载 {progress}%")

    def _on_load_finished(self, ok: bool) -> None:
        self._loading = False
        self._reload_btn.setText("⟳")
        self._reload_btn.setToolTip("刷新")
        self._refresh_nav_state()
        if not ok:
            self.title_changed.emit("加载失败")

    def _on_url_changed(self, url: QUrl) -> None:
        value = url.toString()
        self._last_url = value
        self._url_input.setText(value)
        self.url_changed.emit(value)
        self._refresh_nav_state()
        self._refresh_favorite_state()

    def _on_title_changed(self, title: str) -> None:
        self.title_changed.emit(title or "浏览器")

    def _refresh_nav_state(self) -> None:
        if self._view is None:
            self._set_nav_enabled(False)
            return
        history = self._view.history()
        self._back_btn.setEnabled(history.canGoBack())
        self._forward_btn.setEnabled(history.canGoForward())
        self._reload_btn.setEnabled(True)
        self._home_btn.setEnabled(True)
        self._favorite_btn.setEnabled(True)
        self._favorites_btn.setEnabled(True)

    def _set_nav_enabled(self, enabled: bool) -> None:
        for button in (
            self._back_btn,
            self._forward_btn,
            self._reload_btn,
            self._home_btn,
            self._favorite_btn,
            self._favorites_btn,
        ):
            button.setEnabled(enabled)

    def _current_favorite_index(self) -> int | None:
        current = self.current_url()
        if not current:
            return None
        for idx, item in enumerate(self._favorites):
            if item.get("url") == current:
                return idx
        return None

    def _refresh_favorite_state(self) -> None:
        if self._current_favorite_index() is None:
            self._favorite_btn.setText("☆")
            self._favorite_btn.setToolTip("收藏当前网页")
        else:
            self._favorite_btn.setText("★")
            self._favorite_btn.setToolTip("取消收藏当前网页")

    def _toggle_favorite(self) -> None:
        if self._view is None:
            return
        idx = self._current_favorite_index()
        if idx is None:
            title = self._view.title() or self.current_url()
            self._favorites.append({"title": title, "url": self.current_url()})
        else:
            self._favorites.pop(idx)
        self._save_favorites()
        self._refresh_favorite_state()

    def _show_favorites_menu(self) -> None:
        self._favorites = self._load_favorites()
        self._refresh_favorite_state()

        menu = QMenu(self)
        if self._favorites:
            for item in self._favorites:
                title = item.get("title") or item.get("url") or "未命名"
                url = item.get("url") or ""
                action = menu.addAction(title)
                action.setToolTip(url)
                action.triggered.connect(lambda checked=False, u=url: self.load_url(u))
        else:
            empty = menu.addAction("暂无收藏")
            empty.setEnabled(False)

        if self.current_url():
            menu.addSeparator()
            if self._current_favorite_index() is None:
                add_action = menu.addAction("收藏当前网页")
            else:
                add_action = menu.addAction("取消收藏当前网页")
            add_action.triggered.connect(self._toggle_favorite)

        menu.exec(self._favorites_btn.mapToGlobal(self._favorites_btn.rect().bottomLeft()))

    def _load_favorites(self) -> list[dict[str, str]]:
        raw = QSettings(_SETTINGS_ORG, _SETTINGS_APP).value(_FAVORITES_KEY, "[]")
        if not isinstance(raw, str):
            return []
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            return []
        if not isinstance(data, list):
            return []
        result: list[dict[str, str]] = []
        for item in data:
            if isinstance(item, dict) and isinstance(item.get("url"), str):
                result.append(
                    {
                        "title": str(item.get("title") or item["url"]),
                        "url": item["url"],
                    }
                )
        return result

    def _save_favorites(self) -> None:
        QSettings(_SETTINGS_ORG, _SETTINGS_APP).setValue(
            _FAVORITES_KEY,
            json.dumps(self._favorites, ensure_ascii=False),
        )

    def keyPressEvent(self, event) -> None:
        if (
            event.modifiers() & Qt.KeyboardModifier.ControlModifier
            and event.key() == Qt.Key.Key_L
        ):
            self.focus_address_bar()
            return
        super().keyPressEvent(event)
