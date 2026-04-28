# Folder Location

左侧多标签页文件夹浏览 + 右侧文件内容预览工具。

## 功能

- **多文件夹标签页**：类似 Chrome，可同时打开任意数量的文件夹，支持拖动排序
- **懒加载树状图**：展开时才读取子目录，无论多复杂的目录结构都能瞬间加载
- **复制路径**：鼠标悬停任意文件/文件夹，点击「复制路径」复制为 `@D:/Code/project/file.md` 格式
- **预览区右键复制**：选中文本后右键可选择 `Copy Path` 或 `Copy`
  - `Copy Path`：复制 `D:/Code/project/file.md:10-20` 加选中文本代码块
  - `Copy`：只复制选中文本；`Ctrl+C` 也保持只复制文本
- **文件预览**：
  - `.md` / `.mdx` — Markdown 渲染（含表格、围栏代码块）
  - `.py` `.ts` `.tsx` `.js` `.json` `.c` `.h` `.go` `.rs` 等 — 语法高亮
  - 图片（`.png` `.jpg` `.gif` `.svg` `.webp`）— 直接显示
  - 其他文本文件 — 等宽字体纯文本显示
- **系统托盘**：关闭窗口时最小化到托盘，单击托盘图标切换显示/隐藏，右键可退出

## 环境要求

- Python 3.12（conda）
- 见 `requirements.txt`

## 安装

```powershell
conda create -n foldertree python=3.12 -y
conda activate foldertree
pip install -r requirements.txt
```

## 运行

```powershell
python main.py
```

## 使用方法

| 操作 | 方式 |
|------|------|
| 添加文件夹 | 点击右上角 **+** 按钮，或按 `Ctrl+O` |
| 切换文件夹 | 点击顶部标签页 |
| 关闭文件夹 | 点击标签页上的 **×** |
| 拖动排序 | 拖拽标签页左右移动 |
| 展开目录 | 点击树状图中的箭头 |
| 预览文件 | 点击任意文件，右侧显示内容 |
| 复制路径 | 鼠标悬停到文件/文件夹，点击「复制路径」 |
| 复制预览选区路径 | 在右侧预览区选中文本后右键点击 `Copy Path` |
| 复制预览选区文本 | 在右侧预览区选中文本后右键点击 `Copy`，或按 `Ctrl+C` |

## 打包为 exe

确保在 conda 环境中已安装依赖：

```powershell
conda activate foldertree
```

### 单文件夹模式（推荐，启动快）

```powershell
pyinstaller --noconsole --name Folder Location --add-data "icon.svg;." main.py
```

生成目录：`dist\Folder Location\Folder Location.exe`

### 单文件模式

```powershell
pyinstaller --noconsole --onefile --name Folder Location --add-data "icon.svg;." main.py
```

生成文件：`dist\Folder Location.exe`

> **注意：**
> - `--add-data "icon.svg;."` 将图标文件打包进去（Windows 路径分隔符用 `;`）
> - 使用了 `QWebEngineView`，单文件夹模式的 `dist` 目录约 150–300 MB，属正常现象
> - 单文件模式首次启动需要解压，速度较慢

### 清理打包缓存

```powershell
Remove-Item -Recurse -Force build, dist, *.spec
```
