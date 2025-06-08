import requests
import pandas as pd
import time
from flow_analysis import run_flow_analysis
from analyze_zone_flow_from_summary import summarize_flows
from datetime import datetime, timedelta

def fetch_loki_logs():
    LOKI_URL = "http://loki:3100"
    query = '{job="syslog_raw"}'
    limit = 4000
    now = time.time()
    start_ns = int((now - 86400 * 7) * 1e9)  # 7일 전 (ns)
    #start_ns = int((now - 86400 * 1) * 1e9) # 하루
    end_ns = int(now * 1e9)

    log_lines = []
    next_start = start_ns

    print("📥 Loki에서 주간 로그 수집 시작...")

    while True:
        resp = requests.get(
            f"{LOKI_URL}/loki/api/v1/query_range",
            params={
                "query": query,
                "start": next_start,
                "end": end_ns,
                "limit": limit,
                "direction": "forward"
            }
        )

        data = resp.json().get("data", {}).get("result", [])
        entries_count = 0

        for stream in data:
            values = stream.get("values", [])
            entries_count += len(values)
            log_lines.extend([entry[1] for entry in values])

        print(f"  ➤ {entries_count}줄 수집됨 (누적 {len(log_lines)}줄)")

        if entries_count == 0:
            break

        last_ts = int(stream["values"][-1][0])
        next_start = last_ts + 1

        time.sleep(0.2)

    print("✅ Loki 로그 수집 완료.")
    return pd.DataFrame(log_lines, columns=["Line"])

df_log = fetch_loki_logs()
flow_summary = run_flow_analysis(df_log)
summary_payload = summarize_flows(flow_summary)

res = requests.post("http://n8n:5678/webhook/zone-report", json=summary_payload) # 워크플로우 생성시 만드는 웹훅 url로 설정
print("📤 n8n 전송 완료:", res.status_code)
