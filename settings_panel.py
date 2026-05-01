"""设置面板 — 复制路径格式选项。"""
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QComboBox, QCheckBox, QGroupBox,
)
from PySide6.QtCore import Qt, Signal, QSettings

_SETTINGS_ORG = "FolderTree"
_SETTINGS_APP = "FolderTree"


class SettingsPanel(QWidget):
    settings_changed = Signal()

    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(16)

        title = QLabel("设置")
        title.setStyleSheet("font-size: 16px; font-weight: 600;")
        layout.addWidget(title)

        # ── 复制路径格式 ──
        copy_group = QGroupBox("复制路径格式")
        copy_group.setStyleSheet(
            "QGroupBox { font-size: 13px; font-weight: 500; "
            "border: 1px solid #2f3336; border-radius: 8px; "
            "margin-top: 10px; padding: 14px 12px 12px 12px; }"
            "QGroupBox::title { subcontrol-origin: margin; left: 12px; padding: 0 6px; }"
        )
        gl = QVBoxLayout(copy_group)
        gl.setSpacing(12)

        # @ 前缀
        self._prefix_check = QCheckBox("复制路径时添加 \"@\" 前缀")
        self._prefix_check.stateChanged.connect(self._save)
        gl.addWidget(self._prefix_check)

        # 路径分隔符
        sep_row = QWidget()
        sr = QVBoxLayout(sep_row)
        sr.setContentsMargins(0, 0, 0, 0)
        sr.setSpacing(4)

        sep_label = QLabel("路径分隔符")
        sep_label.setStyleSheet("color: #e7e9ea; font-size: 13px;")
        sr.addWidget(sep_label)

        self._sep_combo = QComboBox()
        self._sep_combo.addItem("正斜杠  /  (D:/Code/file.py)", "/")
        self._sep_combo.addItem("反斜杠  \\  (D:\\Code\\file.py)", "\\")
        self._sep_combo.setStyleSheet(
            "QComboBox { background: #16181c; border: 1px solid #2f3336; "
            "border-radius: 6px; padding: 6px 10px; color: #e7e9ea; font-size: 13px; }"
            "QComboBox::drop-down { border: none; width: 20px; }"
            "QComboBox::down-arrow { image: none; border-left: 4px solid transparent; "
            "border-right: 4px solid transparent; border-top: 6px solid #71767b; }"
            "QComboBox QAbstractItemView { background: #16181c; border: 1px solid #2f3336; "
            "color: #e7e9ea; selection-background-color: #2f3336; }"
        )
        self._sep_combo.currentIndexChanged.connect(self._save)
        sr.addWidget(self._sep_combo)
        gl.addWidget(sep_row)

        # 预览
        self._preview_label = QLabel()
        self._preview_label.setStyleSheet(
            "color: #71767b; font-family: 'JetBrains Mono', 'Consolas', monospace; "
            "font-size: 12px; padding: 6px 0;"
        )
        gl.addWidget(self._preview_label)

        layout.addWidget(copy_group)
        layout.addStretch(1)

        self._load()
        self._update_preview()

    # ── 持久化 ──

    def _load(self) -> None:
        s = QSettings(_SETTINGS_ORG, _SETTINGS_APP)
        prefix = s.value("settings/copy_prefix", True)
        if isinstance(prefix, str):
            prefix = prefix.lower() in ("true", "1", "yes")
        self._prefix_check.setChecked(bool(prefix))

        sep = s.value("settings/path_separator", "/")
        if sep not in ("/", "\\"):
            sep = "/"
        idx = 0 if sep == "/" else 1
        self._sep_combo.setCurrentIndex(idx)

    def _save(self) -> None:
        s = QSettings(_SETTINGS_ORG, _SETTINGS_APP)
        s.setValue("settings/copy_prefix", self._prefix_check.isChecked())
        s.setValue("settings/path_separator", self.sep_value())
        self._update_preview()
        self.settings_changed.emit()

    def _update_preview(self) -> None:
        path = "D:/Code/folder-location/main.py"
        if self.sep_value() == "\\":
            path = path.replace("/", "\\")
        prefix = "@" if self._prefix_check.isChecked() else ""
        self._preview_label.setText(f"预览：{prefix}{path}")

    # ── 公共接口 ──

    def prefix_enabled(self) -> bool:
        return self._prefix_check.isChecked()

    def sep_value(self) -> str:
        return self._sep_combo.currentData()

    def format_path(self, raw: str) -> str:
        sep = self.sep_value()
        if sep == "\\":
            raw = raw.replace("/", "\\")
        else:
            raw = raw.replace("\\", "/")
        if self._prefix_check.isChecked():
            raw = "@" + raw
        return raw


# ── 模块级函数：供 tree / history / render 调用 ─────────────────────────────

def format_copy_path(raw: str) -> str:
    """根据当前设置格式化路径（不依赖 SettingsPanel 实例）。"""
    s = QSettings(_SETTINGS_ORG, _SETTINGS_APP)
    prefix = s.value("settings/copy_prefix", True)
    if isinstance(prefix, str):
        prefix = prefix.lower() in ("true", "1", "yes")
    sep = s.value("settings/path_separator", "/")
    if sep not in ("/", "\\"):
        sep = "/"
    if sep == "\\":
        raw = raw.replace("/", "\\")
    else:
        raw = raw.replace("\\", "/")
    if prefix:
        raw = "@" + raw
    return raw
