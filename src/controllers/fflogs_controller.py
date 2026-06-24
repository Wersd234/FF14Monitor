# ==========================================
# File: src/controller/fflogs_controller.py
# 职责: 负责 FFLogs API 请求、国服汉化、数据清洗与逆推
# ==========================================
import os
import json
import urllib.request
import urllib.parse
import base64
from PyQt6.QtCore import QThread, pyqtSignal

# 翻译缓存库路径
CACHE_PATH = os.path.join(os.getcwd(), "assets", "translation_cache.json")


def get_safe_float(val, default=0.0):
    if val is None or val == "": return default
    try:
        return float(val)
    except Exception:
        return default


class FFLogsWorker(QThread):
    progress = pyqtSignal(str)
    finished = pyqtSignal(list)
    error = pyqtSignal(str)

    def __init__(self, client_id, client_secret, report_code, fight_id):
        super().__init__()
        self.client_id = client_id
        self.client_secret = client_secret
        self.report_code = report_code
        self.fight_id = fight_id

        # 初始化本地翻译缓存字典
        self.translation_cache = {}
        self.cache_updated = False
        if os.path.exists(CACHE_PATH):
            try:
                with open(CACHE_PATH, 'r', encoding='utf-8') as f:
                    self.translation_cache = json.load(f)
            except:
                pass

    def get_cn_skill_name(self, skill_id, fallback_name):
        """通过肥肥咖啡 API 获取国服纯正中文技能名"""
        if not skill_id or skill_id == "0":
            return fallback_name

        skill_id_str = str(skill_id)

        if skill_id_str in self.translation_cache:
            return self.translation_cache[skill_id_str]

        self.progress.emit(f"  🌐 发现未知技能 ID:{skill_id} ({fallback_name})，正在请求国服数据...")
        url = f"https://cafemaker.wakingsands.com/Action/{skill_id}?columns=Name"
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 (FF14_Monitor)'})
            with urllib.request.urlopen(req, timeout=3) as res:
                data = json.loads(res.read().decode('utf-8'))
                cn_name = data.get("Name")
                if cn_name:
                    self.translation_cache[skill_id_str] = cn_name
                    self.cache_updated = True
                    self.progress.emit(f"    ✅ 翻译成功: {fallback_name} -> {cn_name}")
                    return cn_name
        except Exception:
            self.progress.emit(f"    ⚠️ 翻译超时或失败，暂用英文名兜底。")

        return fallback_name

    def run(self):
        try:
            self.progress.emit("正在获取 FFLogs 授权 Token...")
            token_url = "https://www.fflogs.com/oauth/token"
            data = urllib.parse.urlencode({'grant_type': 'client_credentials'}).encode('ascii')
            auth_str = f"{self.client_id}:{self.client_secret}"
            b64_auth = base64.b64encode(auth_str.encode('ascii')).decode('ascii')

            req = urllib.request.Request(token_url, data=data, headers={'Authorization': f'Basic {b64_auth}'})
            with urllib.request.urlopen(req, timeout=10) as res:
                token = json.loads(res.read().decode())['access_token']

            self.progress.emit(f"授权成功！正在拉取 Report: {self.report_code} 的战斗列表...")
            api_url = "https://www.fflogs.com/api/v2/client"
            headers = {'Content-Type': 'application/json', 'Authorization': f'Bearer {token}'}

            query_fights = """
            query($code: String!) { 
              reportData { 
                report(code: $code) { 
                  fights { id startTime endTime name } 
                  masterData { abilities { gameID name } }
                } 
              } 
            }
            """
            payload = {"query": query_fights, "variables": {"code": self.report_code}}
            req = urllib.request.Request(api_url, data=json.dumps(payload).encode('utf-8'), headers=headers)
            with urllib.request.urlopen(req, timeout=10) as res:
                fights_data = json.loads(res.read().decode())

            if "errors" in fights_data:
                self.error.emit(f"FFLogs API 拒绝访问: {fights_data['errors'][0]['message']}")
                return

            report_node = fights_data.get('data', {}).get('reportData', {}).get('report', {})
            fights = report_node.get('fights', [])
            target_fight = next((f for f in fights if str(f['id']) == str(self.fight_id)),
                                fights[-1] if fights else None)
            if not target_fight:
                self.error.emit("未找到战斗回合！")
                return

            start_time = target_fight['startTime']
            end_time = target_fight['endTime']
            fight_name = target_fight['name']

            master_data = report_node.get('masterData', {})
            en_ability_dict = {str(a['gameID']): a.get('name', 'Unknown') for a in master_data.get('abilities', [])}

            self.progress.emit(f"锁定战斗: {fight_name}。开始分批拉取事件流...")

            query_events = """
            query($code: String!, $start: Float!, $end: Float!) {
              reportData {
                report(code: $code) {
                  events(startTime: $start, endTime: $end, dataType: DamageTaken, hostilityType: Friendlies, limit: 10000) { 
                    data 
                    nextPageTimestamp 
                  }
                }
              }
            }
            """

            all_events = []
            next_start = start_time
            page = 1

            while next_start and next_start <= end_time:
                payload = {
                    "query": query_events,
                    "variables": {"code": self.report_code, "start": next_start, "end": end_time}
                }
                req = urllib.request.Request(api_url, data=json.dumps(payload).encode('utf-8'), headers=headers)
                with urllib.request.urlopen(req, timeout=15) as res:
                    events_data = json.loads(res.read().decode())

                event_res = events_data.get('data', {}).get('reportData', {}).get('report', {}).get('events', {})
                page_events = event_res.get('data', [])
                all_events.extend(page_events)
                next_start = event_res.get('nextPageTimestamp')

                self.progress.emit(f"📦 已拉取第 {page} 页 (本页获取 {len(page_events)} 条数据)...")
                page += 1

            self.progress.emit(f"📥 获取完毕！共计 {len(all_events)} 条受击记录。正在进行汉化与逆向推算...")

            timeline_dict = []
            max_debug_dmg = 0
            total_events = len(all_events)

            for index, evt in enumerate(all_events):
                if index > 0 and index % 500 == 0:
                    self.progress.emit(f"  ⚙️ 正在清洗数据... 进度: {index} / {total_events}")

                evt_type = evt.get('type', '')
                if evt_type not in ['damage', 'calculateddamage']: continue

                source = evt.get('source', {})
                if source and source.get('type') == 'Player': continue

                ability_id = str(evt.get('abilityGameID', ''))
                en_name = en_ability_dict.get(ability_id, evt.get('ability', {}).get('name', 'Unknown'))
                skill_name = self.get_cn_skill_name(ability_id, en_name)

                # 【增强版过滤】: 过滤无效 ID、日文攻撃、unknown平A等垃圾数据
                if ability_id == "500000" or skill_name == "Combined DoTs": continue
                if not skill_name or "unknown" in skill_name.lower() or skill_name.lower() in ["none", ""]: continue
                if skill_name in ["Attack", "攻击", "攻撃", "自动攻击", "Weaponskill", "战技"]: continue
                if "attack" in skill_name.lower() or "攻撃" in skill_name: continue

                rel_time_float = (evt.get('timestamp', start_time) - start_time) / 1000.0
                target_id = evt.get('targetID')
                is_dot_tick = (evt.get('tick') is True)

                # 提取裸伤
                try:
                    unmit = evt.get('unmitigatedAmount')
                    if unmit is not None:
                        raw_dmg = int(get_safe_float(unmit))
                    else:
                        amt = int(get_safe_float(evt.get('amount')))
                        absb = int(get_safe_float(evt.get('absorbed')))
                        mit = int(get_safe_float(evt.get('mitigated')))
                        multiplier = get_safe_float(evt.get('multiplier'), 1.0)
                        if 0 < multiplier < 1.0:
                            raw_dmg = int((amt + absb) / multiplier)
                        else:
                            raw_dmg = amt + mit + absb
                except Exception:
                    raw_dmg = 0

                if raw_dmg > max_debug_dmg: max_debug_dmg = raw_dmg
                if raw_dmg < 5000: continue

                if is_dot_tick:
                    skill_name = f"[DoT] {skill_name}"
                    group_window = 25.0
                else:
                    group_window = 3.0

                matched = False
                for t_evt in reversed(timeline_dict):
                    if t_evt['skill'] == skill_name and abs(t_evt['float_time'] - rel_time_float) <= group_window:
                        if raw_dmg > t_evt['raw_dmg']:
                            t_evt['raw_dmg'] = raw_dmg
                        if target_id:
                            t_evt['targets'].add(target_id)
                        matched = True
                        break

                if not matched:
                    timeline_dict.append({
                        "float_time": rel_time_float,
                        "time": int(rel_time_float),
                        "skill": skill_name,
                        "raw_dmg": raw_dmg,
                        "targets": {target_id} if target_id else set(),
                        "is_dot": is_dot_tick,
                        "mits": []
                    })

            if self.cache_updated:
                os.makedirs(os.path.dirname(CACHE_PATH), exist_ok=True)
                with open(CACHE_PATH, 'w', encoding='utf-8') as f:
                    json.dump(self.translation_cache, f, ensure_ascii=False, indent=2)

            final_timeline = []
            for t_evt in timeline_dict:
                if t_evt['raw_dmg'] >= 15000 or t_evt.get('is_dot'):
                    if t_evt.get('is_dot'):
                        t_evt['dmg_type'] = "DoT (Tick)"
                    else:
                        hit_count = len(t_evt['targets'])
                        if hit_count >= 5:
                            t_evt['dmg_type'] = "AOE (Raid)"
                        elif hit_count > 1:
                            t_evt['dmg_type'] = f"Cleave ({hit_count} Targets)"
                        else:
                            t_evt['dmg_type'] = "Single (TB)"

                    t_evt.pop('targets', None)
                    t_evt.pop('float_time', None)
                    t_evt.pop('is_dot', None)

                    m, s = divmod(t_evt['time'], 60)
                    t_evt['time_str'] = f"{m:02d}:{s:02d}"
                    final_timeline.append(t_evt)
                    self.progress.emit(
                        f"  👉 提取成功: [{t_evt['time_str']}] {t_evt['skill']} [{t_evt['dmg_type']}] (裸伤: {t_evt['raw_dmg']:,})")

            final_timeline.sort(key=lambda x: x["time"])

            if not final_timeline:
                self.error.emit(f"❌ 诊断失败！最高单次伤害仅为 {max_debug_dmg}。请确认日志有效性。")
            else:
                self.finished.emit(final_timeline)
        except Exception as e:
            self.error.emit(f"发生网络或解析错误: {str(e)}")