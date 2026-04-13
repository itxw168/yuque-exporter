@echo off
echo 正在打包程序...
python -m PyInstaller --onefile --windowed --name "语雀知识库导出工具" gui_app.py
echo 打包完成！
pause
