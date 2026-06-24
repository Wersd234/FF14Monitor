import json
import urllib.request
import urllib.parse
import base64
import os

# ==========================================
# 🔧 请在这里填入你的测试信息
# ==========================================
CLIENT_ID = "a144622a-89c3-4561-a55e-5d00449f6d11"
CLIENT_SECRET = "FeyH32gXwfBaH8JK4kA5Qu6wEkbqnAFqEAzLCveJ"
REPORT_CODE = "dqv179fcmrPKyWzD"  # 例如: "aBcD1234EFgh5678" (链接 reports/ 后面的部分)
FIGHT_ID = "3"  # 战斗回合 ID，例如 "10"


def fetch_raw_fflogs():
    print("🚀 开始获取 FFLogs 原始数据...")

    # 1. 获取 Token
    print("🔑 正在请求授权 Token...")
    token_url = "https://www.fflogs.com/oauth/token"
    data = urllib.parse.urlencode({'grant_type': 'client_credentials'}).encode('ascii')
    auth_str = f"{CLIENT_ID}:{CLIENT_SECRET}"
    b64_auth = base64.b64encode(auth_str.encode('ascii')).decode('ascii')

    req = urllib.request.Request(token_url, data=data, headers={'Authorization': f'Basic {b64_auth}'})
    with urllib.request.urlopen(req, timeout=10) as res:
        token = json.loads(res.read().decode())['access_token']

    api_url = "https://www.fflogs.com/api/v2/client"
    headers = {'Content-Type': 'application/json', 'Authorization': f'Bearer {token}'}

    # 2. 获取战斗列表 (Fights) 和 原始技能字典 (MasterData)
    print(f"📄 正在拉取 Report [{REPORT_CODE}] 的元数据...")
    query_fights = """
    query($code: String!) { 
      reportData { 
        report(code: $code) { 
          fights { id startTime endTime name } 
          masterData {
            abilities { gameID name type }
          }
        } 
      } 
    }
    """
    payload = {"query": query_fights, "variables": {"code": REPORT_CODE}}
    req = urllib.request.Request(api_url, data=json.dumps(payload).encode('utf-8'), headers=headers)
    with urllib.request.urlopen(req, timeout=10) as res:
        fights_data = json.loads(res.read().decode())

    # 保存元数据到文件
    with open("raw_metadata_dump.json", "w", encoding="utf-8") as f:
        json.dump(fights_data, f, indent=2, ensure_ascii=False)
    print("✅ 元数据已保存至: raw_metadata_dump.json")

    # 找到目标战斗的开始和结束时间
    report_node = fights_data.get('data', {}).get('reportData', {}).get('report', {})
    fights = report_node.get('fights', [])
    target_fight = next((f for f in fights if str(f['id']) == str(FIGHT_ID)), None)

    if not target_fight:
        print("❌ 未找到指定的 Fight ID，请检查参数！")
        return

    start_time = target_fight['startTime']
    end_time = target_fight['endTime']

    # 3. 拉取全部受击事件 (Events) - 不做任何筛选清洗
    print(f"⚔️ 正在循环拉取战斗 [{target_fight['name']}] 的原始受击事件...")
    # 注意这里：dataType 改成了 All，你可以看到所有的伤害、治疗、Buff！
    # 如果你只想看伤害，可以改回 dataType: DamageTaken
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

    all_raw_events = []
    next_start = start_time
    page = 1

    while next_start and next_start <= end_time:
        payload = {
            "query": query_events,
            "variables": {"code": REPORT_CODE, "start": next_start, "end": end_time}
        }
        req = urllib.request.Request(api_url, data=json.dumps(payload).encode('utf-8'), headers=headers)
        with urllib.request.urlopen(req, timeout=15) as res:
            events_data = json.loads(res.read().decode())

        event_res = events_data.get('data', {}).get('reportData', {}).get('report', {}).get('events', {})
        page_events = event_res.get('data', [])
        all_raw_events.extend(page_events)

        next_start = event_res.get('nextPageTimestamp')
        print(f"  📥 拉取第 {page} 页 (本页包含 {len(page_events)} 条事件)...")
        page += 1

    # 保存最原始的 Event 数组到文件
    with open("raw_events_dump.json", "w", encoding="utf-8") as f:
        json.dump(all_raw_events, f, indent=2, ensure_ascii=False)
    print(f"✅ 成功！总计 {len(all_raw_events)} 条原始事件已保存至: raw_events_dump.json")


if __name__ == "__main__":
    fetch_raw_fflogs()