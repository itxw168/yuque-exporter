# 语雀知识库导出工具（yuque-exporter）

带图形化界面的**语雀知识库**批量导出工具（Python + PyInstaller 打包，单 exe 可运行）。

## 功能
- 输入语雀公开知识库 URL，一键批量导出为 Markdown
- 实时进度显示，支持自定义保存目录
- 详情见 `源代码原理及作用说明.md` / `打包说明.md`

## 使用
- 预编译包：**Releases** 附件下载 `语雀知识库导出工具.zip`（解压双击 `启动程序.bat`）
- 源码运行：`pip install -r requirements.txt && python yuque_exporter.py`（GUI：`gui_app.py`）

## 构建
- 运行 `打包程序.bat` 生成单 exe / 压缩包（需要 PyInstaller）

## License
[MIT](LICENSE) © 2026 xiaowei