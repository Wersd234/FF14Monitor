from PyQt6.QtWidgets import QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, QLabel, QTabWidget
from src.ui.death_recap import DeathRecapWidget
from src.ui.history_panel import HistoryPanelWidget
from src.ui.radar_canvas import RadarCanvasWidget
from src.ui.planner_widget import TimelinePlannerWidget

# 引入我们刚刚重构的排轴控制器 (大脑)
from src.controllers.planner_controller import PlannerController


class MainWindow(QMainWindow):
    def __init__(self, act_log_dir: str):
        super().__init__()
        self.setWindowTitle("FF14 终极高难战术控制台 (沙盘回放 + 协作排轴)")
        self.resize(1440, 900)
        self.setStyleSheet("background-color: #121212; color: #ffffff;")

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(5, 5, 5, 5)

        # ==========================================
        # 核心标签页容器
        # ==========================================
        self.tabs = QTabWidget()
        self.tabs.setStyleSheet("""
            QTabWidget::pane { border: 1px solid #333; background: #121212; }
            QTabBar::tab { background: #2A2A2A; color: #AAA; padding: 12px 25px; font-size: 16px; font-weight: bold; border-top-left-radius: 6px; border-top-right-radius: 6px;}
            QTabBar::tab:selected { background: #4169E1; color: #FFF; }
            QTabBar::tab:hover:!selected { background: #444; }
        """)

        # ==========================================
        # Tab 1: 战术复盘 (历史列表 + 法医报告 + 2D 雷达)
        # ==========================================
        self.tab_replay = QWidget()
        replay_layout = QHBoxLayout(self.tab_replay)

        # 左侧面板 (日志读取与死因分析)
        left_layout = QVBoxLayout()
        self.status_label = QLabel("🟢 核心引擎待命中...")
        self.status_label.setStyleSheet("font-size: 14px; font-weight: bold; color: #888; margin-bottom: 5px;")

        self.history_panel = HistoryPanelWidget(act_log_dir)
        self.death_recap_widget = DeathRecapWidget()

        left_layout.addWidget(self.status_label)
        left_layout.addWidget(self.history_panel, stretch=1)
        left_layout.addWidget(self.death_recap_widget, stretch=1)

        # 右侧面板 (2D 走位沙盘)
        self.radar_widget = RadarCanvasWidget()

        replay_layout.addLayout(left_layout, 4)
        replay_layout.addWidget(self.radar_widget, 6)

        # ==========================================
        # Tab 2: 减伤排轴 (全新 MVC 架构协作沙盘)
        # ==========================================
        # 1. 实例化 Controller 大脑
        self.planner_controller = PlannerController()
        # 2. 实例化 UI，并将大脑注入其中
        self.tab_planner = TimelinePlannerWidget(self.planner_controller)
        # 3. 让大脑装载初始数据
        self.planner_controller.load_initial_data()

        # ==========================================
        # 组装 Tab 并连线
        # ==========================================
        self.tabs.addTab(self.tab_replay, "🎬 实战灭团法医分析 (2D雷达)")
        self.tabs.addTab(self.tab_planner, "🛡️ 多人协作排轴沙盘 (Planner)")
        main_layout.addWidget(self.tabs)

        # 将历史列表中选中的死亡记录，发送给法医面板和雷达画板
        self.history_panel.report_selected_signal.connect(self.display_death_recap)

    def update_status(self, text: str):
        """供后台线程调用，更新左上角的文字状态"""
        self.status_label.setText(text)

    def display_death_recap(self, report_data: dict):
        """当用户点击某次死亡记录时触发"""
        self.death_recap_widget.update_report(report_data)
        self.radar_widget.load_replay(report_data)