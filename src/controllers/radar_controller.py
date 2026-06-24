import urllib.request
import json
from PyQt6.QtCore import QThread, pyqtSignal


class MapFetcherThread(QThread):
    """雷达后端：后台静默下载 FFXIV 高清副本地图"""
    map_ready = pyqtSignal(bytes, dict)

    def __init__(self, zone_id):
        super().__init__()
        self.zone_id = zone_id

    def run(self):
        try:
            if not self.zone_id or self.zone_id in ["0", "Unknown"]: return

            apis = ["https://xivapi.com", "https://cafemaker.wakingsands.com"]
            for base_url in apis:
                try:
                    url1 = f"{base_url}/TerritoryType/{self.zone_id}?columns=Map"
                    req1 = urllib.request.Request(url1, headers={'User-Agent': 'Mozilla/5.0'})
                    with urllib.request.urlopen(req1, timeout=3) as res:
                        data1 = json.loads(res.read().decode())

                    map_id = data1.get("Map", {}).get("ID")
                    if not map_id: continue

                    url2 = f"{base_url}/Map/{map_id}"
                    req2 = urllib.request.Request(url2, headers={'User-Agent': 'Mozilla/5.0'})
                    with urllib.request.urlopen(req2, timeout=3) as res:
                        data2 = json.loads(res.read().decode())

                    img_path = data2.get("Map")
                    if not img_path: continue

                    url3 = f"{base_url}{img_path}"
                    req3 = urllib.request.Request(url3, headers={'User-Agent': 'Mozilla/5.0'})
                    with urllib.request.urlopen(req3, timeout=5) as res:
                        img_bytes = res.read()

                    self.map_ready.emit(img_bytes, data2)
                    break
                except Exception:
                    continue
        except Exception:
            pass


def process_radar_data(replay_data, victim_name):
    """雷达后端：将乱序的时间轴数据打包成分类轨道，并寻找 Boss"""
    tracks = {}
    id_to_name = {}
    main_boss_id = None

    for p in replay_data:
        eid = p['id']
        if p['name'] != "Unknown":
            id_to_name[eid] = p['name']
        if eid not in tracks:
            tracks[eid] = []
        tracks[eid].append(p)

    for eid in tracks:
        tracks[eid].sort(key=lambda x: x['t'])

    max_points = 0
    for eid, track in tracks.items():
        name = id_to_name.get(eid, "Unknown")
        if eid.startswith("40") and name != "Unknown":
            if len(track) > max_points:
                max_points = len(track)
                main_boss_id = eid

    return tracks, id_to_name, main_boss_id