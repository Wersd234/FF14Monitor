# ==========================================
# File: src/ui/fflogs_import_dialog.py
# 职责: 负责渲染弹窗UI，接收输入，并调用 Controller 处理
# ==========================================
import os
import json
import re
from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel,
                             QLineEdit, QPushButton, QMessageBox, QTextEdit)
from PyQt6.QtCore import Qt, QTimer

# 🚀 引入剥离出去的 Controller (Worker)
from src.controllers.fflogs_controller import FFLogsWorker

CONFIG_PATH = os.path.join(os.getcwd(), "assets", "fflogs_config.json")

class FFLogsImportDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("一键导入 FFLogs 时间轴 (国服汉化与逆推版)")
        self.setFixedSize(650, 450)
        self.setStyleSheet("background-color: #1E1E1E; color: #FFF; font-size: 14px;")

        self.timeline_data = None
        self.worker = None

        layout = QVBoxLayout(self)

        layout.addWidget(QLabel("🔗 <b>1. 填入 FFLogs 战斗链接</b> (请确保链接包含 #fight=数字)"))
        self.input_url = QLineEdit()
        self.input_url.setPlaceholderText("例如: https://www.fflogs.com/reports/abc123DEF#fight=10")
        self.input_url.setStyleSheet("padding: 5px; background: #333; border: 1px solid #555;")
        layout.addWidget(self.input_url)

        layout.addWidget(QLabel("\n🔑 <b>2. FFLogs V2 API 密钥</b> (只需填一次，自动保存本地)"))
        desc = QLabel("<a href='https://www.fflogs.com/api/clients' style='color:#00FFCC;'>点击前往 FFLogs 个人设置底部创建 V2 Client 获取</a>")
        desc.setOpenExternalLinks(True)
        layout.addWidget(desc)

        h_client = QHBoxLayout()
        h_client.addWidget(QLabel("Client ID:"))
        self.input_client = QLineEdit()
        self.input_client.setStyleSheet("background: #333; border: 1px solid #555;")
        h_client.addWidget(self.input_client)
        layout.addLayout(h_client)

        h_secret = QHBoxLayout()
        h_secret.addWidget(QLabel("Client Secret:"))
        self.input_secret = QLineEdit()
        self.input_secret.setEchoMode(QLineEdit.EchoMode.Password)
        self.input_secret.setStyleSheet("background: #333; border: 1px solid #555;")
        h_secret.addWidget(self.input_secret)
        layout.addLayout(h_secret)

        self.console = QTextEdit()
        self.console.setReadOnly(True)
        self.console.setStyleSheet("background: #0A0A0A; color: #00FFCC; font-family: Consolas; padding: 5px;")
        layout.addWidget(self.console)

        self.btn_start = QPushButton("🚀 开始智能提取全场时间轴")
        self.btn_start.setStyleSheet("background-color: #4169E1; padding: 8px; font-weight: bold; border-radius: 4px;")
        self.btn_start.clicked.connect(self.start_import)
        layout.addWidget(self.btn_start)

        self.load_config()

    def load_config(self):
        if os.path.exists(CONFIG_PATH):
            try:
                with open(CONFIG_PATH, 'r') as f:
                    data = json.load(f)
                    self.input_client.setText(data.get('client_id', ''))
                    self.input_secret.setText(data.get('client_secret', ''))
            except:
                pass

    def save_config(self):
        os.makedirs(os.path.dirname(CONFIG_PATH), exist_ok=True)
        with open(CONFIG_PATH, 'w') as f:
            json.dump({
                "client_id": self.input_client.text().strip(),
                "client_secret": self.input_secret.text().strip()
            }, f)

    def log(self, text):
        self.console.append(text)
        self.console.verticalScrollBar().setValue(self.console.verticalScrollBar().maximum())

    def start_import(self):
        url = self.input_url.text().strip()
        client_id = self.input_client.text().strip()
        client_secret = self.input_secret.text().strip()

        if not all([url, client_id, client_secret]):
            QMessageBox.warning(self, "错误", "请填满所有字段！")
            return

        # 前端正则校验输入格式
        match = re.search(r'reports/([a-zA-Z0-9]+)(?:.*?fight=([0-9]+|last))?', url)
        if not match:
            QMessageBox.warning(self, "错误", "无法解析该链接，请确认格式是否正确！")
            return

        report_code = match.group(1)
        fight_id = match.group(2) if match.group(2) else "last"

        self.save_config()
        self.btn_start.setEnabled(False)
        self.console.clear()

        # 初始化并调用 Controller
        self.worker = FFLogsWorker(client_id, client_secret, report_code, fight_id)
        self.worker.progress.connect(self.log)
        self.worker.error.connect(self.on_error)
        self.worker.finished.connect(self.on_success)
        self.worker.start()

    def on_error(self, err_msg):
        self.log(f"<span style='color:red;'>❌ 失败: {err_msg}</span>")
        self.btn_start.setEnabled(True)

    def on_success(self, timeline):
        self.timeline_data = timeline
        self.log(f"<br><span style='color:#32CD32; font-weight:bold;'>✅ 成功提取了 {len(timeline)} 个机制！翻译缓存已更新。窗口即将关闭...</span>")
        QTimer.singleShot(2500, self.accept)

    def get_timeline_data(self):
        return self.timeline_data