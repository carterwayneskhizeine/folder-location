"""Git 后端：封装 git CLI 调用，零外部依赖。

设计原则
--------
- 所有 IO 用 ``subprocess.run`` 调 git CLI（git 是用户系统已有的，零打包风险）
- 状态数据用 dataclass 暴露，方便 UI 直接渲染
- 长时间操作（status / diff / log）跑在 ``QThread`` 里，调用方负责调度

git status porcelain 双字符格式
-------------------------------
XY filename
X = 暂存区状态, Y = 工作区状态, ? = 未跟踪

常用状态码：
  M  modified       A  added         D  deleted
  R  renamed        C  copied        U  updated
  ?  untracked      !  ignored       " " no change

详见 https://git-scm.com/docs/git-status#_short_format
"""
from __future__ import annotations

import re
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path


# ── 数据模型 ────────────────────────────────────────────────────────────────


# 状态码映射 → 人类可读 + 排序权重（VS Code 风格）
_STATUS_INDEX: dict[str, tuple[str, int]] = {
    # staged
    "A":  ("added",      1),
    "M":  ("modified",   2),
    "D":  ("deleted",    3),
    "R":  ("renamed",    4),
    "C":  ("copied",     5),
    # unstaged
    ".M": ("modified",   2),
    ".D": ("deleted",    3),
    # untracked / conflict
    "??": ("untracked",  6),
    "!!": ("ignored",    9),
    "UU": ("conflict",   0),  # 最高优先级
}


@dataclass
class FileStatus:
    """一个文件的 git 状态。"""
    path: str               # 相对仓库根的路径
    x: str = ""             # 暂存区状态码
    y: str = ""             # 工作区状态码
    is_untracked: bool = False
    is_staged: bool = False
    is_dirty: bool = False  # 工作区有改动
    old_path: str | None = None  # rename 源

    @property
    def code(self) -> str:
        if self.is_untracked:
            return "??"
        return f"{self.x}{self.y}" if self.x or self.y else ""

    @property
    def label(self) -> str:
        if self.is_untracked:
            return "Untracked"
        x = self.x.strip()
        y = self.y.strip()
        if x and y:
            x_label = _STATUS_INDEX.get(x, (x, 0))[0]
            y_label = _STATUS_INDEX.get(f".{y}", (y, 0))[0]
            return f"{x_label} + {y_label}"
        if x:
            return _STATUS_INDEX.get(x, (x, 0))[0]
        if y:
            return _STATUS_INDEX.get(f".{y}", (y, 0))[0]
        return "clean"

    @property
    def sort_key(self) -> int:
        if self.is_untracked:
            return _STATUS_INDEX["??"][1]
        if self.x in _STATUS_INDEX:
            return _STATUS_INDEX[self.x][1]
        if self.y:
            return _STATUS_INDEX.get(f".{self.y}", ("", 8))[1]
        return 8


@dataclass
class Hunk:
    """diff 中的一个 hunk（@@ ... @@）。"""
    old_start: int
    old_count: int
    new_start: int
    new_count: int
    lines: list[tuple[str, str]] = field(default_factory=list)
    # 每行：(" " text) / ("+" text) / ("-" text)


@dataclass
class FileDiff:
    """一个文件的完整 diff。"""
    path: str
    old_path: str | None = None    # rename 时使用
    is_new: bool = False
    is_deleted: bool = False
    is_binary: bool = False
    hunks: list[Hunk] = field(default_factory=list)

    @property
    def additions(self) -> int:
        return sum(1 for h in self.hunks for sign, _ in h.lines if sign == "+")

    @property
    def deletions(self) -> int:
        return sum(1 for h in self.hunks for sign, _ in h.lines if sign == "-")


@dataclass
class Commit:
    """git log 中的一个提交。"""
    sha: str            # 完整 hash
    short_sha: str      # 7 位
    summary: str        # commit message 第一行
    author: str
    date: str           # ISO 格式


# ── 后端 ──────────────────────────────────────────────────────────────────


class GitBackend:
    """git CLI 的薄包装。

    使用方式：
        backend = GitBackend(Path("/path/to/repo"))
        files = backend.status()
        diff_text = backend.diff("README.md")
        commits = backend.log(20)
    """

    def __init__(self, repo: Path) -> None:
        self.repo = Path(repo).resolve()
        self._git: str = shutil.which("git") or "git"

    # ── 工具 ──

    @staticmethod
    def is_git_installed() -> bool:
        return shutil.which("git") is not None

    def is_valid_repo(self) -> bool:
        return (self.repo / ".git").exists()

    def _run(self, *args: str, check: bool = False,
             input_text: str | None = None) -> subprocess.CompletedProcess:
        """调 git，cwd 设为 repo 根，UTF-8 解码。"""
        return subprocess.run(
            [self._git, *args],
            cwd=str(self.repo),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            input=input_text,
            check=check,
        )

    # ── 元信息 ──

    def current_branch(self) -> str:
        """当前分支名（detached HEAD 时返回短 SHA）。"""
        r = self._run("symbolic-ref", "--short", "HEAD")
        if r.returncode == 0:
            return r.stdout.strip()
        # detached
        r2 = self._run("rev-parse", "--short", "HEAD")
        return r2.stdout.strip() if r2.returncode == 0 else "(detached)"

    # ── status ──

    def status(self) -> list[FileStatus]:
        """解析 ``git status --porcelain`` 输出。"""
        r = self._run("status", "--porcelain", "-z", "--untracked-files=all")
        if r.returncode != 0:
            return []

        files: list[FileStatus] = []
        # -z 模式：\0 分隔条目；rename 是 "XY\0old\0new"
        entries = r.stdout.split("\x00")
        i = 0
        while i < len(entries):
            entry = entries[i]
            if not entry or len(entry) < 3:
                i += 1
                continue
            code = entry[:2]
            # rename 模式：下个 entry 是新文件名
            if code.startswith("R") or code.startswith("C"):
                old_path = entry[3:]
                if i + 1 < len(entries):
                    i += 1
                    new_path = entries[i]
                else:
                    new_path = old_path
                files.append(FileStatus(
                    path=new_path,
                    x=code[0],
                    y=code[1],
                    is_staged=True,
                    old_path=old_path,
                ))
            elif code == "??":
                files.append(FileStatus(
                    path=entry[3:],
                    is_untracked=True,
                ))
            else:
                files.append(FileStatus(
                    path=entry[3:],
                    x=code[0],
                    y=code[1],
                    is_staged=code[0] != " " and code[0] != "?",
                    is_dirty=code[1] != " " and code[1] != "?",
                ))
            i += 1

        # 按状态排序（staged 在前，untracked 在后）
        files.sort(key=lambda f: (f.sort_key, f.path.lower()))
        return files

    # ── diff ──

    def diff(self, path: str, *, staged: bool = False,
             context: int = 3) -> FileDiff:
        """获取单文件 diff。

        - ``staged=False``：工作区 vs 暂存区（或 HEAD）
        - ``staged=True``：暂存区 vs HEAD
        """
        args = ["diff", f"--unified={context}"]
        if staged:
            args.append("--cached")
        args += ["--", path]

        r = self._run(*args)
        return self._parse_diff(r.stdout, path)

    def diff_range(self, old_rev: str, new_rev: str, path: str,
                   context: int = 3) -> FileDiff:
        """获取两个 commit 之间的 diff（用于历史查看）。"""
        r = self._run("diff", f"--unified={context}", old_rev, new_rev, "--", path)
        return self._parse_diff(r.stdout, path)

    @staticmethod
    def _parse_diff(text: str, path: str) -> FileDiff:
        """解析 unified diff 文本为 ``FileDiff``。"""
        if not text.strip():
            return FileDiff(path=path)

        is_new = is_deleted = is_binary = False
        old_path: str | None = None
        hunks: list[Hunk] = []
        current: Hunk | None = None

        for line in text.splitlines():
            if line.startswith("diff --git "):
                # 新文件开始
                continue
            if line.startswith("new file mode"):
                is_new = True
                continue
            if line.startswith("deleted file mode"):
                is_deleted = True
                continue
            if line.startswith("Binary files") or "GIT binary patch" in line:
                is_binary = True
                continue
            if line.startswith("rename from "):
                old_path = line[len("rename from "):]
                continue
            if line.startswith("--- "):
                if line == "--- /dev/null":
                    is_new = True
                continue
            if line.startswith("+++ "):
                if line == "+++ /dev/null":
                    is_deleted = True
                continue
            m = re.match(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@", line)
            if m:
                current = Hunk(
                    old_start=int(m.group(1)),
                    old_count=int(m.group(2) or 1),
                    new_start=int(m.group(3)),
                    new_count=int(m.group(4) or 1),
                )
                hunks.append(current)
                continue
            if current is None:
                continue
            if line.startswith("+"):
                current.lines.append(("+", line[1:]))
            elif line.startswith("-"):
                current.lines.append(("-", line[1:]))
            elif line.startswith(" "):
                current.lines.append((" ", line[1:]))
            elif line.startswith("\\ No newline"):
                # 末尾标记，忽略
                continue

        return FileDiff(
            path=path,
            old_path=old_path,
            is_new=is_new,
            is_deleted=is_deleted,
            is_binary=is_binary,
            hunks=hunks,
        )

    # ── 暂存 / 取消暂存 ──

    def add(self, paths: list[str]) -> tuple[bool, str]:
        """``git add`` 一个或多个路径。"""
        if not paths:
            return True, ""
        r = self._run("add", "--", *paths)
        return r.returncode == 0, r.stderr.strip()

    def reset(self, paths: list[str]) -> tuple[bool, str]:
        """取消暂存（``git reset HEAD``）。"""
        if not paths:
            return True, ""
        r = self._run("reset", "HEAD", "--", *paths)
        return r.returncode == 0, r.stderr.strip()

    def discard(self, paths: list[str]) -> tuple[bool, str]:
        """放弃工作区改动（``git checkout --``）。危险操作，调用方需二次确认。"""
        if not paths:
            return True, ""
        r = self._run("checkout", "--", *paths)
        return r.returncode == 0, r.stderr.strip()

    # ── commit ──

    def commit(self, message: str) -> tuple[bool, str, str]:
        """提交。返回 ``(ok, sha_or_error, stderr)``。"""
        if not message.strip():
            return False, "", "Commit message is empty"
        r = self._run("commit", "-m", message)
        if r.returncode != 0:
            return False, "", r.stderr.strip()
        # 取刚提交的 SHA
        sha_r = self._run("rev-parse", "HEAD")
        sha = sha_r.stdout.strip() if sha_r.returncode == 0 else ""
        return True, sha, ""

    # ── log ──

    def log(self, limit: int = 20) -> list[Commit]:
        """最近 N 个提交。"""
        fmt = "%H%x00%h%x00%s%x00%an%x00%aI"
        r = self._run("log", f"--pretty=format:{fmt}", f"-n{limit}")
        if r.returncode != 0:
            return []
        commits: list[Commit] = []
        for line in r.stdout.splitlines():
            if not line:
                continue
            parts = line.split("\x00")
            if len(parts) >= 5:
                commits.append(Commit(
                    sha=parts[0],
                    short_sha=parts[1],
                    summary=parts[2],
                    author=parts[3],
                    date=parts[4],
                ))
        return commits

    # ── repo 根解析 ──

    @staticmethod
    def find_repo_root(start: Path) -> Path | None:
        """向上递归找 ``.git`` 目录。"""
        start = Path(start).resolve()
        if start.is_file():
            start = start.parent
        cur = start
        for _ in range(20):  # 最多 20 层
            if (cur / ".git").exists():
                return cur
            parent = cur.parent
            if parent == cur:
                return None
            cur = parent
        return None
