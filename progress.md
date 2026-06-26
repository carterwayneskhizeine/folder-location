# Progress: Git 功能实施日志

> 每个工具调用、文件修改、测试结果都在这里

---

## Session 1 — 2026-06-26

### 14:00 启动
- 收到需求：添加 VS Code 风格 git diff + commit 面板
- 调研：项目是 PySide6 桌面应用，已有 sidebar 三面板模式可复用
- 确认用户决策：side-by-side diff / 逐文件 checkbox / VS Code 对齐历史 / 两者结合 repo 定位

### 14:15 规划
- 创建 `task_plan.md` — 7 阶段拆解
- 创建 `findings.md` — 依赖选型记录
- 创建 `progress.md` — 本文件
- 选定技术路径：`subprocess` git CLI + `unidiff` + 自绘 side-by-side

### 14:25 阶段 1+2 完成
- ✅ git 2.54.0 已装，Python 3.13.5（实际）但 foldertree 仍是 3.12
- ✅ `git_backend.py` 完成（327 行，零依赖）
- ✅ `test_git_backend.py` 5 个测试全部通过：
  - branch 检测
  - status 解析（含中文文件名）
  - diff 解析（行级 +/-, hunks）
  - add + commit + log
  - 中文文件名（UTF-8 正确）
- 修了 1 个 bug：`label` 字段对 `x=" " y="M"` 情况返回空字符串
- 决定：subprocess + 自解析（不用 unidiff / GitPython）

### 14:50 阶段 3 完成
- ✅ `left_panel.py` 加第 4 个 sidebar 按钮（GIT_BRANCH 图标）
- ✅ stack 现在有 4 个页面（tree / history / git / settings）
- ✅ `_show_git()` 新方法：切换时让 git_panel 自动从当前文件夹推断 repo
- ✅ `git_panel.py` 创建（220 行），含 4 个组件：
  - `RepoBar` — 路径下拉 + 浏览 + 刷新
  - `BranchLabel` — 分支名 + 计数
  - `FileListPlaceholder` — 阶段 4 替换
  - `CommitBox` — 消息框 + 按钮（commit/discard，阶段 6 实现）
- ✅ 冒烟测试通过：stack=4，所有子组件就位
- 文件树切换 → 自动同步到 git_panel（如果该路径在 .git 内）

### 15:15 阶段 4 完成
- ✅ `git_file_list.py` 创建（260 行）— 独立组件
- ✅ `GroupHeader` — 可点击折叠/展开的分组标题
- ✅ `FileRowWidget` — checkbox + 状态徽章 (A/M/D/?) + 文件名 + 增减统计
- ✅ `FileList` — 三组(STAGED/CHANGES/UNTRACKED) 动态填充 + clear
- ✅ `git_panel.FileListPlaceholder` → 真 `FileList`
- ✅ wire 上 `selection_changed` → backend.add/reset 联动
- ✅ 冒烟测试通过：4 行文件（3 changes + 1 untracked），checkbox 勾选 → selected_paths 正确
- ✅ commit 按钮：只有 staged 有文件时才启用

### 15:35 阶段 5 完成
- ✅ `diff_view.py` 创建（240 行）
- ✅ `DiffSide` (`QPlainTextEdit` 子类)：自绘行号 + 染色背景
- ✅ `DiffView` 主组件：左右双栏 + 共享滚动条 + 文件头
- ✅ `_align_lines()` 把 hunk 转成左右对齐的行序列
- ✅ `git_panel` 改成 splitter：左 = file_list+commit / 右 = diff_view
- ✅ `_on_file_clicked` → 调 backend.diff() → 渲染
- ✅ 实测：左栏 value=20 → 右栏 value=20（同步滚动生效）
- ✅ binary 文件 / 无 diff / 错误 都有兜底
- 性能：`QPlainTextEdit` + 一次性 fill 文本（不用 cell widget），5000 行上限

### 下一步
- （全部完成 ✅）

---

## 文件变更记录

| 文件 | 操作 | 时间 | 备注 |
|------|------|------|------|
| `task_plan.md` | 新建 | 2026-06-26 | 7 阶段拆解 |
| `findings.md` | 新建 | 2026-06-26 | 依赖选型 |
| `progress.md` | 新建 | 2026-06-26 | 会话日志 |
| `git_backend.py` | 新建 | 2026-06-26 | 327 行后端 |
| `test_git_backend.py` | 新建 | 2026-06-26 | 5 个测试全过 |
| `git_panel.py` | 新建 | 2026-06-26 | 220 行骨架 |
| `left_panel.py` | 修改 | 2026-06-26 | 加 git 按钮 + 第 4 页面 |
| `smoke_test_stage3.py` | 新建 | 2026-06-26 | 冒烟测试 |
| `git_file_list.py` | 新建 | 2026-06-26 | 260 行文件列表组件 |
| `git_panel.py` | 修改 | 2026-06-26 | 集成 FileList + add/reset 联动 |
| `smoke_test_stage4.py` | 新建 | 2026-06-26 | 冒烟测试通过 |
| `diff_view.py` | 新建 | 2026-06-26 | 240 行 side-by-side diff |
| `git_panel.py` | 修改 | 2026-06-26 | 改成 splitter + 加 _show_diff_for |
| `smoke_test_stage5.py` | 新建 | 2026-06-26 | 冒烟测试通过（同步滚动实测） |
| `git_panel.py` | 修改 | 2026-06-26 | 真 commit + Discard + Ctrl+Enter + 错误处理 |
| `smoke_test_stage6.py` | 新建 | 2026-06-26 | 7/7 通过 |
| `git_log_list.py` | 新建 | 2026-06-26 | 180 行 commit 历史列表 |
| `git_panel.py` | 修改 | 2026-06-26 | 加 ViewTabBar + History 视图 + commit click |
| `smoke_test_stage7.py` | 新建 | 2026-06-26 | 5/5 通过 |
| `smoke_integration.py` | 新建 | 2026-06-26 | MainWindow 全量集成测试通过 |
| `README.md` | 修改 | 2026-06-26 | 加 Git 功能描述 + 8 行使用方法 |
| `left_panel.py` | 修改 | 2026-06-26 | 跳过：会话恢复依赖 set_repo() 已支持 |

---

## 错误日志

| 错误 | 次数 | 解决 |
|------|------|------|
| `label` 字段对 `x=" "` 情况返回空 | 1 | 加 `.strip()` 并拆分 x/y 判断 |
| 测试 fake mousePressEvent 触发 super() 错误 | 1 | 改用 `set_expanded()` 直接测 |
| PySide6 `receivers()` 不接 SignalInstance | 1 | 改用 `setValue()` 实测同步 |
| QTextCursor import 错误（QtWidgets 没有） | 1 | 删除未用的 import |
