# Findings: Git Diff & Commit 功能调研

> 所有技术发现、参考链接、代码片段、API 测试结果都在这里

---

## 依赖库评估

### GitPython
- **官网**：https://gitpython.readthedocs.io/
- **优点**：完整 API 封装，对象化（`Repo` / `Index` / `Diff`）
- **缺点**：
  - Windows + PyInstaller 有坑（依赖 `gitdb`，`async` 包）
  - 版本兼容性（GitPython 3.1+ 要求 Git 2.x+）
- **结论**：✅ 可用，但需验证打包

### 直接 subprocess 调 git CLI
- **优点**：零依赖，跨平台稳定
- **缺点**：要自己 parse 输出（特别是中文文件名）
- **结论**：✅ 备用方案，更可控

### unidiff（parse `git diff` 输出）
- **官网**：https://github.com/matiasb/python-unidiff
- **优点**：简单，纯 Python
- **结论**：⏸️ 暂不使用 — 需要额外依赖，自己 parse 也很简单

### 决定：零依赖方案
- `subprocess.run(["git", ...])` 调 git CLI
- `--porcelain` 给 status，`--unified=N` 给 diff，`--oneline` 给 log
- diff 自己解析（每行首字符 `+/-/ `/`\` 已包含全部信息）
- 优点：打包零风险（git 是用户系统已有的），无 Python 版本兼容问题

### diff-match-patch（Google）
- **官网**：https://github.com/google/diff-match-patch
- **结论**：❌ 不需要，字符级 diff 对我们过细

---

## 实现策略（最终）

**底层**：用 `subprocess` 调 `git` CLI（避免 GitPython 的 PyInstaller 坑）
**解析**：`unidiff` 解析 `git diff --unified=N` 输出
**UI**：自绘 side-by-side（`QPlainTextEdit` 双栏 + 同步滚动）

---

## API 测试记录

（实施时记录）

### `git status --porcelain`
- 输出格式：`XY filename` （X=staged, Y=unstaged, ?=untracked）
- 状态码：M=modified, A=added, D=deleted, R=renamed, ??=untracked
- 中文文件名是 UTF-8 编码，需用 `encoding='utf-8'`

### `git diff --unified=0`
- 给出行级 diff，0 上下文行最省空间
- 配合 `unidiff` 解析

### `git log --oneline -n 20`
- 简易历史格式

---

## 参考资料

- VS Code Source Control 面板截图：https://code.visualstudio.com/docs/sourcecontrol/overview
- `git status` 状态码：https://git-scm.com/docs/git-status#_short_format
- PyInstaller + GitPython issue：https://github.com/pyinstaller/pyinstaller/issues/4693

---

## 问题与坑（实施中记录）

| 坑 | 解决方案 |
|----|--------|
|  |  |
