import sys
import traceback
from PyQt6.QtWidgets import QApplication
from src.core.history_reader import HistoryLogReader
from src.ui.main_window import MainWindow

# 【在此填入你真实的 ACT 日志路径】
# 比如: r"C:\Advanced Combat Tracker\FFXIVLogs"
ACT_LOGS_DIR = r"F:\FF14 ACT\AppData\Advanced Combat Tracker\FFXIVLogs"


# ==============================================================
# 全局异常捕获器：绝不允许 PyQt 底层 C++ 崩溃 (0xC0000409)！
# 任何报错都会被翻译成 Python 错误栈打印在控制台
# ==============================================================
def global_exception_handler(exctype, value, tb):
    print("\n" + "!" * 50)
    print("🚨 程序遇到异常，但被全局护盾拦截！具体原因如下：")
    traceback.print_exception(exctype, value, tb)
    print("!" * 50 + "\n")


sys.excepthook = global_exception_handler


class AppController:
    """生命周期大管家：管理 UI 和后台读取线程"""

    def __init__(self):
        self.main_window = MainWindow(ACT_LOGS_DIR)

        # 监听 UI [实战分析] Tab 中点击“📂 解析”按钮的信号
        self.main_window.history_panel.parse_file_signal.connect(self.start_history_parse)
        self.history_reader = None

    def start_history_parse(self, file_path: str):
        """线程安全控制：如果有人狂点解析按钮，先安全杀掉上一个线程"""
        if self.history_reader is not None and self.history_reader.isRunning():
            self.main_window.update_status("正在安全中止上一个解析任务...")
            self.history_reader.terminate()
            self.history_reader.wait()
            self.history_reader = None

        # 启动全新的后台多线程日志分析大闸蟹
        self.history_reader = HistoryLogReader(file_path)

        # 把后台分析的进度文字发送给主窗口的状态栏
        self.history_reader.progress_signal.connect(self.main_window.update_status)
        # 分析完成后，把整理好的数据发送给左侧的历史树状列表
        self.history_reader.history_parsed_signal.connect(self.main_window.history_panel.load_parsed_data)

        # 发车！
        self.history_reader.start()


def main():
    app = QApplication(sys.argv)

    # 启用极其美观、跨平台的 Fusion 现代皮肤风格
    app.setStyle("Fusion")

    controller = AppController()
    controller.main_window.show()

    sys.exit(app.exec())


if __name__ == '__main__':
    main()