import os
import time
from PyQt6.QtCore import QThread, pyqtSignal

class ACTLogTailer(QThread):
    new_log_line_signal = pyqtSignal(str)

    def __init__(self, log_file_path: str):
        super().__init__()
        self.log_file_path = log_file_path
        self._is_running = True

    def run(self):
        # 如果文件不存在，我们就建一个空的，方便你测试！
        if not os.path.exists(self.log_file_path):
            with open(self.log_file_path, 'w', encoding='utf-8') as f:
                f.write("00|2026-01-01T00:00:00|Log Started\n")
            print(f"找不到日志，已自动为你创建测试日志文件: {self.log_file_path}")

        with open(self.log_file_path, 'r', encoding='utf-8') as f:
            f.seek(0, os.SEEK_END)
            while self._is_running:
                line = f.readline()
                if not line:
                    time.sleep(0.1)
                    continue
                self.new_log_line_signal.emit(line.strip())

    def stop(self):
        self._is_running = False
        self.wait()