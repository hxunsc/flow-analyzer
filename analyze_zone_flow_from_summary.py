def summarize_flows(flow_summary):
    import pandas as pd
    from collections import defaultdict, Counter

    # 전처리
    flow_summary["start_time"] = pd.to_datetime(flow_summary["start_time"])
    flow_summary["end_time"] = pd.to_datetime(flow_summary["end_time"])
    flow_summary["duration_seconds"] = (flow_summary["end_time"] - flow_summary["start_time"]).dt.total_seconds()
    flow_summary["hour"] = flow_summary["start_time"].dt.hour
    flow_summary["date"] = flow_summary["start_time"].dt.date

    zone_label_map = {
        "1": "1층 출입구", "6": "1.5층 출입구", "I": "1층 카페 앞", "H": "1층 내 쇼파석",
        "A": "1층 문쪽 공간", "C": "1층 계단쪽 공간", "E": "화장실 앞 복도", "L": "1.5층 내부 공간",
        "J": "2층 전시장 앞 공간", "K": "2층 전시장 내 공간", "M": "1층 바깥쪽 회의실 공간", "N": "1층 안쪽 회의실 공간"
    }

    def map_zone_name(z): return zone_label_map.get(z, z)

    def clean_and_split(flow):
        if pd.isna(flow): return []
        cleaned = flow.replace("→", "->").replace(" → ", "->").strip()
        return [z.strip() for z in cleaned.split("->")]

    # 체류시간 구간 분포
    bins = [0, 300, 900, 1800, float("inf")]
    labels = ["0~5분", "5~15분", "15~30분", "30분 이상"]
    flow_summary["duration_category"] = pd.cut(flow_summary["duration_seconds"], bins=bins, labels=labels, right=False)
    duration_distribution = flow_summary["duration_category"].value_counts().sort_index().to_dict()

    # 마지막 zone 기준 평균 체류시간
    flow_summary["last_zone"] = flow_summary["zone_flow"].map(lambda f: clean_and_split(f)[-1] if pd.notna(f) else None)
    zone_avg_duration = flow_summary.groupby("last_zone")["duration_seconds"].mean().round(2)
    zone_avg_duration.index = zone_avg_duration.index.map(map_zone_name)
    zone_avg_duration = zone_avg_duration.to_dict()

    # 시간대별 zone 이동 흐름
    zone_hour_map = {}
    for _, row in flow_summary.iterrows():
        for z in clean_and_split(row["zone_flow"]):
            zone_hour_map.setdefault(z, {}).setdefault(row["hour"], 0)
            zone_hour_map[z][row["hour"]] += 1
    zone_hour_df = pd.DataFrame(zone_hour_map).fillna(0).astype(int).T
    zone_hour_df.index = zone_hour_df.index.map(map_zone_name)
    zone_hour_flow = zone_hour_df.to_dict(orient="dict")

    # 혼잡 zone 및 시간대
    zone_peak_info = pd.DataFrame({
        "최대 혼잡도": zone_hour_df.max(axis=1),
        "혼잡 발생 시간대": zone_hour_df.idxmax(axis=1)
    }).sort_values("최대 혼잡도", ascending=False)
    zone_peak_info = zone_peak_info.to_dict()

    # 시작/종료 zone 통계
    zone_group_map = {"1": "1층 출입구", "6": "1.5층 출입구", "L": "1.5층 출입구", "E": "화장실 앞 복도", "I": "카페 앞 출입구"}
    first_zone_counter, end_zone_counter = defaultdict(int), defaultdict(int)
    for flow in flow_summary["zone_flow"].dropna():
        zones = clean_and_split(flow)
        if zones:
            first_zone_counter[zones[0]] += 1
            end_zone_counter[zones[-1]] += 1
    grouped_counter_start, grouped_counter_end = defaultdict(int), defaultdict(int)
    for z, c in first_zone_counter.items():
        grouped_counter_start[zone_group_map.get(z, "기타")] += c
    for z, c in end_zone_counter.items():
        grouped_counter_end[zone_group_map.get(z, "기타")] += c
    zone_first_visits = pd.DataFrame.from_dict(grouped_counter_start, orient="index", columns=["first_visit_count"]).reset_index().rename(columns={"index": "zone"}).to_dict(orient="records")
    zone_last_visits = pd.DataFrame.from_dict(grouped_counter_end, orient="index", columns=["last_visit_count"]).reset_index().rename(columns={"index": "zone"}).to_dict(orient="records")

    # Top 5 이동 흐름
    multi_zone_df = flow_summary[flow_summary["zone_flow"].apply(lambda x: len(clean_and_split(x)) >= 2)]
    top_flows = multi_zone_df["zone_flow"].value_counts().head(5)
    top_multi_flows = {
        " → ".join([map_zone_name(z) for z in clean_and_split(flow)]): f"{count}회"
        for flow, count in top_flows.items()
    }

    # zone 등장 횟수 / 허브 / 서브플로우
    all_zones, hub_zones = [], Counter()
    subflow_counter_2, subflow_counter_3 = Counter(), Counter()
    for flow in flow_summary["zone_flow"].dropna():
        zones = clean_and_split(flow)
        all_zones += zones
        if len(zones) > 2:
            for z in zones[1:-1]:
                hub_zones[z] += 1
        for i in range(len(zones) - 1):
            sub2 = "→".join(zones[i:i+2])
            subflow_counter_2[sub2] += 1
        for i in range(len(zones) - 2):
            sub3 = "→".join(zones[i:i+3])
            subflow_counter_3[sub3] += 1
    zone_appearance = {map_zone_name(k): v for k, v in Counter(all_zones).most_common(5)}
    hub_zones_named = {map_zone_name(k): v for k, v in hub_zones.most_common(3)}
    subflows_2_named = {" → ".join(map_zone_name(z) for z in k.split("→")): v for k, v in subflow_counter_2.most_common(5)}
    subflows_3_named = {" → ".join(map_zone_name(z) for z in k.split("→")): v for k, v in subflow_counter_3.most_common(5)}

    # 날짜별 고유 사용자 수
    unique_users_by_date = flow_summary.groupby("date")["user_id"].nunique().to_dict()

    return {
        "duration_distribution": duration_distribution,
        "zone_avg_duration": zone_avg_duration,
        "zone_hour_flow": zone_hour_flow,
        "zone_peak_info": zone_peak_info,
        "zone_first_visits": zone_first_visits,
        "zone_last_visits": zone_last_visits,
        "top_multi_flows": top_multi_flows,
        "zone_appearance": zone_appearance,
        "hub_zones": hub_zones_named,
        "subflows_2": subflows_2_named,
        "subflows_3": subflows_3_named,
        "unique_users_by_date": unique_users_by_date,
        "avg_duration": round(flow_summary["duration_seconds"].mean(), 2),
        "max_duration": round(flow_summary["duration_seconds"].max(), 2),
        "flow_count": int(len(flow_summary))
    }
