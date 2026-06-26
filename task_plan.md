# Task Plan: Git Diff & Commit 功能

> 类似 VS Code 的 Source Control 侧边栏
> 状态：⏳ 规划中 → 🔨 实现中 → ✅ 完成

## 目标

为 Folder Location 添加 git 集成面板，包括：
- 文件状态列表（修改/新增/删除/未跟踪）
- Side-by-side diff 视图
- 逐文件暂存（checkbox）
- Commit message 输入 + 提交
- 简易 commit 历史
- 多 repo 支持

## 用户决策（已确认）

| 项 | 选择 |
|----|------|
| Diff 风格 | Side-by-side 双栏 |
| Commit 粒度 | 逐文件 checkbox |
| 历史记录 | 对齐 VS Code（working tree + 暂存 + 最近 commit） |
| 仓库定位 | 两者结合（标签页 + 独立选择） |

---

## 阶段划分

### 阶段 1：调研与依赖选型  ✅ 完成
- [x] 评估 `GitPython` vs 直接 `subprocess` 调 git CLI
- [x] 选择 diff 渲染库（`diff-match-patch` / `dulwich` / 自写）
- [x] 验证 Windows + Python 3.12 兼容性
- [x] 确认打包兼容性（PyInstaller 单文件夹模式）

**输出**：✅ 零依赖方案（subprocess + 自解析）

### 阶段 2：基础架构搭建  ✅ 完成
- [x] `git_backend.py` — 封装 git 操作（status / diff / add / commit / log）
- [x] 数据模型：`FileStatus` / `Hunk` / `FileDiff` / `Commit`
- [x] `repo` 信号/线程模型（避免阻塞 UI）
- [x] 在 `main.py` 注册到 `QApplication` 生命周期

**输出**：✅ `git_backend.py` + 5 个测试全部通过

### 阶段 3：侧边栏入口  ✅ 完成
- [x] `left_panel.py` 加第 4 个 sidebar 按钮（git 图标）
- [x] 切换到第 4 个 stack 页面
- [x] 复用 `_sidebar_icon` 模式
- [x] 标签页标题显示分支名（需要在 `tree.py` 加钩子）

**输出**：✅ 侧边栏可切换到 git 面板（git_panel.py 占位）

### 阶段 4：文件状态列表（Working Tree 视图）  ✅ 完成
- [x] `git_panel.py` 主体框架
- [x] repo 选择器（顶部下拉）
- [x] 文件列表（按状态分组：Staged / Changes / Untracked）
- [x] 每行：checkbox + 状态图标 + 文件名
- [x] 点击文件 → 触发 diff 加载

**输出**：✅ git_file_list.py (260 行) + git_panel 集成 + 冒烟测试通过

### 阶段 5：Side-by-Side Diff 视图  ✅ 完成
- [x] `diff_view.py` — 双栏 `QPlainTextEdit`（不用 `QTextEdit`，性能更好）
- [x] 红色删除（-）左侧 / 绿色新增（+）右侧
- [x] 上下文行（unchanged）灰显
- [x] 行号 + 同步滚动（实测 left=20 → right=20）
- [x] 大文件性能优化（懒加载 / 截断）

**输出**：✅ diff_view.py (240 行) + git_panel 集成 + 冒烟测试通过

### 阶段 6：Commit 流程  ✅ 完成
- [x] message 输入框（多行）
- [x] `Ctrl+Enter` 快捷键提交
- [x] 提交后自动刷新状态
- [x] 错误处理（无文件、message 为空、git 报错）
- [x] 状态栏反馈（与现有 `_on_copied` 风格一致）

**输出**：✅ 完整 commit + discard 工作流，7 个测试通过

### 阶段 7：Commit 历史 + 收尾  ✅ 完成
- [x] 简易历史列表（最近 N 条）
- [x] 点击 commit → 查看该 commit 的 stat 总览
- [x] 会话恢复（当前选中的 repo）
- [x] 打包验证（PyInstaller 重新生成）
- [x] README 更新

**输出**：✅ git_log_list.py (180 行) + tab 切换 + 集成测试通过 + README 更新

---

## 关键技术决策

### Diff 渲染
- **不用 pygments**（已有）— 它只做语法高亮，不做 diff 对齐
- **候选 1**：`diff-match-patch`（Google）— 字符级 diff，需要自己映射到行级
- **候选 2**：`python-diff` / `unidiff` — 直接 parse `git diff` 输出
- **推荐**：用 git 原生 `--unified=0` 输出 + `unidiff` 解析 + 自渲染

### 性能
- 大仓库 status 可能很慢（>1s），用 `QThread` 后台
- diff 大文件用 `QPlainTextEdit`（`QTextEdit` 会卡）
- 文件列表用 `QListView` + model（不要用 `QListWidget`）

### 复用现有代码
- 复用 `_sidebar_icon` 加 `BRANCH` / `DIFF` 图标
- 复用 `path_copied` 信号（commit hash 复制）
- 复用 `_on_copied` 状态栏模式
- 复用 `theme.py` 的深色配色

---

## 风险与依赖

| 风险 | 缓解 |
|------|------|
| GitPython 在 Windows + PyInstaller 兼容性 | 备用方案：subprocess git CLI |
| 大文件 diff 卡死 | 限制显示行数 + 异步加载 |
| git 命令在用户系统不存在 | 检测 + 友好提示 |
| 文件路径含中文 / 空格 | 用 `Path` 对象，传 `as_posix()` |

---

## 状态变更日志

- `2026-06-26` — 规划启动
