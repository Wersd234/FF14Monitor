from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QSlider, QPushButton, QGraphicsView, QGraphicsScene, \
    QGraphicsEllipseItem, QGraphicsTextItem, QLabel, QGraphicsPixmapItem, QGraphicsRectItem
from PyQt6.QtCore import Qt, QTimer, QRectF
from PyQt6.QtGui import QPen, QBrush, QColor, QFont, QPixmap

# 【引入 Controller】
from src.controllers.radar_controller import MapFetcherThread, process_radar_data

JOB_MAP = {
    19: "骑士", 20: "武僧", 21: "战士", 22: "龙骑", 23: "诗人", 24: "白魔", 25: "黑魔",
    27: "召唤", 28: "学者", 30: "忍者", 31: "机工", 32: "暗骑", 33: "占星", 34: "武士",
    35: "赤魔", 37: "绝枪", 38: "舞者", 39: "钐镰", 40: "贤者", 41: "蝰蛇", 42: "画魔"
}

JOB_COLORS = {
    19: "#4169E1", 21: "#4169E1", 32: "#4169E1", 37: "#4169E1",
    24: "#32CD32", 28: "#32CD32", 33: "#32CD32", 40: "#32CD32",
    20: "#DC143C", 22: "#DC143C", 23: "#DC143C", 25: "#DC143C",
    27: "#DC143C", 30: "#DC143C", 31: "#DC143C", 34: "#DC143C",
    35: "#DC143C", 38: "#DC143C", 39: "#DC143C", 41: "#DC143C", 42: "#DC143C"
}


class RadarCanvasWidget(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        controls = QHBoxLayout()
        self.play_btn = QPushButton("▶ 播放")
        self.play_btn.setStyleSheet("background-color: #333; color: white; padding: 5px;")

        self.time_slider = QSlider(Qt.Orientation.Horizontal)
        self.time_slider.setRange(-1500, 100)
        self.time_slider.setValue(-1500)

        self.time_label = QLabel("-15.0s")
        self.time_label.setStyleSheet("color: #00FFCC; font-weight: bold;")
        self.time_label.setFixedWidth(50)

        controls.addWidget(self.play_btn)
        controls.addWidget(self.time_slider)
        controls.addWidget(self.time_label)

        self.view = QGraphicsView()
        self.scene = QGraphicsScene()
        self.view.setScene(self.scene)
        self.view.setStyleSheet("background-color: #1A1A1A; border: 1px solid #333;")
        self.view.setRenderHint(self.view.renderHints().Antialiasing)
        self.view.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.view.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        layout.addLayout(controls)
        layout.addWidget(self.view)

        # 内部状态
        self.tracks = {}
        self.id_to_name = {}
        self.id_to_job = {}
        self.zone_name = ""
        self.zone_id = ""
        self.is_playing = False
        self.current_time = -15.0
        self.main_boss_id = None
        self.entity_items = {}
        self.victim_name = ""
        self.center_x = 100.0
        self.center_y = 100.0

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.on_tick)

        self.play_btn.clicked.connect(self.toggle_play)
        self.time_slider.sliderMoved.connect(self.on_slider_moved)

        # Controller 管理
        self.map_fetcher = None
        self.cached_pixmap = None
        self.cached_map_data = None
        self.grid_item = None

    def load_replay(self, report_data: dict):
        self.timer.stop()
        self.is_playing = False
        self.play_btn.setText("▶ 播放")

        self.victim_name = report_data.get("victim", "")
        new_zone_id = report_data.get("zone_id", "")
        self.zone_name = report_data.get("zone", "未知区域")
        self.id_to_job = report_data.get("jobs", {})
        replay_data = report_data.get("replay_data", [])

        self.entity_items.clear()

        # 【调用 Controller 进行数据整理】
        self.tracks, self.id_to_name, self.main_boss_id = process_radar_data(replay_data, self.victim_name)

        if new_zone_id != self.zone_id:
            self.zone_id = new_zone_id
            self.cached_pixmap = None
            self.cached_map_data = None

            if self.map_fetcher and self.map_fetcher.isRunning():
                self.map_fetcher.terminate()
                self.map_fetcher.wait()

            if self.zone_id and self.zone_id != "Unknown":
                self.map_fetcher = MapFetcherThread(self.zone_id)
                self.map_fetcher.map_ready.connect(self.on_map_downloaded)
                self.map_fetcher.start()

        self.draw_arena(replay_data)

        self.current_time = -15.0
        self.time_slider.setValue(-1500)
        self.update_frame(self.current_time)

    def draw_arena(self, replay_data):
        self.scene.clear()
        self.entity_items.clear()

        if not replay_data: return

        valid_xs = sorted([p['x'] for p in replay_data if p['x'] != 0.0])
        valid_ys = sorted([p['y'] for p in replay_data if p['y'] != 0.0])
        if not valid_xs: valid_xs = [100.0]
        if not valid_ys: valid_ys = [100.0]

        self.center_x = valid_xs[len(valid_xs) // 2]
        self.center_y = valid_ys[len(valid_ys) // 2]

        arena_width = 50
        arena_height = 50
        scale = 15

        w_scaled = arena_width * scale
        h_scaled = arena_height * scale
        tl_x = (self.center_x * scale) - (w_scaled / 2)
        tl_y = (self.center_y * scale) - (h_scaled / 2)

        self.grid_item = QGraphicsRectItem(tl_x, tl_y, w_scaled, h_scaled)
        self.grid_item.setPen(QPen(QColor("#8C7B5D"), 3))
        self.grid_item.setBrush(QBrush(QColor("#E2D4A8")))
        self.grid_item.setZValue(-20)
        self.scene.addItem(self.grid_item)

        if self.cached_pixmap:
            self._render_map_item()

        display_name = self.zone_name if self.zone_id != "Unknown" else "未检测到副本"
        zone_text = self.scene.addText(display_name, QFont("Microsoft YaHei", 20, QFont.Weight.Bold))
        zone_text.setDefaultTextColor(QColor(0, 0, 0, 80))
        zone_text.setPos(self.center_x * scale - zone_text.boundingRect().width() / 2, tl_y + 10)

        n_text = self.scene.addText("N", QFont("Consolas", 14, QFont.Weight.Bold))
        n_text.setDefaultTextColor(QColor("#FF4444"))
        n_text.setPos(self.center_x * scale - 10, tl_y - 30)

        padding = 50
        target_rect = QRectF(tl_x - padding, tl_y - padding, w_scaled + padding * 2, h_scaled + padding * 2)
        self.scene.setSceneRect(target_rect)
        self.view.resetTransform()
        self.view.fitInView(target_rect, Qt.AspectRatioMode.KeepAspectRatio)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self.scene.sceneRect().width() > 0:
            self.view.fitInView(self.scene.sceneRect(), Qt.AspectRatioMode.KeepAspectRatio)

    def on_map_downloaded(self, img_bytes, map_data):
        self.cached_pixmap = QPixmap()
        self.cached_pixmap.loadFromData(img_bytes)
        self.cached_map_data = map_data
        self._render_map_item()

    def _render_map_item(self):
        size_factor = self.cached_map_data.get("SizeFactor", 100) / 100.0
        visual_scale = 0.75 * size_factor

        bg_item = QGraphicsPixmapItem(self.cached_pixmap)
        bg_item.setScale(visual_scale)
        bg_item.setZValue(-10)

        offset_x = (self.center_x * 15) - (1024 * visual_scale)
        offset_y = (self.center_y * 15) - (1024 * visual_scale)
        bg_item.setPos(offset_x, offset_y)

        self.scene.addItem(bg_item)
        if self.grid_item:
            self.grid_item.hide()

    def toggle_play(self):
        self.is_playing = not self.is_playing
        if self.is_playing:
            if self.current_time >= 1.0: self.current_time = -15.0
            self.play_btn.setText("⏸ 暂停")
            self.timer.start(30)
        else:
            self.play_btn.setText("▶ 播放")
            self.timer.stop()

    def on_slider_moved(self, val):
        self.current_time = val / 100.0
        self.update_frame(self.current_time)

    def on_tick(self):
        self.current_time += 0.03
        if self.current_time > 1.0:
            self.current_time = 1.0
            self.toggle_play()

        self.time_slider.setValue(int(self.current_time * 100))
        self.update_frame(self.current_time)

    def update_frame(self, t):
        try:
            self.time_label.setText(f"{t:.1f}s")
            scale = 15

            for eid, track in self.tracks.items():
                if not track: continue

                before = track[0]
                after = track[-1]
                for p in track:
                    if p['t'] <= t: before = p
                    if p['t'] >= t:
                        after = p
                        break

                if after['t'] == before['t']:
                    curr_x, curr_y = before['x'], before['y']
                else:
                    ratio = (t - before['t']) / (after['t'] - before['t'])
                    curr_x = before['x'] + (after['x'] - before['x']) * ratio
                    curr_y = before['y'] + (after['y'] - before['y']) * ratio

                name = self.id_to_name.get(eid, "Unknown")
                is_enemy = eid.startswith("40") or name == "Unknown"
                is_main_boss = (eid == self.main_boss_id)
                is_victim = (name == self.victim_name)

                if is_enemy and not is_main_boss: continue

                if eid not in self.entity_items:
                    job_id = self.id_to_job.get(eid, 0)

                    if is_main_boss:
                        size, color, text = 16, QColor("#FF2222"), "Boss"
                        z_val = 10
                    elif is_victim:
                        job_str = f"[{JOB_MAP.get(job_id, '未知')}] " if job_id else ""
                        size, color, text = 12, QColor("#FF4444"), job_str + name
                        z_val = 20
                    else:
                        job_str = f"[{JOB_MAP.get(job_id, '未知')}] " if job_id else ""
                        color_hex = JOB_COLORS.get(job_id, "#CCCCCC")
                        size, color, text = 10, QColor(color_hex), job_str + name
                        z_val = 5

                    dot = QGraphicsEllipseItem(0, 0, size, size)
                    dot.setBrush(QBrush(color))
                    dot.setPen(QPen(Qt.GlobalColor.white, 1.5))
                    dot.setZValue(z_val)

                    if text:
                        label = QGraphicsTextItem(text)
                        label.setDefaultTextColor(Qt.GlobalColor.white if is_victim else color)
                        label.setFont(QFont("Microsoft YaHei", 9, QFont.Weight.Bold))
                        label.setParentItem(dot)
                        label.setPos(-20, -22)

                    dead_x = QGraphicsTextItem("❌")
                    dead_x.setFont(QFont("Microsoft YaHei", 12))
                    dead_x.setDefaultTextColor(QColor("#FF0000"))
                    dead_x.setParentItem(dot)
                    dead_x.setPos(-9, -13)
                    dead_x.hide()

                    self.scene.addItem(dot)
                    self.entity_items[eid] = {"dot": dot, "dead_x": dead_x, "is_victim": is_victim, "color": color}

                item_dict = self.entity_items[eid]
                dot = item_dict["dot"]
                dot.setPos(curr_x * scale - dot.rect().width() / 2, curr_y * scale - dot.rect().height() / 2)

                if item_dict["is_victim"]:
                    if t >= 0.0:
                        dot.setBrush(QBrush(Qt.GlobalColor.transparent))
                        dot.setPen(QPen(Qt.GlobalColor.transparent))
                        item_dict["dead_x"].show()
                    else:
                        dot.setBrush(QBrush(item_dict["color"]))
                        dot.setPen(QPen(Qt.GlobalColor.white, 1.5))
                        item_dict["dead_x"].hide()
        except Exception:
            pass