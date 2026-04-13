#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
import os
import time
import requests
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
    QLabel, QLineEdit, QPushButton, QTextEdit, QFileDialog, QProgressBar,
    QMessageBox
)
from PyQt6.QtCore import QThread, pyqtSignal, Qt
from PyQt6.QtGui import QTextCursor
from yuque_exporter import YuqueExporter


class ExportThread(QThread):
    update_signal = pyqtSignal(str)
    progress_signal = pyqtSignal(int, int)
    finish_signal = pyqtSignal(bool, str)
    
    def __init__(self, kb_url, output_dir):
        super().__init__()
        self.kb_url = kb_url
        self.output_dir = output_dir
        self.is_stopped = False
    
    def stop(self):
        self.is_stopped = True
    
    def run(self):
        try:
            exporter = YuqueExporter(output_dir=self.output_dir)
            
            self.update_signal.emit(f"开始导出知识库: {self.kb_url}")
            self.update_signal.emit("正在获取知识库信息...")
            
            docs = exporter.get_public_kb_docs(self.kb_url)
            total = len(docs)
            self.update_signal.emit(f"找到 {total} 个文档")
            
            if total == 0:
                self.update_signal.emit("未找到文档，请检查URL是否正确")
                self.finish_signal.emit(False, "未找到文档")
                return
            
            success_count = 0
            for i, doc in enumerate(docs):
                if self.is_stopped:
                    self.update_signal.emit("\n导出已停止")
                    self.finish_signal.emit(False, "导出已停止")
                    return
                
                self.progress_signal.emit(i + 1, total)
                self.update_signal.emit(f"正在导出: {doc['title']}")
                
                if exporter.export_doc(doc):
                    success_count += 1
                time.sleep(0.5)
            
            self.update_signal.emit(f"\n导出完成！成功: {success_count}/{total}")
            self.update_signal.emit(f"输出目录: {os.path.abspath(self.output_dir)}")
            
            self.finish_signal.emit(True, f"导出成功！成功导出 {success_count}/{total} 个文档")
            
        except requests.exceptions.RequestException as e:
            self.update_signal.emit(f"网络错误: {str(e)}")
            self.finish_signal.emit(False, f"网络错误: {str(e)}")
        except ValueError as e:
            self.update_signal.emit(f"解析错误: {str(e)}")
            self.finish_signal.emit(False, f"解析错误: {str(e)}")
        except Exception as e:
            self.update_signal.emit(f"导出失败: {str(e)}")
            import traceback
            self.update_signal.emit(f"错误详情: {traceback.format_exc()}")
            self.finish_signal.emit(False, f"导出失败: {str(e)}")


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("语雀知识库导出工具")
        self.setGeometry(100, 100, 800, 600)
        
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        layout = QVBoxLayout(central_widget)
        
        # URL输入
        url_layout = QHBoxLayout()
        url_label = QLabel("知识库URL:")
        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("请输入语雀公开知识库URL，例如: https://www.yuque.com/xxx/xxx")
        url_layout.addWidget(url_label)
        url_layout.addWidget(self.url_input)
        layout.addLayout(url_layout)
        
        # 输出目录
        output_layout = QHBoxLayout()
        output_label = QLabel("输出目录:")
        self.output_input = QLineEdit()
        
        downloads_dir = self.get_downloads_dir()
        self.output_input.setText(downloads_dir)
        
        output_button = QPushButton("浏览")
        output_button.clicked.connect(self.browse_output)
        output_layout.addWidget(output_label)
        output_layout.addWidget(self.output_input)
        output_layout.addWidget(output_button)
        layout.addLayout(output_layout)
        
        # 按钮区域
        button_layout = QHBoxLayout()
        
        self.export_button = QPushButton("开始导出")
        self.export_button.clicked.connect(self.start_export)
        button_layout.addWidget(self.export_button)
        
        self.stop_button = QPushButton("停止")
        self.stop_button.clicked.connect(self.stop_export)
        self.stop_button.setEnabled(False)
        button_layout.addWidget(self.stop_button)
        
        self.exit_button = QPushButton("退出")
        self.exit_button.clicked.connect(self.close)
        button_layout.addWidget(self.exit_button)
        
        layout.addLayout(button_layout)
        
        # 进度条
        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        layout.addWidget(self.progress_bar)
        
        # 导出日志标签
        log_label = QLabel("导出日志:")
        layout.addWidget(log_label)
        
        # 单栏日志区域
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        layout.addWidget(self.log_text)
        
        # 状态
        self.export_thread = None
    
    def get_downloads_dir(self):
        """获取Windows下载目录"""
        if os.name == 'nt':  # Windows系统
            import ctypes
            from ctypes import wintypes
            
            GUID_FOLDERID_Downloads = ctypes.c_byte * 16
            FOLDERID_Downloads = GUID_FOLDERID_Downloads(
                0x37, 0x4D, 0xE2, 0x9B, 0x8B, 0x47, 0x3C, 0x48, 
                0xA9, 0x8F, 0x6C, 0x9E, 0x4A, 0x0B, 0x0C, 0x1B
            )
            
            try:
                SHGetKnownFolderPath = ctypes.windll.shell32.SHGetKnownFolderPath
                SHGetKnownFolderPath.argtypes = [
                    ctypes.POINTER(GUID_FOLDERID_Downloads),
                    wintypes.DWORD,
                    wintypes.HANDLE,
                    ctypes.POINTER(ctypes.c_wchar_p)
                ]
                SHGetKnownFolderPath.restype = wintypes.HRESULT
                
                path = ctypes.c_wchar_p()
                if SHGetKnownFolderPath(ctypes.byref(FOLDERID_Downloads), 0, None, ctypes.byref(path)) == 0:
                    downloads_path = path.value
                    return downloads_path
            except Exception:
                pass
        
        downloads_path = os.path.join(os.path.expanduser('~'), 'Downloads')
        if not os.path.exists(downloads_path):
            downloads_path = os.path.expanduser('~')
        
        return downloads_path
    
    def browse_output(self):
        directory = QFileDialog.getExistingDirectory(self, "选择输出目录")
        if directory:
            self.output_input.setText(directory)
    
    def start_export(self):
        kb_url = self.url_input.text().strip()
        output_dir = self.output_input.text().strip()
        
        if not kb_url:
            QMessageBox.warning(self, "警告", "请输入知识库URL")
            return
        
        if not output_dir:
            QMessageBox.warning(self, "警告", "请输入输出目录")
            return
        
        if not (kb_url.startswith("https://www.yuque.com/") or kb_url.startswith("http://www.yuque.com/")):
            QMessageBox.warning(self, "警告", "请输入有效的语雀知识库URL")
            return
        
        # 清空日志
        self.log_text.clear()
        self.progress_bar.setValue(0)
        self.export_button.setEnabled(False)
        self.stop_button.setEnabled(True)
        
        # 开始导出线程
        self.export_thread = ExportThread(kb_url, output_dir)
        self.export_thread.update_signal.connect(self.update_log)
        self.export_thread.progress_signal.connect(self.update_progress)
        self.export_thread.finish_signal.connect(self.export_finished)
        self.export_thread.start()
    
    def stop_export(self):
        if self.export_thread and self.export_thread.isRunning():
            reply = QMessageBox.question(
                self, 
                "确认停止", 
                "确定要停止导出吗？",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            
            if reply == QMessageBox.StandardButton.Yes:
                self.export_thread.stop()
    
    def update_log(self, message):
        # 添加日志
        self.log_text.append(message)
        
        # 自动滚动到最新内容
        cursor = self.log_text.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        self.log_text.setTextCursor(cursor)
        self.log_text.ensureCursorVisible()
    
    def update_progress(self, current, total):
        self.progress_bar.setMaximum(total)
        self.progress_bar.setValue(current)
    
    def export_finished(self, success, message):
        self.export_button.setEnabled(True)
        self.stop_button.setEnabled(False)
        
        if success:
            QMessageBox.information(self, "成功", message)
        else:
            QMessageBox.critical(self, "失败", message)
    
    def closeEvent(self, event):
        """重写关闭事件，确保线程正确退出"""
        if self.export_thread and self.export_thread.isRunning():
            reply = QMessageBox.question(
                self, 
                "确认退出", 
                "导出任务正在进行中，确定要退出吗？",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            
            if reply == QMessageBox.StandardButton.Yes:
                self.export_thread.stop()
                self.export_thread.wait()
                event.accept()
            else:
                event.ignore()
        else:
            event.accept()


def main():
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == '__main__':
    main()
